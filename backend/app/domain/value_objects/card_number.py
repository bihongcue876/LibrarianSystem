"""CardNumber 值对象（`05-domain-model.md` §3.2）。

格式：`CARD` + 4 位年份 + 6 位序号，如 `CARD2026000001`（BR-004）。
把格式知识收敛在值对象内部，避免校验逻辑散落各处。
"""

from __future__ import annotations

import re
from dataclasses import dataclass

CARD_NUMBER_PATTERN = re.compile(r"^CARD(\d{4})(\d{6})$")


@dataclass(frozen=True, slots=True)
class CardNumber:
    value: str

    def __post_init__(self) -> None:
        if not self.is_valid(self.value):
            raise ValueError(f"非法借阅证号: {self.value!r}")

    # ---- 构造 -------------------------------------------------------------

    @classmethod
    def generate(cls, year: int, sequence: int) -> "CardNumber":
        """生成证号。`sequence` 为当年内递增序号，从 1 开始。"""
        if not 1000 <= year <= 9999:
            raise ValueError(f"非法年份: {year}")
        if not 1 <= sequence <= 999999:
            raise ValueError(f"序号超范围: {sequence}")
        return cls(f"CARD{year:04d}{sequence:06d}")

    @classmethod
    def parse(cls, value: str) -> "CardNumber":
        return cls(value)

    # ---- 校验 -------------------------------------------------------------

    @staticmethod
    def is_valid(value: str) -> bool:
        return bool(isinstance(value, str) and CARD_NUMBER_PATTERN.match(value))

    @property
    def year(self) -> int:
        match = CARD_NUMBER_PATTERN.match(self.value)
        assert match is not None  # __post_init__ 已保证
        return int(match.group(1))

    @property
    def sequence(self) -> int:
        match = CARD_NUMBER_PATTERN.match(self.value)
        assert match is not None
        return int(match.group(2))

    def __str__(self) -> str:
        return self.value
