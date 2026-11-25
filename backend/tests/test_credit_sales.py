"""Checkout with split / partial / credit payments (spec §6.3 Checkout)."""
import uuid
from datetime import timedelta
from decimal import Decimal

import pytest
from sqlalchemy import func, select

from app.core.business_time import business_date_today
from app.models.customer_ledger import CustomerLedgerEntry
from app.models.inventory import Inventory
from app.models.payment import Payment
from app.models.sale import Sale
from app.services import ledger_service
from tests.conftest import (
    auth_headers, make_branch, make_customer, make_inventory, make_product, make_user,
)


async def _setup(db, price=Decimal("80000"), cost=Decimal("50000"), qty=100):
    branch = await make_branch(db)
    cashier = await make_user(db, "cashier", branch=branch)
    product = await make_product(db)
    product.selling_price = price
    product.cost_price = cost
    await db.flush()
    await make_inventory(db, product, branch, quantity=qty)
    return branch, cashier, product


async def _sell(client, cashier, branch, product, qty=5, payments=None, customer=None, **extra):
    body = {"branch_id": str(branch.id), "items": [{"product_id": str(product.id), "quantity": qty}]}
    if payments is not None:
        body["payments"] = payments
    if customer is not None:
        body["customer_id"] = str(customer.id)
    body.update(extra)
    return await client.post("/api/v1/sales", json=body, headers=auth_headers(cashier))


async def _ledger_rows(db, customer):
    return (await db.execute(
        select(CustomerLedgerEntry).where(CustomerLedgerEntry.customer_id == customer.id)
        .order_by(CustomerLedgerEntry.created_at, CustomerLedgerEntry.entry_type.desc())
    )).scalars().all()


@pytest.mark.asyncio
async def test_full_cash_sale_walk_in(client, db_session):
    branch, cashier, product = await _setup(db_session)
    r = await _sell(client, cashier, branch, product, payments=[{"method": "cash", "amount": "400000"}])
    assert r.status_code == 201, r.text
    sale = r.json()["sale"]
    assert sale["payment_status"] == "PAID"
    assert sale["outstanding"] == "0.00"
    assert sale["paid"] == "400000.00"
    assert sale["payment_method"] == "cash"
    assert len(sale["payments"]) == 1
    assert sale["customer"] is None
    n = (await db_session.execute(select(func.count()).select_from(CustomerLedgerEntry).where(
        CustomerLedgerEntry.source_id == uuid.UUID(sale["id"])
    ))).scalar()
    assert n == 0
    row =(await db_session.execute(select(Sale).where(Sale.id == uuid.UUID(sale["id"])))).scalar_one()
    assert row.payment_method is None


@pytest.mark.asyncio
async def test_split_payment_sale(client, db_session):
    branch, cashier, product = await _setup(db_session)
    r = await _sell(client, cashier, branch, product, payments=[
        {"method": "cash", "amount": "200000"},
        {"method": "mobile_money", "amount": "200000", "reference": "MP1"},
    ])
    assert r.status_code == 201, r.text
    sale = r.json()["sale"]
    assert len(sale["payments"]) == 2
    assert sale["payment_method"] == "mixed"
    assert sale["payment_status"] == "PAID"


@pytest.mark.asyncio
async def test_partial_payment_creates_debt(client, db_session):
    branch, cashier, product = await _setup(db_session)
    customer = await make_customer(db_session, credit_limit=Decimal("2000000"), credit_days=30)
    r = await _sell(client, cashier, branch, product,
                    payments=[{"method": "cash", "amount": "150000"}], customer=customer)
    assert r.status_code == 201, r.text
    sale = r.json()["sale"]
    assert sale["outstanding"] == "250000.00"
    assert sale["payment_status"] == "PARTIALLY_PAID"
    assert sale["due_date"] == (business_date_today() + timedelta(days=30)).isoformat()
    assert sale["customer"]["id"] == str(customer.id)
    rows = await _ledger_rows(db_session, customer)
    assert sorted((r.entry_type, r.debit, r.credit) for r in rows) == [
        ("payment", Decimal("0.00"), Decimal("150000.00")),
        ("sale", Decimal("400000.00"), Decimal("0.00")),
    ]
    assert await ledger_service.customer_balance(db_session, customer.id) == Decimal("250000")


