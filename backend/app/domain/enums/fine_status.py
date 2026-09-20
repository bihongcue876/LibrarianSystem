"""罚款状态枚举（`05-domain-model.md` §7.3）。"""

from __future__ import annotations

from enum import Enum


class FineStatus(str, Enum):
    UNPAID = "UNPAID"
    PAID = "PAID"

    @property
    def blocks_borrowing(self) -> bool:
        """存在未缴罚款时禁止借书（BR-011）。"""
        return self is FineStatus.UNPAID
