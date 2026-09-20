"""DateRange 值对象（`05-domain-model.md` §5.2）。

**不可变**：`extend_days()` 返回**新对象**而非修改自身——
这让续借操作天然可重放、可测试。
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta


@dataclass(frozen=True, slots=True)
class DateRange:
    start: datetime
    end: datetime

    def __post_init__(self) -> None:
        if self.end < self.start:
            raise ValueError("DateRange.end 不得早于 start")

    def contains(self, moment: datetime) -> bool:
        return self.start <= moment <= self.end

    def days(self) -> int:
        return (self.end - self.start).days

    def extend_days(self, days: int) -> "DateRange":
        """返回延长后的**新** `DateRange`，原对象不变。"""
        return DateRange(self.start, self.end + timedelta(days=days))

    def elapsed_days(self, moment: datetime) -> int:
        """自 `end` 起超出的天数；未超出返回负数。"""
        return (moment - self.end).days
