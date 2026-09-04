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


class RateLimited(AppException):
    def __init__(self, message: str = "요청 한도를 초과했습니다. 잠시 후 다시 시도하세요.") -> None:
        super().__init__(code="RATE_LIMITED", message=message, http_status=429)


class ProfileAlreadyExists(AppException):
    def __init__(
        self, message: str = "이미 온보딩이 완료되었습니다. PATCH /users/profile을 사용하세요."
    ) -> None:
        super().__init__(code="PROFILE_ALREADY_EXISTS", message=message, http_status=409)


class ProfileNotFound(AppException):
    def __init__(self, message: str = "프로필이 없습니다. 온보딩을 먼저 완료하세요.") -> None:
        super().__init__(code="PROFILE_NOT_FOUND", message=message, http_status=404)


class OnboardingRequired(AppException):
    def __init__(self, message: str = "온보딩을 먼저 완료해야 합니다.") -> None:
        super().__init__(code="ONBOARDING_REQUIRED", message=message, http_status=403)
