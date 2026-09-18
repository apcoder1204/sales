"""
Demo data seed script — populates a rich, realistic dataset for the demo
environment (demo.cctvpoint.org) ONLY. Never run this against the production
database.

Fully idempotent: every run wipes and rebuilds the transactional tables it
owns (products, inventory, inventory_transactions, sales, sale_items,
stock_transfers, stock_transfer_items, daily_closings) and regenerates them
from scratch. The org skeleton (branches, roles, users, categories) is
created once via app.db.seed and left alone on subsequent runs.

This doubles as the nightly reset script — see backend/scripts/reset_demo_data.sh.

  python -m app.db.seed_demo
"""
import asyncio
import random
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import select, delete

from app.db.session import AsyncSessionLocal
from app.models.branch import Branch
from app.models.role import Role
from app.models.category import Category
from app.models.user import User
from app.models.product import Product
from app.models.inventory import Inventory
from app.models.inventory_transaction import InventoryTransaction
from app.models.sale import Sale
from app.models.sale_item import SaleItem
from app.models.stock_transfer import StockTransfer
from app.models.stock_transfer_item import StockTransferItem
from app.models.daily_closing import DailyClosing

UTC = timezone.utc


def _utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


DAYS_OF_HISTORY = 21
BUSINESS_START_HOUR = 8
BUSINESS_END_HOUR = 19

# (code, name, category_name, brand, unit, cost_price, selling_price, minimum_stock)
DEMO_PRODUCTS = [
    ("CAM-DOM-2MP", "2MP Dome Camera Indoor", "CCTV Camera", "Hikvision", "Kipande", 45000, 68000, 10),
    ("CAM-BUL-2MP", "2MP Bullet Camera Outdoor", "CCTV Camera", "Hikvision", "Kipande", 52000, 78000, 10),
    ("CAM-DOM-4MP", "4MP Dome Camera Indoor", "CCTV Camera", "Hikvision", "Kipande", 68000, 98000, 8),
    ("CAM-BUL-4MP", "4MP Bullet Camera Outdoor", "CCTV Camera", "Hikvision", "Kipande", 75000, 110000, 8),
    ("CAM-PTZ-5X", "5X Zoom PTZ Camera", "CCTV Camera", "Dahua", "Kipande", 185000, 260000, 4),
    ("CAM-WIFI-3MP", "3MP WiFi Camera", "CCTV Camera", "Reolink", "Kipande", 58000, 89000, 12),
    ("CAM-4G-3MP", "3MP 4G SIM Camera", "CCTV Camera", "Reolink", "Kipande", 120000, 175000, 6),
    ("NVR-4CH", "4-Channel NVR", "CCTV Camera", "Hikvision", "Kipande", 95000, 140000, 6),
    ("NVR-8CH", "8-Channel NVR", "CCTV Camera", "Hikvision", "Kipande", 165000, 235000, 5),
    ("NVR-16CH", "16-Channel NVR", "CCTV Camera", "Hikvision", "Kipande", 320000, 445000, 3),
    ("HDD-1TB", "1TB Surveillance Hard Drive", "CCTV Camera", "Western Digital", "Kipande", 78000, 110000, 15),
    ("HDD-2TB", "2TB Surveillance Hard Drive", "CCTV Camera", "Western Digital", "Kipande", 135000, 185000, 10),
    ("BNC-CABLE-100", "100m BNC + Power Cable Roll", "CCTV Camera", "Generic", "Mfuko / Sanduku", 65000, 95000, 8),
    ("ACC-FP-READER", "Fingerprint Access Reader", "Access Control", "ZKTeco", "Kipande", 95000, 145000, 8),
    ("ACC-RFID-CARD", "RFID Card Reader", "Access Control", "ZKTeco", "Kipande", 55000, 82000, 10),
    ("ACC-EXIT-BTN", "Exit Push Button", "Access Control", "Generic", "Kipande", 8000, 15000, 20),
    ("ACC-MAG-LOCK", "Magnetic Door Lock 280kg", "Access Control", "ZKTeco", "Kipande", 45000, 68000, 10),
    ("ACC-EL-LOCK", "Electric Strike Lock", "Access Control", "Generic", "Kipande", 32000, 49000, 12),
    ("ACC-CARD-50", "RFID Access Cards (pack of 50)", "Access Control", "Generic", "Mfuko / Sanduku", 35000, 55000, 6),
    ("ACC-TURNSTILE", "Tripod Turnstile Gate", "Access Control", "ZKTeco", "Kipande", 850000, 1150000, 2),
    ("NET-SW-8POE", "8-Port PoE Switch", "Networking", "TP-Link", "Kipande", 85000, 125000, 8),
    ("NET-SW-16POE", "16-Port PoE Switch", "Networking", "TP-Link", "Kipande", 165000, 235000, 5),
    ("NET-ROUTER", "Wireless Gigabit Router", "Networking", "TP-Link", "Kipande", 48000, 72000, 10),
    ("NET-CAT6-305", "Cat6 Cable Box 305m", "Networking", "Generic", "Mfuko / Sanduku", 145000, 195000, 6),
    ("NET-RJ45-100", "RJ45 Connectors (pack of 100)", "Networking", "Generic", "Mfuko / Sanduku", 12000, 20000, 15),
    ("NET-UPS-650", "650VA UPS Backup", "Networking", "APC", "Kipande", 68000, 98000, 10),
    ("NET-UPS-1200", "1200VA UPS Backup", "Networking", "APC", "Kipande", 145000, 205000, 6),
    ("ALM-PANEL-8Z", "8-Zone Alarm Control Panel", "Alarm System", "Paradox", "Kipande", 165000, 235000, 5),
    ("ALM-MOTION", "PIR Motion Sensor", "Alarm System", "Paradox", "Kipande", 22000, 35000, 15),
    ("ALM-DOOR-SENS", "Door/Window Contact Sensor", "Alarm System", "Paradox", "Kipande", 15000, 24000, 20),
    ("ALM-SIREN", "Outdoor Alarm Siren + Strobe", "Alarm System", "Paradox", "Kipande", 35000, 52000, 8),
    ("ALM-SMOKE", "Smoke Detector", "Alarm System", "Generic", "Kipande", 28000, 42000, 12),
    ("ALM-REMOTE", "Wireless Remote Control (pair)", "Alarm System", "Paradox", "Kipande", 12000, 19000, 15),
]