@pytest.mark.asyncio
async def test_full_credit_sale(client, db_session):
    branch, cashier, product = await _setup(db_session)
    customer = await make_customer(db_session, credit_limit=Decimal("2000000"))
    r = await _sell(client, cashier, branch, product, payments=[], customer=customer)
    assert r.status_code == 201, r.text
    sale = r.json()["sale"]
    assert sale["outstanding"] == sale["total_amount"]
    assert sale["payment_status"] == "UNPAID"
    assert sale["payment_method"] == "credit"
    assert sale["payments"] == []


@pytest.mark.asyncio
async def test_credit_without_customer_rejected(client, db_session):
    branch, cashier, product = await _setup(db_session)
    r = await _sell(client, cashier, branch, product, payments=[{"method": "cash", "amount": "150000"}])
    assert r.status_code == 400
    assert r.json()["code"] == "CREDIT_REQUIRES_CUSTOMER"
    inv = (await db_session.execute(select(Inventory).where(
        Inventory.product_id == product.id, Inventory.branch_id == branch.id
    ))).scalar_one()
    await db_session.refresh(inv)
    assert inv.quantity == 100


@pytest.mark.asyncio
async def test_no_payment_no_customer_rejected(client, db_session):
    branch, cashier, product = await _setup(db_session)
    r = await _sell(client, cashier, branch, product, payments=[])
    assert r.status_code == 400
    assert r.json()["code"] == "CREDIT_REQUIRES_CUSTOMER"


@pytest.mark.asyncio
async def test_credit_limit_zero_rejected(client, db_session):
    branch, cashier, product = await _setup(db_session)
    customer = await make_customer(db_session)
    r = await _sell(client, cashier, branch, product, payments=[], customer=customer)
    assert r.status_code == 400
    assert r.json()["code"] == "CREDIT_NOT_ALLOWED"


@pytest.mark.asyncio
async def test_inactive_customer_credit_rejected(client, db_session):
    branch, cashier, product = await _setup(db_session)
    customer = await make_customer(db_session, credit_limit=Decimal("2000000"), status="inactive")
    r = await _sell(client, cashier, branch, product, payments=[], customer=customer)
    assert r.status_code == 400
    assert r.json()["code"] == "CUSTOMER_INACTIVE"


@pytest.mark.asyncio
async def test_inactive_customer_on_paid_sale_allowed(client, db_session):
    branch, cashier, product = await _setup(db_session)
    customer = await make_customer(db_session, status="inactive")
    r = await _sell(client, cashier, branch, product,
                    payments=[{"method": "cash", "amount": "400000"}], customer=customer)
    assert r.status_code == 201, r.text
    assert r.json()["sale"]["customer"]["id"] == str(customer.id)


@pytest.mark.asyncio
async def test_unknown_customer_404(client, db_session):
    branch, cashier, product = await _setup(db_session)
    r = await client.post("/api/v1/sales", json={
        "branch_id": str(branch.id), "customer_id": str(uuid.uuid4()),
        "items": [{"product_id": str(product.id), "quantity": 1}],
        "payments": [{"method": "cash", "amount": "80000"}],
    }, headers=auth_headers(cashier))
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_credit_limit_exceeded(client, db_session):
    branch, cashier, product = await _setup(db_session, price=Decimal("500000"), cost=Decimal("300000"))
    admin = await make_user(db_session, "admin")
    customer = await make_customer(db_session, credit_limit=Decimal("2000000"))
    await ledger_service.post(
        db_session, customer_id=customer.id, branch_id=branch.id, entry_type="opening_balance",
        source_type="opening_balance", source_id=uuid.uuid4(),
        business_date=business_date_today(), description="old", created_by=admin.id,
        debit=Decimal("1700000"),
    )
    before = (await db_session.execute(select(func.count()).select_from(Sale))).scalar()
    r = await _sell(client, cashier, branch, product, qty=1, payments=[], customer=customer)
    assert r.status_code == 422, r.text
    body = r.json()
    assert body["code"] == "CREDIT_LIMIT_EXCEEDED"
    assert body["params"] == {
        "limit": "2000000", "current": "1700000", "requested": "500000", "available": "300000",
    }
    after = (await db_session.execute(select(func.count()).select_from(Sale))).scalar()
    assert after == before


@pytest.mark.asyncio
async def test_overpayment_rejected(client, db_session):
    branch, cashier, product = await _setup(db_session)
    r = await _sell(client, cashier, branch, product, payments=[{"method": "cash", "amount": "500000"}])
    assert r.status_code == 400
    assert r.json()["code"] == "PAYMENT_EXCEEDS_TOTAL"


