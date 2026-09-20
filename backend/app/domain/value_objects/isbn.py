"""Isbn 值对象（`05-domain-model.md` §4.5）。

支持 ISBN-10 与 ISBN-13，含校验位验证；`normalize` 去掉连字符与空格。
"""

from __future__ import annotations

import re
from dataclasses import dataclass

_NON_DIGIT = re.compile(r"[^0-9Xx]")


@dataclass(frozen=True, slots=True)
class Isbn:
    value: str

    def __post_init__(self) -> None:
        normalized = self.normalize(self.value)
        if not self.is_valid(normalized):
            raise ValueError(f"非法 ISBN: {self.value!r}")
        object.__setattr__(self, "value", normalized)

    # ---- 规范化与校验 -----------------------------------------------------

    @staticmethod
    def normalize(value: str) -> str:
        """去掉连字符/空格并转大写。"""
        if value is None:
            return ""
        return _NON_DIGIT.sub("", str(value)).upper()

    @staticmethod
    def is_valid(value: str) -> bool:
        candidate = Isbn.normalize(value)
        if len(candidate) == 10:
            return Isbn._is_valid_isbn10(candidate)
        if len(candidate) == 13:
            return Isbn._is_valid_isbn13(candidate)
        return False

    @staticmethod
    def _is_valid_isbn10(candidate: str) -> bool:
        if not re.match(r"^\d{9}[\dX]$", candidate):
            return False
        total = 0
        for index, char in enumerate(candidate):
            digit = 10 if char == "X" else int(char)
            total += (10 - index) * digit
        return total % 11 == 0

    @staticmethod
    def _is_valid_isbn13(candidate: str) -> bool:
        if not candidate.isdigit():
            return False
        total = 0
        for index, char in enumerate(candidate):
            weight = 1 if index % 2 == 0 else 3
            total += weight * int(char)
        return total % 10 == 0

    def __str__(self) -> str:
        return self.value
