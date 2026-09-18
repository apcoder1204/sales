"""Branch- and object-level authorization checks.

`app.core.dependencies.require_role(...)` only checks *role* — it has no
concept of branch or object ownership, so a route wired up with the right
role gate can still leak or mutate another branch's data if nothing here is
called too. These helpers are the single source of truth for that missing
layer; call them from the *service* layer (not just the route) so a
misconfigured or future route can't bypass them.

A client-supplied branch_id must never be trusted for a branch-scoped role
(cashier, store_keeper) — every helper below resolves or validates the
branch server-side instead of trusting the caller's input.
"""
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import (
    InsufficientPermissionException,
    NotFoundException,
    ValidationException,
)

# admin/super_admin: full global scope. general_manager: existing cross-branch
# operational scope (reports, transfer approval) — narrower category/action
# restrictions for general_manager are applied at the specific call site
# (e.g. audit log category), not here.
GLOBAL_SCOPE_ROLES = ("super_admin", "admin", "general_manager")


def is_global_scope(user) -> bool:
    return user.role.name in GLOBAL_SCOPE_ROLES


async def get_main_store_id(db: AsyncSession) -> UUID:
    """Resolve the single active main-store branch fresh from the DB
    (branch_type == 'main_store'), never from a user's possibly-stale
    branch_id — so store_keeper scope always tracks the real main store."""
    from app.repositories.inventory_repo import inventory_repo

    main_store = await inventory_repo.get_main_store(db)
    if not main_store:
        raise NotFoundException("Ghala Kuu")
    return main_store.id


async def resolve_read_branch_id(
    db: AsyncSession, user, requested_branch_id: UUID | None
) -> UUID | None:
    """The branch_id a *read* endpoint (listing/report/audit) should actually
    filter on for `user`. Ignores the client-supplied value entirely for a
    branch-scoped role; passes it through unchanged for global-scope roles
    (None means "no filter" there, by existing app convention)."""
    if user.role.name == "cashier":
        return user.branch_id
    if user.role.name == "store_keeper":
        return await get_main_store_id(db)
    return requested_branch_id


async def require_write_branch_access(
    db: AsyncSession, user, target_branch_id: UUID | None
) -> None:
    """For *mutations* that write to a specific branch (stock adjustment,
    sale creation, ...): raise 403 unless `user` may act on
    `target_branch_id`. No-op for global-scope roles."""
    if user.role.name == "cashier":
        if target_branch_id is None or str(user.branch_id) != str(target_branch_id):
            raise InsufficientPermissionException("Huwezi kufanya kazi kwa tawi lingine")
    elif user.role.name == "store_keeper":
        main_store_id = await get_main_store_id(db)
        if target_branch_id is None or str(main_store_id) != str(target_branch_id):
            raise InsufficientPermissionException("Hisa inaruhusiwa kutoka Ghala Kuu pekee")


async def get_active_branch_or_error(db: AsyncSession, branch_id: UUID | None, label: str):
    from app.models.branch import Branch

    branch = await db.get(Branch, branch_id) if branch_id else None
    if not branch:
        raise NotFoundException(label)
    if not branch.is_active:
        raise ValidationException(f"{label} halifanyi kazi kwa sasa")
    return branch


async def require_valid_branch_pair(db: AsyncSession, from_branch_id: UUID, to_branch_id: UUID):
    """Both branches must exist, be active, and differ. A DB FK/CHECK
    constraint alone can't give a clean 404/400 for this — it surfaces as a
    raw IntegrityError — so it's validated here before anything is written."""
    if str(from_branch_id) == str(to_branch_id):
        raise ValidationException("Tawi la kutoa na kupokea haliwezi kuwa sawa")
    from_branch = await get_active_branch_or_error(db, from_branch_id, "Tawi la kutoa")
    to_branch = await get_active_branch_or_error(db, to_branch_id, "Tawi la kupokea")
    return from_branch, to_branch


async def require_stock_request_branches(
    db: AsyncSession, user, from_branch_id: UUID, to_branch_id: UUID
) -> None:
    """Object-relationship authorization for *creating* a stock request:
    which branch pairs `user` is actually allowed to request stock between.

    - cashier: may only request stock delivered TO their own branch, sourced
      FROM the active main store. Cannot spoof either end.
    - store_keeper: scoped to the main store — one side of the request must
      be the main store.
    - super_admin / admin / general_manager: any valid branch pair (existing
      cross-branch operational scope), still subject to the
      existence/active/different-branch checks.
    """
    await require_valid_branch_pair(db, from_branch_id, to_branch_id)

    if user.role.name == "cashier":
        if str(to_branch_id) != str(user.branch_id):
            raise InsufficientPermissionException("Unaweza kuomba bidhaa kwa tawi lako pekee")
        main_store_id = await get_main_store_id(db)
        if str(from_branch_id) != str(main_store_id):
            raise InsufficientPermissionException("Ombi linapaswa kutoka Ghala Kuu")
    elif user.role.name == "store_keeper":
        main_store_id = await get_main_store_id(db)
        if main_store_id not in (from_branch_id, to_branch_id):
            raise InsufficientPermissionException("Ombi lazima lihusishe Ghala Kuu")


async def require_direct_transfer_branches(
    db: AsyncSession, user, from_branch_id: UUID, to_branch_id: UUID
) -> None:
    """Object-relationship authorization for a *direct* transfer
    (`POST /transfers`, no prior request). store_keeper must originate from
    the main store; admin/super_admin/general_manager keep their existing
    cross-branch capability, still subject to existence/active/different
    checks."""
    await require_valid_branch_pair(db, from_branch_id, to_branch_id)

    if user.role.name == "store_keeper":
        main_store_id = await get_main_store_id(db)
        if str(from_branch_id) != str(main_store_id):
            raise InsufficientPermissionException("Hisa inaruhusiwa kutoka Ghala Kuu pekee")
