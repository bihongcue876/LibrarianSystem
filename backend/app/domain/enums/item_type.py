"""借出物类型枚举（`05-domain-model.md` §4.6）。"""

from __future__ import annotations

from enum import Enum


class ItemType(str, Enum):
    CHINESE_BOOK = "CHINESE_BOOK"              # 中文图书
    FOREIGN_BOOK = "FOREIGN_BOOK"              # 外文图书
    CHINESE_MAGAZINE = "CHINESE_MAGAZINE"      # 中文杂志
    FOREIGN_MAGAZINE = "FOREIGN_MAGAZINE"      # 外文杂志
    THESIS = "THESIS"                          # 论文
