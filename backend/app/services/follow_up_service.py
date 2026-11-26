"""Debt-collection follow-up notes (brief §16). Writing one never touches
payments, allocations, the ledger or any balance."""
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.authorization import get_active_branch_or_error, require_write_branch_access
from app.core.exceptions import NotFoundException, ValidationException
from app.models.customer import Customer
from app.models.follow_up import CustomerFollowUp
from app.schemas.debt import FollowUpCreate, FollowUpOut
from app.services.audit_service import audit_service


def to_out(f: CustomerFollowUp) -> FollowUpOut:
    return FollowUpOut(
        id=f.id, branch_id=f.branch_id, branch_name=f.branch.name, contact_date=f.contact_date,
        method=f.method, note=f.note, expected_payment_date=f.expected_payment_date,
        responsible_user_name=f.responsible.full_name, created_at=f.created_at,
    )


async def _branch_id(db: AsyncSession, data: FollowUpCreate, user) -> UUID:
    if user.role.name == "cashier":
        if data.branch_id is not None:
            await require_write_branch_access(db, user, data.branch_id)
        return user.branch_id
    if data.branch_id is None:
        raise ValidationException("Chagua tawi", "BRANCH_REQUIRED")
    branch = await get_active_branch_or_error(db, data.branch_id, "Tawi")
    if branch.branch_type != "pos_point":
        raise ValidationException("Chagua Sehemu ya Mauzo", "BRANCH_NOT_POS")
    return branch.id


async def create(db: AsyncSession, customer_id: UUID, data: FollowUpCreate, user) -> CustomerFollowUp:
    if not await db.get(Customer, customer_id):
        raise NotFoundException("Mteja", "customer")
    branch_id = await _branch_id(db, data, user)
    f = CustomerFollowUp(
        customer_id=customer_id, branch_id=branch_id, contact_date=data.contact_date,
        method=data.method, note=data.note.strip(), expected_payment_date=data.expected_payment_date,
        responsible_user_id=user.id, created_by=user.id,
    )
    db.add(f)
    await db.commit()
    await db.refresh(f)
    await audit_service.log(
        db, action="FOLLOW_UP_ADDED", category="sales",
        user_id=user.id, username=user.username, user_role=user.role.name, branch_id=branch_id,
        entity_type="customer", entity_id=str(customer_id),
        details={"follow_up_id": str(f.id), "method": f.method,
                 "expected_payment_date": f.expected_payment_date.isoformat() if f.expected_payment_date else None},
    )
    return f


async def list_(db: AsyncSession, customer_id: UUID, branch_id: UUID | None) -> list[CustomerFollowUp]:
    q = select(CustomerFollowUp).where(CustomerFollowUp.customer_id == customer_id)
    if branch_id is not None:
        q = q.where(CustomerFollowUp.branch_id == branch_id)
    q = q.order_by(CustomerFollowUp.contact_date.desc(), CustomerFollowUp.created_at.desc())
    return list((await db.execute(q)).scalars().all())
