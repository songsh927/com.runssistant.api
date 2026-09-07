"""AI(LLM) 엔드포인트 전용 Redis 고정 윈도우 rate limiting.

LLM 호출은 비용과 지연이 크므로 **LLM을 태우는 경로만** 한도를 건다.
그 외 경로는 카운터를 올리지도, Redis를 조회하지도 않고 그대로 통과한다.

키 체계:
  rl:ai:{client_ip}:{window_start}   (분 단위 윈도우)

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

# LLM을 호출하는 엔드포인트 — app/graph의 코칭 그래프를 태우는 경로만 등록한다.
# 새 AI 엔드포인트를 추가하면 여기에도 반드시 넣을 것.
_AI_PATHS: frozenset[str] = frozenset({"/coach/recommend"})
_WINDOW_SEC = 60


def _is_ai_path(path: str) -> bool:
    return path in _AI_PATHS


def _get_key(request: Request) -> str:
    client_ip = (request.client.host if request.client else "unknown") or "unknown"
    window = int(time.time()) // _WINDOW_SEC
    return f"rl:ai:{client_ip}:{window}"


async def rate_limit_middleware(request: Request, call_next):  # type: ignore[no-untyped-def]
    if not _is_ai_path(request.url.path):
        return await call_next(request)

    key = _get_key(request)
    try:
        count = await redis_client.incr(key)
        if count == 1:
            await redis_client.expire(key, _WINDOW_SEC)
        if count > settings.RATE_LIMIT_AI:
            logger.warning("rate_limited", path=request.url.path, count=count)
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
