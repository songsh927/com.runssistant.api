from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ProfileAlreadyExists, ProfileNotFound
from app.repositories.user_repo import UserRepository
from app.schemas.runner_profile import (
    RunnerProfileCreate,
    RunnerProfileResponse,
    RunnerProfileUpdate,
)

_repo = UserRepository()


class ProfileService:
    async def create_profile(
        self, session: AsyncSession, user_id: str, data: RunnerProfileCreate
    ) -> RunnerProfileResponse:
        user = await _repo.get(session, user_id)
        if user is None or user.onboarding_completed:
            raise ProfileAlreadyExists()

        profile_dict = data.model_dump(mode="json")
        await _repo.update(
            session,
            user,
            {
                "runner_profile": profile_dict,
                "onboarding_completed": True,
            },
        )
        return RunnerProfileResponse(**profile_dict, onboarding_completed=True)

    async def get_profile(self, session: AsyncSession, user_id: str) -> RunnerProfileResponse:
        user = await _repo.get(session, user_id)
        if user is None or not user.runner_profile:
            raise ProfileNotFound()
        return RunnerProfileResponse(
            **user.runner_profile, onboarding_completed=user.onboarding_completed
        )

    async def update_profile(
        self, session: AsyncSession, user_id: str, data: RunnerProfileUpdate
    ) -> RunnerProfileResponse:
        user = await _repo.get(session, user_id)
        if user is None or not user.runner_profile:
            raise ProfileNotFound()

        current = dict(user.runner_profile)
        update_dict = data.model_dump(mode="json", exclude_none=True)
        merged = {**current, **update_dict}

        await _repo.update(session, user, {"runner_profile": merged})
        return RunnerProfileResponse(**merged, onboarding_completed=user.onboarding_completed)
