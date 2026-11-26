from datetime import datetime
from fastapi import HTTPException


class AppException(HTTPException):
    """Every response body is {"detail": <Swahili fallback text>, "code":
    <stable machine-readable identifier>, "params": <optional structured
    data for dynamic content>}. `detail` remains a real, readable Swahili
    sentence (used if the frontend has no translation for `code` yet, and
    for anything reading raw API responses directly), but `code` (+
    `params` for messages with interpolated values) is what the frontend
    actually uses to pick a message in the active UI language — see
    frontend/src/constants/translations/{en,sw}.js `makosa.msimbo`."""
    def __init__(self, status_code: int, detail: str, code: str, params: dict | None = None):
        payload = {"detail": detail, "code": code}
        if params:
            payload["params"] = params
        super().__init__(status_code=status_code, detail=payload)


class InvalidTokenException(AppException):
    def __init__(self):
        super().__init__(401, "Tokeni si sahihi", "INVALID_TOKEN")


class TokenExpiredException(AppException):
    def __init__(self):
        super().__init__(401, "Tokeni imeisha muda", "TOKEN_EXPIRED")


class InvalidCredentialsException(AppException):
    def __init__(self):
        super().__init__(401, "Jina la mtumiaji au neno la siri si sahihi", "INVALID_CREDENTIALS")


class AccountLockedException(AppException):
    def __init__(self, locked_until: datetime):
        super().__init__(
            423,
            f"Akaunti imefungwa hadi {locked_until.strftime('%H:%M')}. Jaribu tena baadaye.",
            "ACCOUNT_LOCKED",
            params={"locked_until": locked_until.isoformat()},
        )


class InactiveUserException(AppException):
    def __init__(self):
        super().__init__(403, "Akaunti imezimwa. Wasiliana na msimamizi.", "ACCOUNT_INACTIVE")


class InsufficientPermissionException(AppException):
    def __init__(self, detail: str = "Huna ruhusa ya kufanya hivi", code: str = "INSUFFICIENT_PERMISSION"):
        super().__init__(403, detail, code)


class NotFoundException(AppException):
    # resource_key is the stable lookup key the frontend's terminology
    # dictionary (SW.rasilimali) uses to translate `resource` — a small,
    # fixed vocabulary (see call sites), not free text.
    def __init__(self, resource: str = "Rekodi", resource_key: str = "record"):
        super().__init__(404, f"{resource} haipatikani", "NOT_FOUND", params={"resource": resource_key})


class InsufficientStockException(AppException):
    def __init__(self, product: str, available: int, requested: int):
        super().__init__(
            400,
            f"Hisa haitoshi kwa '{product}'. Zinapatikana: {available}, Ulizohitaji: {requested}",
            "INSUFFICIENT_STOCK",
            params={"product": product, "available": available, "requested": requested},
        )


class DuplicateException(AppException):
    def __init__(self, field: str = "Rekodi", code: str = "DUPLICATE"):
        super().__init__(409, f"{field} tayari ipo", code)


class TransferPermissionException(AppException):
    def __init__(self):
        super().__init__(
            403,
            "Huna ruhusa ya kuhamisha bidhaa kati ya Sehemu za Mauzo. Wasiliana na Meneja Mkuu.",
            "TRANSFER_NOT_ALLOWED"
        )


class ValidationException(AppException):
    def __init__(self, detail: str, code: str = "VALIDATION_ERROR"):
        super().__init__(400, detail, code)


class WhatsAppException(AppException):
    """WhatsApp report-sharing failures — each carries its own stable code
    (WHATSAPP_*) so the frontend can show a specific message."""
    def __init__(self, status_code: int, detail: str, code: str, params: dict | None = None):
        super().__init__(status_code, detail, code, params)


class WhatsAppReceiverLockedException(WhatsAppException):
    def __init__(self):
        super().__init__(
            403,
            "Namba ya kupokea imewekwa na seva na haiwezi kubadilishwa hapa",
            "WHATSAPP_RECEIVER_LOCKED",
        )


def whatsapp_error(code: str, params: dict | None = None) -> WhatsAppException:
    """Build the WhatsApp error for `code` with its fixed status + Swahili text."""
    status, detail = _WHATSAPP_ERRORS[code]
    if params:
        detail = detail.format(**params)
    return WhatsAppException(status, detail, code, params)


