"""`reservations` ORM 模型（`13-database-design.md` §4.8）。"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.db.base import Base, EnumText

RESERVATION_STATUSES = "'ACTIVE','READY','EXPIRED','CANCELLED'"


class ReservationModel(Base):
    """`reservations` 表。指向**题录**（非副本）。"""

    __tablename__ = "reservations"

    reservation_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    reader_id: Mapped[int] = mapped_column(Integer, ForeignKey("readers.reader_id"), nullable=False)
    title_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("book_titles.title_id"), nullable=False
    )
    status: Mapped[str] = mapped_column(EnumText(20), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)  # 决定排队顺序（BR-021）
    ready_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    expired_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    __table_args__ = (
        CheckConstraint(f"status IN ({RESERVATION_STATUSES})", name="ck_reservations_status"),
        CheckConstraint("ready_at IS NULL OR ready_at >= created_at", name="ck_reservations_ready"),
        CheckConstraint(
            "expired_at IS NULL OR expired_at >= created_at", name="ck_reservations_expired"
        ),
        # 同一读者对同一题录不得有多个有效预约（BR-023）
        Index(
            "uq_reservations_active_reader_title",
            "reader_id",
            "title_id",
            unique=True,
            sqlite_where=text("status IN ('ACTIVE','READY')"),
        ),
        Index("idx_reservations_title_status_created", "title_id", "status", "created_at"),
    )
