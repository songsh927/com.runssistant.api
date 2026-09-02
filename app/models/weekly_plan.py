from datetime import date
from decimal import Decimal
from typing import Any

import sqlalchemy as sa
from sqlalchemy import Date, ForeignKey, Numeric
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, uuid_pk


class WeeklyPlan(TimestampMixin, Base):
    __tablename__ = "weekly_plans"
    __table_args__ = (sa.UniqueConstraint("user_id", "week_start", name="unique_user_week"),)

    id: Mapped[str] = uuid_pk()
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    goal_id: Mapped[str | None] = mapped_column(ForeignKey("goals.id"), nullable=True)
    week_start: Mapped[date] = mapped_column(Date, nullable=False)
    planned_sessions: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")
    )
    total_planned_km: Mapped[Decimal | None] = mapped_column(Numeric(5, 1), nullable=True)
    adjustments_log: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")
    )