# Weighted so cash/mobile money dominate, matching typical TZ retail mix.
PAYMENT_METHODS = ["cash"] * 3 + ["mobile_money"] * 3 + ["bank_transfer"]

_txn_seq = 0
_transfer_seq = 0


def _next_txn_no(business_date) -> str:
    global _txn_seq
    _txn_seq += 1
    return f"TXN-{business_date:%Y%m%d}-{_txn_seq:04d}"


def _next_transfer_no(business_date) -> str:
    global _transfer_seq
    _transfer_seq += 1
    return f"TRF-{business_date:%Y%m%d}-{_transfer_seq:04d}"


def _random_time_on(day) -> datetime:
    hour = random.randint(BUSINESS_START_HOUR, BUSINESS_END_HOUR - 1)
    minute = random.randint(0, 59)
    second = random.randint(0, 59)
    return datetime.combine(day, datetime.min.time()).replace(hour=hour, minute=minute, second=second)


async def _ensure_skeleton(db) -> None:
    """Create branches/roles/categories/users once, via the same script
    production uses, if they don't already exist. Never wiped on reruns."""
    existing = await db.execute(select(Role).limit(1))
    if existing.scalar_one_or_none():
        return
    from app.db.seed import seed as seed_skeleton
    await seed_skeleton()


async def _wipe_generated_data(db) -> None:
    """Delete everything this script owns, in FK-safe (dependents-first)
    order. Never touches branches/roles/users/categories."""
    for model in (
        SaleItem, Sale, StockTransferItem, StockTransfer,
        InventoryTransaction, Inventory, DailyClosing, Product,
    ):
        await db.execute(delete(model))
    await db.commit()


async def _create_products(db, categories: dict[str, Category]) -> list[Product]:
    products = []
    for code, name, cat_name, brand, unit, cost, price, min_stock in DEMO_PRODUCTS:
        p = Product(
            product_code=code, name=name, category_id=categories[cat_name].id,
            brand=brand, unit=unit,
            cost_price=Decimal(cost), selling_price=Decimal(price),
            minimum_stock=min_stock, status="active",
        )
        db.add(p)
        products.append(p)
    await db.flush()
    return products


async def _stock_in(db, product: Product, branch: Branch, qty: int, actor: User) -> None:
    inv = Inventory(product_id=product.id, branch_id=branch.id, quantity=qty, reserved_qty=0)
    db.add(inv)
    await db.flush()
    db.add(InventoryTransaction(
        product_id=product.id, branch_id=branch.id, transaction_type="stock_in",
        quantity_before=0, quantity_change=qty, quantity_after=qty,
        notes="Awali — mzigo wa kuanzia", performed_by=actor.id,
    ))


