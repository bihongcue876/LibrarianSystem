"""规则表 ORM 模型：`borrow_policies`、`fine_rules`
（`13-database-design.md` §4.10、§4.11）。

规则**必须存库**（BR-049）：代码中严禁出现 `if reader_type == 'UNDERGRADUATE': return 5`
这类分支。种子数据由 `scripts/init_db.py` 写入。
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.db.base import Base, EnumText, MoneyType

READER_TYPES = "'COLLEGE','UNDERGRADUATE','GRADUATE','DOCTOR','TEACHER'"
ITEM_TYPES = "'CHINESE_BOOK','FOREIGN_BOOK','CHINESE_MAGAZINE','FOREIGN_MAGAZINE','THESIS'"


class BorrowPolicyModel(Base):
    """`borrow_policies` 表。`UNIQUE(reader_type)` 保证每种类型恰有一条规则。"""

    __tablename__ = "borrow_policies"

    policy_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    reader_type: Mapped[str] = mapped_column(EnumText(20), nullable=False, unique=True)
    max_borrow_count: Mapped[int] = mapped_column(Integer, nullable=False)
    borrow_days: Mapped[int] = mapped_column(Integer, nullable=False)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    updated_by: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("system_admins.admin_id"), nullable=True
    )

    __table_args__ = (
        CheckConstraint(f"reader_type IN ({READER_TYPES})", name="ck_borrow_policies_reader_type"),
        CheckConstraint("max_borrow_count > 0", name="ck_borrow_policies_max_count"),
        CheckConstraint("borrow_days > 0", name="ck_borrow_policies_borrow_days"),
    )


class FineRuleModel(Base):
    """`fine_rules` 表。"""

    __tablename__ = "fine_rules"

    rule_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    item_type: Mapped[str] = mapped_column(EnumText(20), nullable=False, unique=True)
    daily_price: Mapped[object] = mapped_column(MoneyType, nullable=False)
    grace_days: Mapped[int] = mapped_column(Integer, nullable=False)
    max_amount: Mapped[object] = mapped_column(MoneyType, nullable=False)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    updated_by: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("system_admins.admin_id"), nullable=True
    )

    __table_args__ = (
        CheckConstraint(f"item_type IN ({ITEM_TYPES})", name="ck_fine_rules_item_type"),
        CheckConstraint("grace_days >= 0", name="ck_fine_rules_grace_days"),
    )
