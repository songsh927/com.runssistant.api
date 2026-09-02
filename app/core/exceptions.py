from dataclasses import dataclass, field
from typing import Any


@dataclass
class AppException(Exception):
    code: str
    message: str
    http_status: int
    details: dict[str, Any] = field(default_factory=dict)


class NotFound(AppException):
    def __init__(self, message: str = "리소스를 찾을 수 없습니다.") -> None:
        super().__init__(code="NOT_FOUND", message=message, http_status=404)


class Conflict(AppException):
    def __init__(self, message: str = "이미 존재하는 데이터입니다.") -> None:
        super().__init__(code="CONFLICT", message=message, http_status=409)


class Unauthorized(AppException):
    def __init__(self, message: str = "인증에 실패했습니다.") -> None:
        super().__init__(code="UNAUTHORIZED", message=message, http_status=401)


class ValidationError(AppException):
    def __init__(self, message: str = "입력값이 올바르지 않습니다.") -> None:
        super().__init__(code="VALIDATION_ERROR", message=message, http_status=400)


class CoachingUnavailable(AppException):
    def __init__(self, message: str = "AI 코칭 서비스를 사용할 수 없습니다.") -> None:
        super().__init__(code="COACHING_UNAVAILABLE", message=message, http_status=503)
