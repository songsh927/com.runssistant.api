from datetime import date, datetime
from decimal import Decimal
from typing import Any

import sqlalchemy as sa
from sqlalchemy import Computed, Date, DateTime, ForeignKey, Integer, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, uuid_pk


class Run(Base):
    __tablename__ = "runs"
    __table_args__ = (
        sa.CheckConstraint(
            "run_type IN ('easy','tempo','interval','long_run','race','recovery')",
            name="ck_runs_run_type",
        ),
        sa.CheckConstraint("rpe BETWEEN 1 AND 10", name="ck_runs_rpe"),
        sa.CheckConstraint("distance_km > 0", name="ck_runs_distance_positive"),
        sa.CheckConstraint("duration_sec > 0", name="ck_runs_duration_positive"),
        sa.Index("idx_runs_user_date", "user_id", "run_date"),
        sa.UniqueConstraint("user_id", "run_date", "created_at", name="unique_user_run_date"),
    )

    id: Mapped[str] = uuid_pk()
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    run_date: Mapped[date] = mapped_column(Date, nullable=False)
    distance_km: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    duration_sec: Mapped[int] = mapped_column(Integer, nullable=False)
    avg_pace_sec: Mapped[int | None] = mapped_column(
        Computed("(duration_sec / NULLIF(distance_km, 0))::integer", persisted=True),
    )
    run_type: Mapped[str] = mapped_column(String(20), nullable=False)
    rpe: Mapped[int | None] = mapped_column(Integer, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    weather_snapshot: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
