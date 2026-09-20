"""Money 值对象（`05-domain-model.md` §7.2）。

**核心约束：内部使用 `Decimal`，禁止 `float`。**

这是 `02-requirements.md` §7 Q-04 的解决方案——`0.20 × 3` 用 float 会得到
`0.6000000000000001`，用 Decimal 精确得到 `0.60`。

精度统一为 2 位小数（`quantize(Decimal("0.01"))`，四舍五入）。
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

CENT = Decimal("0.01")


def to_decimal(value: Decimal | int | str | float) -> Decimal:
    """把入参安全地转为 `Decimal`。

    `float` 会被**先转字符串**再转 Decimal，避免二进制浮点误差被原样带入
    （例如 `Decimal(0.2)` 会得到 `0.200000000000000011102230246251565404236316680908203125`）。
    """
    if isinstance(value, Decimal):
        return value
    if isinstance(value, float):
        return Decimal(str(value))
    return Decimal(value)


@dataclass(frozen=True, slots=True)
class Money:
    """金额值对象。不可变。"""

    amount: Decimal
    currency: str = "CNY"

    def __post_init__(self) -> None:
        object.__setattr__(self, "amount", to_decimal(self.amount).quantize(CENT, rounding=ROUND_HALF_UP))

    # ---- 构造 -------------------------------------------------------------

    @classmethod
    def zero(cls, currency: str = "CNY") -> "Money":
        return cls(Decimal("0.00"), currency)

    @classmethod
    def of(cls, value: Decimal | int | str | float, currency: str = "CNY") -> "Money":
        return cls(to_decimal(value), currency)

    @classmethod
    def parse(cls, text: str | None) -> "Money":
        """从定点小数字符串解析（数据库 TEXT 列的反序列化入口）。"""
        if text is None or text == "":
            return cls.zero()
        try:
            return cls(Decimal(text))
        except (InvalidOperation, ValueError) as exc:  # pragma: no cover - 防御性
            raise ValueError(f"非法金额: {text!r}") from exc

    # ---- 运算 -------------------------------------------------------------

    def _check_currency(self, other: "Money") -> None:
        if self.currency != other.currency:
            raise ValueError(f"币种不一致: {self.currency} vs {other.currency}")

    def add(self, other: "Money") -> "Money":
        self._check_currency(other)
        return Money(self.amount + other.amount, self.currency)

    def subtract(self, other: "Money") -> "Money":
        self._check_currency(other)
        return Money(self.amount - other.amount, self.currency)

    def multiply(self, factor: Decimal | int | str | float) -> "Money":
        return Money(self.amount * to_decimal(factor), self.currency)

    def min_with_cap(self, cap: "Money") -> "Money":
        """封顶：返回不超过 `cap` 的金额（BR-030）。"""
        self._check_currency(cap)
        return Money(min(self.amount, cap.amount), self.currency)

    # ---- 判定与比较 -------------------------------------------------------

    def is_zero(self) -> bool:
        return self.amount == Decimal("0.00")

    def is_positive(self) -> bool:
        return self.amount > Decimal("0.00")

    def __lt__(self, other: "Money") -> bool:  # type: ignore[override]
        self._check_currency(other)
        return self.amount < other.amount

    def __le__(self, other: "Money") -> bool:  # type: ignore[override]
        self._check_currency(other)
        return self.amount <= other.amount

    def __gt__(self, other: "Money") -> bool:  # type: ignore[override]
        self._check_currency(other)
        return self.amount > other.amount

    def __ge__(self, other: "Money") -> bool:  # type: ignore[override]
        self._check_currency(other)
        return self.amount >= other.amount

    # ---- 序列化 -----------------------------------------------------------

    def to_text(self) -> str:
        """数据库存储形态（TEXT，避免 REAL 精度丢失）。"""
        return str(self.amount)

    def __str__(self) -> str:  # pragma: no cover - 展示用
        return self.to_text()
