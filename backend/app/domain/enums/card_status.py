"""借阅证状态枚举（`05-domain-model.md` §3.3）。

`EXPIRED` 保留不用：借阅证不设过期时间（BR-005）。
"""

from __future__ import annotations

from enum import Enum


class CardStatus(str, Enum):
    ACTIVE = "ACTIVE"          # 有效
    SUSPENDED = "SUSPENDED"    # 挂失
    CANCELLED = "CANCELLED"    # 已注销
    EXPIRED = "EXPIRED"        # 保留不用（BR-005）

    @property
    def counts_towards_one_card_limit(self) -> bool:
        """`ACTIVE` 与 `SUSPENDED` 计入一人一证限制，`CANCELLED` 不计入（BR-003）。"""
        return self in (CardStatus.ACTIVE, CardStatus.SUSPENDED)

    @property
    def is_valid_for_borrowing(self) -> bool:
        """仅 `ACTIVE` 可借书（BR-001）。"""
        return self is CardStatus.ACTIVE
