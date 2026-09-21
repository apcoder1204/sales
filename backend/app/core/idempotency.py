"""Idempotency-Key support for write endpoints prone to client-side retry
or double-submit (a network timeout with an ambiguous outcome, a double-tap
before a button's disabled state takes effect). A client that resends the
same key gets back the exact response of the first successful call instead
of repeating the underlying action — most importantly, instead of creating
a second sale (and deducting stock twice) for what was really one checkout.

Scoped deliberately to the read-then-write pattern, not a full reserve/poll
protocol: a genuine millisecond-exact double-submit race (vanishingly rare
for a human clicking a button, as opposed to an automated retry after a
completed request) may still let both requests through. That's an accepted
tradeoff for the complexity it avoids — see Phase 2 idempotency notes.
"""
from uuid import UUID
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from app.repositories.idempotency_repo import idempotency_repo

MAX_KEY_LENGTH = 100


async def get_cached_response(
    db: AsyncSession, user_id: UUID, endpoint: str, key: str | None
) -> tuple[int, dict] | None:
    if not key or len(key) > MAX_KEY_LENGTH:
        return None
    existing = await idempotency_repo.get(db, user_id, endpoint, key)
    if not existing:
        return None
    return existing.response_status, existing.response_body


async def store_response(
    db: AsyncSession, user_id: UUID, endpoint: str, key: str | None,
    status_code: int, response_body: dict,
) -> None:
    if not key or len(key) > MAX_KEY_LENGTH:
        return
    try:
        await idempotency_repo.create(db, {
            "user_id": user_id, "endpoint": endpoint, "key": key,
            "response_status": status_code, "response_body": response_body,
        })
        await db.commit()
    except IntegrityError:
        # Lost a genuine concurrent race for this exact key — the other
        # request's own copy of the response already serves this purpose;
        # the action itself already succeeded, so this is not an error for
        # the caller of this function.
        await db.rollback()
