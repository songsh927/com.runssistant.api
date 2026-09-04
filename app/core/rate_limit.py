"""Redis 고정 윈도우 rate limiting.

키 체계:
  rl:ip:{client_ip}:{window_start}   (분 단위 윈도우)

Redis 장애 시 fail-open (요청 통과 + 경고 로그):
  가용성을 rate limit 정확성보다 우선한다 — Redis 다운으로 서비스 전체가 멈추면 안 된다.
"""

import time

import structlog
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.config import settings
from app.core.redis import redis_client

logger = structlog.get_logger()

# 경로 프리픽스별 분당 한도 재정의 테이블
_PATH_LIMITS: dict[str, int] = {
    "/coach/recommend": settings.RATE_LIMIT_COACH,
}
_WINDOW_SEC = 60


def _get_limit(path: str) -> int:
    for prefix, limit in _PATH_LIMITS.items():
        if path.startswith(prefix):
            return limit
    return settings.RATE_LIMIT_DEFAULT


def _get_key(request: Request) -> str:
    client_ip = (request.client.host if request.client else "unknown") or "unknown"
    window = int(time.time()) // _WINDOW_SEC
    return f"rl:ip:{client_ip}:{window}"


async def rate_limit_middleware(request: Request, call_next):  # type: ignore[no-untyped-def]
    limit = _get_limit(request.url.path)
    key = _get_key(request)
    try:
        count = await redis_client.incr(key)
        if count == 1:
            await redis_client.expire(key, _WINDOW_SEC)
        if count > limit:
            # 미들웨어에서 raise한 예외는 FastAPI 핸들러를 거치지 않으므로 직접 반환
            return JSONResponse(
                status_code=429,
                content={
                    "error": {
                        "code": "RATE_LIMITED",
                        "message": "요청 한도를 초과했습니다. 잠시 후 다시 시도하세요.",
                        "details": {},
                    }
                },
            )
    except Exception as exc:
        logger.warning("rate_limit_redis_error", error=str(exc), path=request.url.path)

    return await call_next(request)


def register_rate_limit(app: FastAPI) -> None:
    app.middleware("http")(rate_limit_middleware)
