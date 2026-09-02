from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_coach_graph, get_current_user, get_db, get_weather_service
from app.models.user import User
from app.schemas.coach import (
    CoachingSessionResponse,
    FeedbackRequest,
    RecommendRequest,
    RecommendResponse,
)
from app.services.coach_service import CoachService
from app.services.weather_service import WeatherService

router = APIRouter(prefix="/coach", tags=["coach"])
_svc = CoachService()


@router.post("/recommend", response_model=RecommendResponse)
async def recommend(
    body: RecommendRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    graph: Any = Depends(get_coach_graph),
    weather_service: WeatherService = Depends(get_weather_service),
) -> RecommendResponse:
    response = await _svc.recommend(
        db, graph, weather_service, current_user.id, current_user.location, body.rpe, body.notes
    )
    await db.commit()
    return RecommendResponse(**response)


@router.post("/feedback", response_model=CoachingSessionResponse)
async def feedback(
    body: FeedbackRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> CoachingSessionResponse:
    coaching_session = await _svc.submit_feedback(
        db, body.coaching_session_id, current_user.id, body.rating
    )
    await db.commit()
    return CoachingSessionResponse.model_validate(coaching_session)


@router.get("/history", response_model=list[CoachingSessionResponse])
async def history(
    limit: int = Query(default=10, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[CoachingSessionResponse]:
    sessions = await _svc.get_history(db, current_user.id, limit)
    return [CoachingSessionResponse.model_validate(s) for s in sessions]
