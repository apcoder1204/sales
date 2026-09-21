"""Business-date/timezone helpers, shared by anything that needs to reason
about "today" in the branch's local calendar rather than the UTC calendar
Sale.created_at (and every other timestamp column) is stored in.

Centralized here (rather than left on daily_closing_service, which is where
this logic originally lived) so low-level repositories can use it too
without importing a service module and creating a circular import.
"""
from datetime import date, datetime, time, timezone
from zoneinfo import ZoneInfo
from app.config import settings

UTC = timezone.utc
_TZ = ZoneInfo(settings.DEFAULT_TIMEZONE)


def utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def business_date_today() -> date:
    return datetime.now(_TZ).date()


def business_date_for(naive_utc_dt: datetime) -> date:
    """Convert a naive-UTC timestamp (as stored on Sale.created_at) to the
    local business date it falls on."""
    return naive_utc_dt.replace(tzinfo=UTC).astimezone(_TZ).date()


def utc_range_for_business_date(business_date: date) -> tuple[datetime, datetime]:
    """Sale.created_at is stored as naive UTC, but a "business day" is defined
    in the branch's local timezone — convert the local midnight-to-midnight
    window to naive UTC bounds so late-night local sales aren't attributed to
    the wrong calendar day."""
    start_local = datetime.combine(business_date, time.min, tzinfo=_TZ)
    end_local = datetime.combine(business_date, time.max, tzinfo=_TZ)
    return (
        start_local.astimezone(UTC).replace(tzinfo=None),
        end_local.astimezone(UTC).replace(tzinfo=None),
    )
