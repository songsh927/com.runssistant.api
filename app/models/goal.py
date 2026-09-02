from datetime import date
from decimal import Decimal

import sqlalchemy as sa
from sqlalchemy import Date, ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, uuid_pk


class Goal(TimestampMixin, Base):
    __tablename__ = "goals"
    __table_args__ = (
        sa.CheckConstraint("goal_type IN ('weekly_volume','race')", name="ck_goals_goal_type"),
        sa.CheckConstraint("status IN ('active','completed','abandoned')", name="ck_goals_status"),
        sa.CheckConstraint(
            "weekly_km_target IS NULL OR weekly_km_target > 0",
            name="ck_goals_weekly_km_positive",
        ),
        sa.Index(
            "idx_goals_user_active",
            "user_id",
            postgresql_where=sa.text("status = 'active'"),
        ),
    )

    id: Mapped[str] = uuid_pk()
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    goal_type: Mapped[str] = mapped_column(String(20), nullable=False)
    weekly_km_target: Mapped[Decimal | None] = mapped_column(Numeric(5, 1), nullable=True)
    race_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    race_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    race_target_time: Mapped[int | None] = mapped_column(Integer, nullable=True)
    race_distance_km: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    status: Mapped[str] = mapped_column(String(20), server_default="active", nullable=False)
