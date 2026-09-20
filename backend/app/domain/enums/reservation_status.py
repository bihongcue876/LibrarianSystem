"""预约状态枚举（`05-domain-model.md` §6.2）。共 4 态。"""

from __future__ import annotations

from enum import Enum


class ReservationStatus(str, Enum):
    ACTIVE = "ACTIVE"        # 排队等待中
    READY = "READY"          # 已到书，待借取
    EXPIRED = "EXPIRED"      # 已失效
    CANCELLED = "CANCELLED"  # 已取消

    @property
    def is_effective(self) -> bool:
        """有效预约（`ACTIVE`/`READY`）占用 1 个借阅额度（BR-026）。"""
        return self in (ReservationStatus.ACTIVE, ReservationStatus.READY)

    @property
    def is_cancellable(self) -> bool:
        """`ACTIVE` 与 `READY` 均可由读者取消（BR-025a）。"""
        return self.is_effective