_WHATSAPP_ERRORS: dict[str, tuple[int, str]] = {
    "WHATSAPP_DISABLED": (503, "Kutuma kwa WhatsApp hakujawashwa"),
    "WHATSAPP_NO_RECEIVER": (400, "Namba ya kupokea ripoti haijawekwa"),
    "WHATSAPP_NOT_CONNECTED": (503, "WhatsApp haijaunganishwa"),
    "WHATSAPP_SEND_FAILED": (502, "Imeshindwa kutuma kwa WhatsApp"),
    "WHATSAPP_TIMEOUT": (504, "Haijathibitishwa — angalia WhatsApp kabla ya kutuma tena"),
    "WHATSAPP_DAILY_CAP": (429, "Kikomo cha ripoti {cap} kwa siku kimefikiwa"),
    "WHATSAPP_DUPLICATE": (409, "Ripoti hii imeshatumwa"),
    "WHATSAPP_INVALID_PDF": (400, "Faili si PDF sahihi"),
    "WHATSAPP_PDF_TOO_LARGE": (413, "Faili ni kubwa mno"),
}


class DebtException(AppException):
    """Customer accounts / debt errors — each code has a fixed status and a
    Swahili fallback message (frontend translates by `code`)."""
    def __init__(self, status_code: int, detail: str, code: str, params: dict | None = None):
        super().__init__(status_code, detail, code, params)
        self.code = code
        self.params = params or {}


def debt_error(code: str, params: dict | None = None) -> DebtException:
    status, detail = _DEBT_ERRORS[code]
    if params:
        detail = detail.format(**params)
    return DebtException(status, detail, code, params)


_DEBT_ERRORS: dict[str, tuple[int, str]] = {
    "CUSTOMER_PHONE_DUPLICATE": (409, "Mteja mwenye namba hii ya simu tayari yupo"),
    "CUSTOMER_INACTIVE": (400, "Mteja huyu amezimwa"),
    "CREDIT_REQUIRES_CUSTOMER": (400, "Chagua mteja aliyesajiliwa ili kuuza kwa mkopo"),
    "CREDIT_NOT_ALLOWED": (400, "Mteja huyu hajaruhusiwa kukopa"),
    "CREDIT_LIMIT_EXCEEDED": (
        422,
        "Kikomo cha mkopo kimezidi. Kikomo: {limit}, Deni la sasa: {current}, "
        "Unaloomba: {requested}, Kilichobaki: {available}",
    ),
    "PAYMENT_EXCEEDS_TOTAL": (400, "Kiasi kilicholipwa kinazidi jumla ya mauzo"),
    "PAYMENT_EXCEEDS_DEBT": (400, "Kiasi kinazidi deni lililopo ({owed})"),
    "ALLOCATION_INVALID": (400, "Mgawanyo wa malipo si sahihi"),
    "ALLOCATION_MISMATCH": (400, "Jumla ya mgawanyo hailingani na kiasi cha malipo"),
    "SALE_HAS_DEBT_PAYMENTS": (
        400, "Muamala huu una malipo ya deni. Batilisha malipo hayo kwanza"
    ),
    "PAYMENT_ALREADY_REVERSED": (400, "Malipo haya tayari yamebatilishwa"),
    "SALE_PAYMENT_USE_VOID": (
        400, "Malipo ya wakati wa mauzo hubatilishwa kwa kubatilisha muamala"
    ),
    "OPENING_BALANCE_DUPLICATE": (409, "Deni hili la zamani tayari limeingizwa"),
    "OPENING_BALANCE_NOT_PENDING": (400, "Deni hili la zamani limeshaamuliwa"),
    "DATE_RANGE_INVALID": (422, "Tarehe ya mwanzo haiwezi kuwa baada ya tarehe ya mwisho"),
    "RECON_SCOPE_INVALID": (422, "Chagua kipimo sahihi cha upatanisho (tawi, mteja, muamala au malipo yaliyopo)"),
    "EXCEPTION_STILL_PRESENT": (
        409, "Tofauti hii bado ipo. Fanya marekebisho kwanza, kisha uiweke kuwa imetatuliwa"
    ),
    "EXCEPTION_CLOSED": (422, "Tofauti hii tayari imefungwa (imetatuliwa au imepuuzwa)"),
    "EXCEPTION_TRANSITION_INVALID": (422, "Hali ya tofauti haiwezi kubadilishwa hivyo"),
    "OPENING_BALANCE_NOT_APPROVED": (400, "Ni deni la zamani lililoidhinishwa tu linaloweza kubatilishwa"),
    "OPENING_BALANCE_HAS_PAYMENTS": (
        400, "Deni hili lina malipo. Batilisha malipo hayo kwanza"
    ),
}
