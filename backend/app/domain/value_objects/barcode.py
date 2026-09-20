"""Barcode 值对象（`05-domain-model.md` §4.4）。

格式：`BC` + 8 位序号，如 `BC00000001`。
"""

from __future__ import annotations

import re
from dataclasses import dataclass

BARCODE_PATTERN = re.compile(r"^BC(\d{8})$")


@dataclass(frozen=True, slots=True)
class Barcode:
    value: str

    def __post_init__(self) -> None:
        if not self.is_valid(self.value):
            raise ValueError(f"非法馆藏条码: {self.value!r}")

    @classmethod
    def generate(cls, sequence: int) -> "Barcode":
        if not 1 <= sequence <= 99999999:
            raise ValueError(f"序号超范围: {sequence}")
        return cls(f"BC{sequence:08d}")

    @classmethod
    def parse(cls, value: str) -> "Barcode":
        return cls(value)

    @staticmethod
    def is_valid(value: str) -> bool:
        return bool(isinstance(value, str) and BARCODE_PATTERN.match(value))

    @property
    def sequence(self) -> int:
        match = BARCODE_PATTERN.match(self.value)
        assert match is not None
        return int(match.group(1))

    def __str__(self) -> str:
        return self.value
