"""`fine_records` ORM 模型（`13-database-design.md` §4.9）。

`operator_id` **不建外键**（决策：单列 + `operator_role` 消歧）——
收费人可能来自 `librarians` 或 `system_admins` 两张表。
"""

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
)
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.db.base import Base, EnumText, MoneyType


class FineRecordModel(Base):
    """`fine_records` 表。一条借阅记录最多产生一条罚款（`loan_id` UNIQUE）。"""

    __tablename__ = "fine_records"

    fine_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    loan_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("loans.loan_id"), nullable=False, unique=True
    )
    reader_id: Mapped[int] = mapped_column(Integer, ForeignKey("readers.reader_id"), nullable=False)
    amount: Mapped[object] = mapped_column(MoneyType, nullable=False)
    overdue_days: Mapped[int] = mapped_column(Integer, nullable=False)
    billed_days: Mapped[int] = mapped_column(Integer, nullable=False)
    unit_price: Mapped[object] = mapped_column(MoneyType, nullable=False)  # 快照（BR-050）
    status: Mapped[str] = mapped_column(EnumText(20), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
    paid_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    operator_id: Mapped[int | None] = mapped_column(Integer, nullable=True)  # 无 FK，见 13 §4.9
    operator_role: Mapped[str | None] = mapped_column(String(20), nullable=True)

    __table_args__ = (
        CheckConstraint("status IN ('UNPAID','PAID')", name="ck_fine_records_status"),
        CheckConstraint("overdue_days >= 0", name="ck_fine_records_overdue_days"),
        CheckConstraint("billed_days >= 0", name="ck_fine_records_billed_days"),
        CheckConstraint("billed_days <= overdue_days", name="ck_fine_records_billed_le_overdue"),
        CheckConstraint(
            "(status = 'PAID') = (paid_at IS NOT NULL)", name="ck_fine_records_paid_consistent"
        ),
        CheckConstraint(
            "operator_role IS NULL OR operator_role IN ('LIBRARIAN','SYSTEM_ADMIN')",
            name="ck_fine_records_operator_role",
        ),
        CheckConstraint(
            "operator_id IS NULL OR operator_role IS NOT NULL",
            name="ck_fine_records_operator_role_required",
        ),
        Index("idx_fine_records_reader_status", "reader_id", "status"),
    )
