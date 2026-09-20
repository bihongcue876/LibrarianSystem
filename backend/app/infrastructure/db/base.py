"""Declarative Base 与自定义列类型。

**`MoneyType` 的由来（关键设计，见 `13-database-design.md` §1.3）**：
SQLite 没有原生 DECIMAL，SQLAlchemy 的 `Numeric` 在其上会降级为 REAL，
重新引入 `02-requirements.md` Q-04 的浮点精度问题（`0.20 × 3 = 0.6000000000000001`）。
因此金额列**以 TEXT 存储定点小数**，读写时与 `Decimal` 互转。
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from sqlalchemy import String, Text
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.types import TypeDecorator

from app.domain.value_objects.money import Money


class Base(DeclarativeBase):
    """全部 ORM 模型的声明式基类。"""


class MoneyType(TypeDecorator):
    """金额列类型：底层 TEXT，Python 侧 `Money` / `Decimal`。

    代价（已披露）：数据库层**无法对金额做数值比较**
    （`'10.00' < '2.00'` 按字典序成立），非负校验须放在应用层。
    """

    impl = Text
    cache_ok = True

    def process_bind_param(self, value: Any, dialect) -> str | None:
        if value is None:
            return None
        if isinstance(value, Money):
            return value.to_text()
        if isinstance(value, Decimal):
            return str(value.quantize(Decimal("0.01")))
        return str(Decimal(str(value)).quantize(Decimal("0.01")))

    def process_result_value(self, value: Any, dialect) -> Money | None:
        if value is None:
            return None
        return Money.parse(str(value))


class EnumText(TypeDecorator):
    """枚举列：底层 VARCHAR，Python 侧 `str` 枚举。

    比原生 `Enum` 类型更宽松（不生成数据库级 ENUM），
    取值域由 CHECK 约束与领域枚举共同保证。
    """

    impl = String
    cache_ok = True

    def __init__(self, length: int = 20) -> None:
        super().__init__(length)

    def process_bind_param(self, value: Any, dialect) -> str | None:
        if value is None:
            return None
        return value.value if hasattr(value, "value") else str(value)

    def process_result_value(self, value: Any, dialect) -> str | None:
        return value


__all__ = ["Base", "EnumText", "MoneyType"]
