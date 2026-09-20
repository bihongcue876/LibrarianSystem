"""馆藏副本状态枚举（`05-domain-model.md` §4.7）。共 6 态（BR-032）。"""

from __future__ import annotations

from enum import Enum


class ItemStatus(str, Enum):
    AVAILABLE = "AVAILABLE"    # 可借
    BORROWED = "BORROWED"      # 已借出
    RESERVED = "RESERVED"      # 已为预约者预留
    LOST = "LOST"              # 丢失
    DAMAGED = "DAMAGED"        # 破损
    REMOVED = "REMOVED"        # 已下架/软删除

    @property
    def is_borrowable(self) -> bool:
        """仅 `AVAILABLE` 可借出（BR-033）。"""
        return self is ItemStatus.AVAILABLE
