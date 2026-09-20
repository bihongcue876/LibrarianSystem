"""借阅状态枚举（`05-domain-model.md` §5.3）。

`OVERDUE` 是**派生状态**——由 `due_at` 与当前时刻实时判定，
持久化层只存 `BORROWED` / `RETURNED` 两态（见 `13-database-design.md` 的 CHECK 约束）。
领域层保留它以便业务表达与测试断言。
"""

from __future__ import annotations

from enum import Enum


class LoanStatus(str, Enum):
    BORROWED = "BORROWED"
    OVERDUE = "OVERDUE"      # 派生，不落库
    RETURNED = "RETURNED"

    @property
    def is_persistable(self) -> bool:
        """`OVERDUE` 不可持久化。"""
        return self is not LoanStatus.OVERDUE

    @property
    def is_open(self) -> bool:
        """未归还（占用借阅额度）。"""
        return self in (LoanStatus.BORROWED, LoanStatus.OVERDUE)