@pytest.mark.asyncio
async def test_legacy_payload_still_sells(client, db_session):
    branch, cashier, product = await _setup(db_session)
    r = await _sell(client, cashier, branch, product, payment_method="cash")
    assert r.status_code == 201, r.text
    sale = r.json()["sale"]
    assert sale["payment_method"] == "cash"
    assert sale["payment_status"] == "PAID"
    pays = (await db_session.execute(select(Payment).where(Payment.branch_id == branch.id))).scalars().all()
    assert len(pays) == 1 and pays[0].amount == Decimal("400000") and pays[0].kind == "sale"


@pytest.mark.asyncio
async def test_legacy_mobile_money_requires_reference(client, db_session):
    branch, cashier, product = await _setup(db_session)
    r = await _sell(client, cashier, branch, product, payment_method="mobile_money")
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_both_payload_styles_rejected(client, db_session):
    branch, cashier, product = await _setup(db_session)
    r = await _sell(client, cashier, branch, product,
                    payments=[{"method": "cash", "amount": "400000"}], payment_method="cash")
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_payment_line_mobile_money_requires_reference(client, db_session):
    branch, cashier, product = await _setup(db_session)
    r = await _sell(client, cashier, branch, product,
                    payments=[{"method": "mobile_money", "amount": "400000"}])
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_receipt_shows_balance_and_due_date(client, db_session):
    branch, cashier, product = await _setup(db_session)
    customer = await make_customer(db_session, credit_limit=Decimal("2000000"), credit_days=14)
    r = await _sell(client, cashier, branch, product,
                    payments=[{"method": "cash", "amount": "150000"}], customer=customer)
    assert r.status_code == 201, r.text
    sale_id = r.json()["sale"]["id"]
    rec = await client.get(f"/api/v1/sales/{sale_id}/receipt", headers=auth_headers(cashier))
    assert rec.status_code == 200
    body = rec.json()
    assert body["balance"] is not None and "250,000" in body["balance"]
    assert body["due_date"] == (business_date_today() + timedelta(days=14)).strftime("%d/%m/%Y")
    assert len(body["payments"]) == 1
    assert body["customer_name"] == customer.name
    assert r.json()["receipt"]["balance"] == body["balance"]


@pytest.mark.asyncio
async def test_cashier_cannot_sell_on_credit_at_other_branch(client, db_session):
    branch, cashier, product = await _setup(db_session)
    other = await make_branch(db_session)
    await make_inventory(db_session, product, other, quantity=10)
    customer = await make_customer(db_session, credit_limit=Decimal("2000000"))
    r = await _sell(client, cashier, other, product, qty=1, payments=[], customer=customer)
    assert r.status_code == 403
    assert r.json()["code"] == "BRANCH_WRITE_RESTRICTED"


@pytest.mark.asyncio
async def test_sales_list_filter_by_method_uses_payments(client, db_session):
    branch, cashier, product = await _setup(db_session)
    admin = await make_user(db_session, "admin")
    r = await _sell(client, cashier, branch, product, payments=[
        {"method": "cash", "amount": "100000"},
        {"method": "mobile_money", "amount": "300000", "reference": "MP9"},
    ])
    sale_id = r.json()["sale"]["id"]
    for method, present in (("cash", True), ("mobile_money", True), ("bank_transfer", False)):
        res = await client.get("/api/v1/sales", params={"branch_id": str(branch.id), "payment_method": method},
                               headers=auth_headers(admin))
        assert res.status_code == 200, res.text
        ids = [s["id"] for s in res.json()["items"]]
        assert (sale_id in ids) is present, method


@pytest.mark.asyncio
async def test_receipt_time_is_local_business_time(client, db_session):
    from datetime import datetime
    from zoneinfo import ZoneInfo
    from app.config import settings

    branch, cashier, product = await _setup(db_session)
    r = await _sell(client, cashier, branch, product, qty=1, payments=[{"method": "cash", "amount": "80000"}])
    assert r.status_code == 201, r.text
    created = datetime.fromisoformat(r.json()["sale"]["created_at"])
    if created.tzinfo is None:
        from datetime import timezone
        created = created.replace(tzinfo=timezone.utc)
    expected = created.astimezone(ZoneInfo(settings.DEFAULT_TIMEZONE)).strftime("%d/%m/%Y %H:%M")
    assert r.json()["receipt"]["date"] == expected
    rec = await client.get(f"/api/v1/sales/{r.json()['sale']['id']}/receipt", headers=auth_headers(cashier))
    assert rec.json()["date"] == expected
