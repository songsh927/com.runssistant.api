from datetime import datetime
from typing import Any

import sqlalchemy as sa
from sqlalchemy import DateTime, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, uuid_pk


class CoachingSession(Base):
    __tablename__ = "coaching_sessions"
    __table_args__ = (
        sa.CheckConstraint("user_feedback BETWEEN 1 AND 5", name="ck_coaching_sessions_feedback"),
        sa.Index("idx_coaching_user_date", "user_id", sa.text("created_at DESC")),
    )

    id: Mapped[str] = uuid_pk()
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    context_snapshot: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    constraints: Mapped[list[dict[str, Any]] | None] = mapped_column(JSONB, nullable=True)
    recommendation: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    model_used: Mapped[str | None] = mapped_column(String(100), nullable=True)
    user_feedback: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
