from datetime import datetime
from fastapi import HTTPException


class AppException(HTTPException):
    def __init__(self, status_code: int, detail: str, code: str):
        super().__init__(status_code=status_code, detail={"detail": detail, "code": code})


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
            "ACCOUNT_LOCKED"
        )


class InactiveUserException(AppException):
    def __init__(self):
        super().__init__(403, "Akaunti imezimwa. Wasiliana na msimamizi.", "ACCOUNT_INACTIVE")


class InsufficientPermissionException(AppException):
    def __init__(self, detail: str = "Huna ruhusa ya kufanya hivi"):
        super().__init__(403, detail, "INSUFFICIENT_PERMISSION")


class NotFoundException(AppException):
    def __init__(self, resource: str = "Rekodi"):
        super().__init__(404, f"{resource} haipatikani", "NOT_FOUND")


class InsufficientStockException(AppException):
    def __init__(self, product: str, available: int, requested: int):
        super().__init__(
            400,
            f"Hisa haitoshi kwa '{product}'. Zinapatikana: {available}, Ulizohitaji: {requested}",
            "INSUFFICIENT_STOCK"
        )


class DuplicateException(AppException):
    def __init__(self, field: str = "Rekodi"):
        super().__init__(409, f"{field} tayari ipo", "DUPLICATE")


class TransferPermissionException(AppException):
    def __init__(self):
        super().__init__(
            403,
            "Huna ruhusa ya kuhamisha bidhaa kati ya Sehemu za Mauzo. Wasiliana na Meneja Mkuu.",
            "TRANSFER_NOT_ALLOWED"
        )


class ValidationException(AppException):
    def __init__(self, detail: str):
        super().__init__(400, detail, "VALIDATION_ERROR")