async def _seed_initial_stock_and_transfers(
    db, products: list[Product], main_store: Branch, pos_branches: list[Branch], actor: User
) -> dict[tuple, int]:
    """Stocks Main Store generously, then transfers a portion of each
    product to every POS branch (mirrors the real restock → transfer flow).
    Returns a {(product_id, branch_id): available_qty} map for sales gen."""
    stock = {}

    for product in products:
        base_qty = product.minimum_stock * random.randint(6, 14)
        await _stock_in(db, product, main_store, base_qty, actor)
        remaining = base_qty
        stock[(product.id, main_store.id)] = base_qty

        tf_items_by_branch: dict = {}
        for pos in pos_branches:
            if remaining <= 0 or random.random() < 0.15:
                continue  # not every product is stocked at every outlet
            share = max(1, int(base_qty * random.uniform(0.1, 0.25)))
            share = min(share, remaining - 1) if remaining > 1 else 0
            if share <= 0:
                continue
            tf_items_by_branch[pos] = share
            remaining -= share

        if not tf_items_by_branch:
            continue

        business_date = (_utcnow() - timedelta(days=DAYS_OF_HISTORY)).date()
        for pos, qty in tf_items_by_branch.items():
            transfer_no = _next_transfer_no(business_date)
            created = _random_time_on(business_date)
            tf = StockTransfer(
                transfer_no=transfer_no, from_branch_id=main_store.id, to_branch_id=pos.id,
                transferred_by=actor.id, status="completed",
                notes="Mzigo wa kuanzia kwa kioski",
                created_at=created, completed_at=created + timedelta(minutes=random.randint(5, 90)),
            )
            db.add(tf)
            await db.flush()

            db.add(StockTransferItem(
                transfer_id=tf.id, product_id=product.id, quantity=qty, unit_cost=product.cost_price,
            ))

            src_before = stock[(product.id, main_store.id)]
            db.add(InventoryTransaction(
                product_id=product.id, branch_id=main_store.id, transaction_type="transfer_out",
                quantity_before=src_before, quantity_change=-qty, quantity_after=src_before - qty,
                reference_id=tf.id, reference_type="transfer", performed_by=actor.id,
            ))
            stock[(product.id, main_store.id)] = src_before - qty

            dst_inv = Inventory(product_id=product.id, branch_id=pos.id, quantity=qty, reserved_qty=0)
            db.add(dst_inv)
            db.add(InventoryTransaction(
                product_id=product.id, branch_id=pos.id, transaction_type="transfer_in",
                quantity_before=0, quantity_change=qty, quantity_after=qty,
                reference_id=tf.id, reference_type="transfer", performed_by=actor.id,
            ))
            stock[(product.id, pos.id)] = qty

        # Sync the Main Store Inventory row to its final post-transfer quantity
        main_inv = (await db.execute(
            select(Inventory).where(Inventory.product_id == product.id, Inventory.branch_id == main_store.id)
        )).scalar_one()
        main_inv.quantity = stock[(product.id, main_store.id)]

    await db.flush()
    return stock


def _pick_sellable(stock: dict, branch: Branch, products: list[Product]) -> Product | None:
    candidates = [p for p in products if stock.get((p.id, branch.id), 0) > 0]
    return random.choice(candidates) if candidates else None


async def _generate_sale(
    db, branch: Branch, cashier: User, products: list[Product], stock: dict, when: datetime,
) -> Sale | None:
    n_items = random.randint(1, 3)
    chosen: dict = {}
    for _ in range(n_items):
        product = _pick_sellable(stock, branch, products)
        if not product or product.id in chosen:
            continue
        available = stock[(product.id, branch.id)]
        qty = min(available, random.randint(1, 3))
        if qty <= 0:
            continue
        chosen[product.id] = (product, qty)

    if not chosen:
        return None

    subtotal = sum(p.selling_price * qty for p, qty in chosen.values())
    business_date = when.date()
    sale = Sale(
        transaction_no=_next_txn_no(business_date),
        branch_id=branch.id, cashier_id=cashier.id,
        subtotal=subtotal, total_amount=subtotal,
        payment_method=random.choice(PAYMENT_METHODS),
        payment_reference=(f"MP{random.randint(100000, 999999)}" if random.random() < 0.4 else None),
        status="completed", created_at=when,
    )
    db.add(sale)
    await db.flush()

    for product, qty in chosen.values():
        line_total = product.selling_price * qty
        db.add(SaleItem(
            sale_id=sale.id, product_id=product.id, quantity=qty,
            unit_price=product.selling_price, cost_price=product.cost_price, line_total=line_total,
        ))
        before = stock[(product.id, branch.id)]
        db.add(InventoryTransaction(
            product_id=product.id, branch_id=branch.id, transaction_type="sale",
            quantity_before=before, quantity_change=-qty, quantity_after=before - qty,
            reference_id=sale.id, reference_type="sale", performed_by=cashier.id,
        ))
        stock[(product.id, branch.id)] = before - qty

    return sale


