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
