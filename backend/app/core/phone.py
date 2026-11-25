"""Phone number normalisation shared by WhatsApp settings and customers."""
import re

from app.core.exceptions import ValidationException

_SEPARATORS = re.compile(r"[\s\-()]")


def normalize_phone(raw: str) -> str:
    """Normalise a phone number to international digits without '+'
    (e.g. '0712 345 678' -> '255712345678'). Local Tanzanian numbers
    (leading single 0, 10 digits) get the 255 country code."""
    s = _SEPARATORS.sub("", raw or "")
    if s.startswith("+"):
        s = s[1:]
    elif s.startswith("00"):
        s = s[2:]
    elif s.startswith("0") and len(s) == 10:
        s = "255" + s[1:]
    if not s.isdigit() or not (10 <= len(s) <= 15):
        raise ValidationException("Namba ya simu si sahihi", code="INVALID_PHONE")
    return s
