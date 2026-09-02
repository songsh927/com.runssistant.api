from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.api import auth, coach, goals, plans, runs, stats
from app.core.exceptions import AppException

app = FastAPI(title="Running Coach API", version="0.1.0")


@app.exception_handler(AppException)
async def app_exception_handler(_: Request, exc: AppException) -> JSONResponse:
    return JSONResponse(
        status_code=exc.http_status,
        content={"error": {"code": exc.code, "message": exc.message, "details": exc.details}},
    )


app.include_router(auth.router)
app.include_router(runs.router)
app.include_router(stats.router)
app.include_router(goals.router)
app.include_router(plans.router)
app.include_router(coach.router)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
