"""Customer master records (spec §6.2, §6.5). Customers are shared by all
branches and never deleted; only admins change credit terms or status."""
import re
from decimal import Decimal
from uuid import UUID

from sqlalchemy import exists, func, or_, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundException, debt_error
from app.models.customer import Customer
from app.models.sale import Sale
from app.schemas.customer import (
    CustomerCreate, CustomerCreditUpdate, CustomerDetailResponse, CustomerResponse,
    CustomerUpdate,
)
from app.services import debt_insights_service, ledger_service

# Roles that see all branches (and so all-branch credit figures).
GLOBAL_ROLES = ("super_admin", "admin", "general_manager")
from app.services.audit_service import audit_service

_PROFILE_FIELDS = ("name", "phone", "email", "address", "customer_type", "tin", "notes")


def money(v: Decimal | int | str) -> str:
    return f"{Decimal(v):.2f}"


async def _audit(db, user, action, customer: Customer, details: dict):
    await audit_service.log(
        db, action=action, category="sales",
        username=user.username, user_role=user.role.name, user_id=user.id,
        branch_id=user.branch_id, entity_type="customer", entity_id=str(customer.id),
        details={"customer_no": customer.customer_no, "name": customer.name, **details},
    )


async def get_or_404(db: AsyncSession, customer_id: UUID) -> Customer:
    c = await db.get(Customer, customer_id)
    if not c:
        raise NotFoundException("Mteja", "customer")
    return c


async def _phone_taken(db: AsyncSession, phone: str, exclude_id: UUID | None = None) -> bool:
    q = select(Customer.id).where(Customer.phone == phone)
    if exclude_id:
        q = q.where(Customer.id != exclude_id)
    return (await db.execute(q)).first() is not None


async def _flush_unique_phone(db: AsyncSession) -> None:
    try:
        async with db.begin_nested():
            await db.flush()
    except IntegrityError:
        raise debt_error("CUSTOMER_PHONE_DUPLICATE")


async def create(db: AsyncSession, data: CustomerCreate, user) -> Customer:
    if await _phone_taken(db, data.phone):
        raise debt_error("CUSTOMER_PHONE_DUPLICATE")
    seq = (await db.execute(text("SELECT nextval('seq_customer_number')"))).scalar()
    c = Customer(customer_no=f"CUS-{seq:04d}", created_by=user.id, **data.model_dump())
    db.add(c)
    await _flush_unique_phone(db)
    await db.commit()
    await db.refresh(c)
    await _audit(db, user, "CUSTOMER_CREATED", c, {"phone": c.phone})
    return c


async def update(db: AsyncSession, customer_id: UUID, data: CustomerUpdate, user) -> Customer:
    c = await get_or_404(db, customer_id)
    changes = {}
    for field in _PROFILE_FIELDS:
        new = getattr(data, field)
        if field not in data.model_fields_set or new is None:
            continue
        old = getattr(c, field)
        if old != new:
            changes[field] = {"old": old, "new": new}
            setattr(c, field, new)
    if "phone" in changes and await _phone_taken(db, c.phone, exclude_id=c.id):
        raise debt_error("CUSTOMER_PHONE_DUPLICATE")
    if not changes:
        return c
    await _flush_unique_phone(db)
    await db.commit()
    await db.refresh(c)
    await _audit(db, user, "CUSTOMER_UPDATED", c, {"changes": changes})
    return c


async def update_credit(
    db: AsyncSession, customer_id: UUID, data: CustomerCreditUpdate, user
) -> Customer:
    c = await ledger_service.lock_customer(db, customer_id)
    exposure = await ledger_service.customer_balance(db, c.id)
    details = {
        "old_limit": money(c.credit_limit), "new_limit": money(data.credit_limit),
        "old_days": c.credit_days, "new_days": data.credit_days,
        "old_status": c.status, "new_status": data.status,
        "current_exposure": money(exposure),
        "reason": data.reason,
    }
    c.credit_limit = data.credit_limit
    c.credit_days = data.credit_days
    c.status = data.status
    await db.commit()
    await db.refresh(c)
    await _audit(db, user, "CUSTOMER_CREDIT_CHANGED", c, details)
    return c


def _search_filter(q: str):
    like = f"%{q}%"
    conds = [Customer.name.ilike(like), Customer.customer_no.ilike(like)]
    digits = re.sub(r"\D", "", q)
    if digits.startswith("0"):
        digits = digits[1:]
    if len(digits) >= 3:
        conds.append(Customer.phone.like(f"%{digits}%"))
    conds.append(
        exists().where(Sale.customer_id == Customer.id, Sale.transaction_no == q.strip().upper())
    )
    return or_(*conds)


async def search(
    db: AsyncSession, q: str | None, status: str | None, page: int, per_page: int
) -> tuple[list[Customer], int]:
    base = select(Customer)
    if q and q.strip():
        base = base.where(_search_filter(q.strip()))
    if status:
        base = base.where(Customer.status == status)
    total = (await db.execute(select(func.count()).select_from(base.subquery()))).scalar()
    rows = (
        await db.execute(
            base.order_by(Customer.name, Customer.customer_no)
            .offset((page - 1) * per_page).limit(per_page)
        )
    ).scalars().all()
    return list(rows), total


async def get_detail(
    db: AsyncSession, customer_id: UUID, branch_scope: UUID | None, user=None
) -> CustomerDetailResponse:
    """`branch_scope` comes from `branch_context` (cashier → own branch;
    global roles → requested branch or None for all). Balance and overdue
    are scoped; available credit is always the all-branch figure (D4)."""
    c = await get_or_404(db, customer_id)
    return CustomerDetailResponse(
        customer=CustomerResponse.model_validate(c),
        summary=await ledger_service.summary(db, c, branch_scope),
        risk=await debt_insights_service.risk_details(
            db, c, branch_scope,
            # The all-branch % used would reveal other branches' debt once
            # over the limit; branch-scoped roles see only available credit
            # (D4). Decided by role: the admin may also pick one branch.
            show_limit_use=user is None or user.role.name in GLOBAL_ROLES,
        ),
    )