async def _sync_inventory_rows(db, stock: dict) -> None:
    """Write the final in-memory stock levels back to the Inventory table
    (kept in memory during generation to avoid a DB round-trip per sale)."""
    rows = (await db.execute(select(Inventory))).scalars().all()
    for inv in rows:
        key = (inv.product_id, inv.branch_id)
        if key in stock:
            inv.quantity = stock[key]
    await db.flush()


async def _generate_history(
    db, products: list[Product], pos_branches: list[Branch],
    cashier_by_branch: dict, managers: list[User], stock: dict,
) -> None:
    today = _utcnow().date()

    for days_ago in range(DAYS_OF_HISTORY, 0, -1):
        business_date = today - timedelta(days=days_ago)
        for branch in pos_branches:
            cashier = cashier_by_branch[branch.id]
            n_sales = random.randint(2, 10)
            times = sorted(_random_time_on(business_date) for _ in range(n_sales))

            day_totals = {"cash": Decimal(0), "mobile_money": Decimal(0), "bank_transfer": Decimal(0)}
            sales_count = 0
            for when in times:
                sale = await _generate_sale(db, branch, cashier, products, stock, when)
                if sale:
                    day_totals[sale.payment_method] += sale.total_amount
                    sales_count += 1

            total_revenue = sum(day_totals.values())
            closer = random.choice(managers)
            has_variance = random.random() < 0.3
            variance = Decimal(random.choice([-2000, -1000, 1000, 1500, 2500])) if has_variance else Decimal(0)
            closed_at = _random_time_on(business_date).replace(hour=BUSINESS_END_HOUR, minute=random.randint(0, 45))

            db.add(DailyClosing(
                branch_id=branch.id, business_date=business_date, register_number=1, status="closed",
                total_cash=day_totals["cash"], total_mobile_money=day_totals["mobile_money"],
                total_bank_transfer=day_totals["bank_transfer"], total_sales_count=sales_count,
                total_revenue=total_revenue,
                counted_cash=day_totals["cash"] + variance, cash_variance=variance,
                closing_notes=("Tofauti ndogo — imesababishwa na chenji" if has_variance else None),
                closed_by=closer.id, closed_at=closed_at,
                created_at=closed_at, updated_at=closed_at,
            ))

    # Today: a handful of live sales, register left open (no DailyClosing row)
    # so the demo can show the "close day" flow working end-to-end.
    now = _utcnow()
    for branch in pos_branches:
        cashier = cashier_by_branch[branch.id]
        n_sales = random.randint(2, 5)
        for _ in range(n_sales):
            hour_now = now.hour if now.hour > BUSINESS_START_HOUR else BUSINESS_START_HOUR + 1
            when = now.replace(
                hour=random.randint(BUSINESS_START_HOUR, min(hour_now, BUSINESS_END_HOUR - 1)),
                minute=random.randint(0, 59), second=random.randint(0, 59),
            )
            if when > now:
                when = now
            await _generate_sale(db, branch, cashier, products, stock, when)

    await db.flush()


async def seed_demo() -> None:
    async with AsyncSessionLocal() as db:
        await _ensure_skeleton(db)
        await _wipe_generated_data(db)

        branches = (await db.execute(select(Branch))).scalars().all()
        main_store = next(b for b in branches if b.branch_type == "main_store")
        pos_branches = [b for b in branches if b.branch_type == "pos_point"]

        categories = {c.name: c for c in (await db.execute(select(Category))).scalars().all()}
        users = (await db.execute(select(User))).scalars().all()
        actor = next(u for u in users if u.role.name == "super_admin")
        managers = [u for u in users if u.role.name in ("super_admin", "admin", "general_manager")]
        cashier_by_branch = {
            u.branch_id: u for u in users if u.role.name == "cashier" and u.branch_id is not None
        }

        print("Creating products...")
        products = await _create_products(db, categories)

        print("Stocking Main Store and transferring to POS branches...")
        stock = await _seed_initial_stock_and_transfers(db, products, main_store, pos_branches, actor)

        print(f"Generating {DAYS_OF_HISTORY} days of sales + daily closings...")
        await _generate_history(db, products, pos_branches, cashier_by_branch, managers, stock)

        print("Syncing final inventory levels...")
        await _sync_inventory_rows(db, stock)

        await db.commit()
        print("\n✓ Demo data generated successfully!")


if __name__ == "__main__":
    asyncio.run(seed_demo())
