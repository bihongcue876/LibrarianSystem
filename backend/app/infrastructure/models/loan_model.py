"""`loans` ORM 模型（`13-database-design.md` §4.7）。

**`status` 只存两态**（`BORROWED` / `RETURNED`）——`OVERDUE` 是派生状态，
持久化三态会造成"无人负责的状态陈旧"。
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.db.base import Base, EnumText


class LoanModel(Base):
    """`loans` 表。"""

    __tablename__ = "loans"

    loan_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    reader_id: Mapped[int] = mapped_column(Integer, ForeignKey("readers.reader_id"), nullable=False)
    item_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("library_items.item_id"), nullable=False
    )
    borrowed_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    due_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)  # 借出时快照（BR-050）
    returned_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    status: Mapped[str] = mapped_column(EnumText(20), nullable=False)
    librarian_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("librarians.librarian_id"), nullable=True
    )  # 可空：系统管理员代行流通业务时无合法 librarian_id（见 13 §4.7）
    renew_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())

    __table_args__ = (
        CheckConstraint("status IN ('BORROWED','RETURNED')", name="ck_loans_status"),
        CheckConstraint("renew_count BETWEEN 0 AND 2", name="ck_loans_renew_count"),
        CheckConstraint(
            "returned_at IS NULL OR returned_at >= borrowed_at", name="ck_loans_returned_after"
        ),
        CheckConstraint("due_at > borrowed_at", name="ck_loans_due_after_borrowed"),
        Index("idx_loans_reader_status", "reader_id", "status"),
        Index("idx_loans_item_status", "item_id", "status"),
        Index("idx_loans_overdue", "status", "due_at"),
    )
