"""`borrow_cards` ORM 模型（`13-database-design.md` §4.4）。"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.db.base import Base, EnumText

CARD_STATUSES = "'ACTIVE','SUSPENDED','CANCELLED','EXPIRED'"


class BorrowCardModel(Base):
    """`borrow_cards` 表。"""

    __tablename__ = "borrow_cards"

    card_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    card_no: Mapped[str] = mapped_column(String(14), nullable=False, unique=True)
    reader_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("readers.reader_id"), nullable=False
    )
    status: Mapped[str] = mapped_column(EnumText(20), nullable=False)
    issued_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
    issued_by: Mapped[int] = mapped_column(
        Integer, ForeignKey("system_admins.admin_id"), nullable=False
    )
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    expired_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)  # 保留不用（BR-005）

    __table_args__ = (
        CheckConstraint(f"status IN ({CARD_STATUSES})", name="ck_borrow_cards_status"),
        CheckConstraint(
            "length(card_no) = 14 AND card_no LIKE 'CARD%'", name="ck_borrow_cards_card_no"
        ),
        # 一名读者最多一张有效证（BR-003）：部分唯一索引，CANCELLED 不计入
        Index(
            "uq_borrow_cards_active_reader",
            "reader_id",
            unique=True,
            sqlite_where=text("status IN ('ACTIVE','SUSPENDED')"),
        ),
    )
