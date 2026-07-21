from fastapi import Request
from slowapi import Limiter
from slowapi.util import get_remote_address
from app.config import settings


def get_client_ip(request: Request) -> str:
    """Nginx sits in front of the backend in every deployment, so
    request.client.host (what get_remote_address reads) is always Nginx's own
    proxy connection — real client IPs only survive in X-Forwarded-For. Without
    this, every real user behind the proxy shares one rate-limit bucket.

    Nginx's $proxy_add_x_forwarded_for *appends* its own view of the client IP
    to whatever X-Forwarded-For the client sent — so the last entry is the one
    Nginx itself observed (trustworthy); anything before it came from the
    client and is trivially spoofable. Take the last entry, not the first."""
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[-1].strip()
    return get_remote_address(request)


limiter = Limiter(
    key_func=get_client_ip,
    storage_uri=settings.REDIS_URL or "memory://",
    default_limits=[settings.RATE_LIMIT_DEFAULT],
    key_prefix="dukani_rl",
)
