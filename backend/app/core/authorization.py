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

from fastapi import Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import (
    InsufficientPermissionException,
    NotFoundException,
    ValidationException,
)
from app.core.dependencies import get_current_user
from app.db.session import get_db

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
    branch-scoped role; for global-scope roles, None means "no filter" (the
    ALL-branches context) and a specific value is validated against real,
    active branches before being trusted — a global user can request any
    branch context, but not a nonexistent or inactive one."""
    if user.role.name == "cashier":
        return user.branch_id
    if user.role.name == "store_keeper":
        return await get_main_store_id(db)
    if requested_branch_id is not None:
        await get_active_branch_or_error(db, requested_branch_id, "Tawi")
    return requested_branch_id


async def branch_context(
    branch_id: UUID | None = Query(None, description="Requested branch context; ALL branches when omitted (global roles only) — ignored/overridden for branch-scoped roles"),
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UUID | None:
    """FastAPI dependency wrapper around `resolve_read_branch_id`, so a route
    gets validated, role-aware branch-context resolution for free by simply
    declaring `branch_id: UUID | None = Depends(branch_context)` instead of
    hand-rolling its own inline role check. Centralizes the "1. authenticate
    2. determine role 3. determine authorized branches 4. determine
    requested context 5. validate 6. apply filter" flow into one call site.
    """
    return await resolve_read_branch_id(db, current_user, branch_id)


async def get_authorized_branches(db: AsyncSession, user) -> list:
    """The branch list a user is allowed to see/select in a branch-context
    switcher (e.g. GET /users/branches) — never the full unfiltered table.
    Global-scope roles: every active branch. cashier: only their own.
    store_keeper: only the live main store."""
    from sqlalchemy import select
    from app.models.branch import Branch

    if user.role.name == "cashier":
        branch = await db.get(Branch, user.branch_id) if user.branch_id else None
        return [branch] if branch else []
    if user.role.name == "store_keeper":
        main_store_id = await get_main_store_id(db)
        branch = await db.get(Branch, main_store_id)
        return [branch] if branch else []
    rows = (
        await db.execute(select(Branch).where(Branch.is_active == True).order_by(Branch.name))
    ).scalars().all()
    return list(rows)


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
