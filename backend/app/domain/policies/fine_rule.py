"""FineRule 策略对象（`05-domain-model.md` §8.2、`09-design-model.md` §8.2）。

**Strategy 模式的落点**：借出物类型差异通过**查表**体现，规则存数据库、可在线维护（BR-049）。

计算公式（BR-027）：

```
计罚天数 = max(超期天数 − 宽限天数, 0)
罚款金额 = min(计罚天数 × 日单价, 单笔封顶金额)
```

**纪律要求（可机械检查）**：本文件不得出现 `0.2`、`0.5`、`0.1`、`1.0` 等规则数值。
**金额全程使用 `Money`（`Decimal`），禁止 `float`**（Q-04）。

形态说明同 `BorrowPolicy`：`06` 图 6 的字段是**每行一条规则**的持久化视角，
领域侧的策略对象是全部规则的可查询视图，因为 `calculate_fine(item_type, ...)`
需要按类型查表。
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from typing import Iterable, Mapping

from app.domain.enums import ItemType
from app.domain.exceptions import ValidationError
from app.domain.value_objects.money import Money


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(frozen=True, slots=True)
class FineRuleEntry:
    """单条罚款规则（值对象）。"""

    item_type: ItemType
    daily_price: Money
    grace_days: int
    max_amount: Money
    updated_at: datetime | None = None
    updated_by: int | None = None


class FineRule:
    """罚款规则策略。持有全部借出物类型的规则，按类型查表计算。"""

    def __init__(self, entries: Mapping[ItemType | str, FineRuleEntry] | None = None) -> None:
        self._entries: dict[ItemType, FineRuleEntry] = {}
        if entries:
            for key, entry in entries.items():
                self._entries[ItemType(key)] = entry

    # ---- 装配 ------------------------------------------------------------

    @classmethod
    def from_rows(cls, rows: Iterable[dict]) -> "FineRule":
        """从持久化行装配（供 Mapper / Repository 使用）。"""
        entries: dict[ItemType, FineRuleEntry] = {}
        for row in rows:
            item_type = ItemType(row["item_type"])
            entries[item_type] = FineRuleEntry(
                item_type=item_type,
                daily_price=Money.parse(row["daily_price"]),
                grace_days=int(row["grace_days"]),
                max_amount=Money.parse(row["max_amount"]),
                updated_at=row.get("updated_at"),
                updated_by=row.get("updated_by"),
            )
        return cls(entries)

    # ---- 计算（策略接口） ------------------------------------------------

    def calculate_fine(self, item_type: ItemType | str, overdue_days: int) -> Money:
        """计算罚款金额。`overdue_days <= 0` 时返回 0 元。"""
        entry = self._entry(item_type)
        days = self.billed_days(overdue_days, item_type)
        if days <= 0:
            return Money.zero()
        return entry.daily_price.multiply(Decimal(days)).min_with_cap(entry.max_amount)

    def billed_days(self, overdue_days: int, item_type: ItemType | str) -> int:
        """计罚天数 = 超期天数 − 宽限天数（不足宽限则为 0）。"""
        entry = self._entry(item_type)
        return max(int(overdue_days) - entry.grace_days, 0)

    def unit_price_of(self, item_type: ItemType | str) -> Money:
        """该类型的日单价（用于 `FineRecord` 快照，BR-050）。"""
        return self._entry(item_type).daily_price

    def grace_days_of(self, item_type: ItemType | str) -> int:
        return self._entry(item_type).grace_days

    def max_amount_of(self, item_type: ItemType | str) -> Money:
        return self._entry(item_type).max_amount

    def entries(self) -> list[FineRuleEntry]:
        """全部规则（供查询接口与持久化使用）。"""
        return list(self._entries.values())

    def _entry(self, item_type: ItemType | str | None) -> FineRuleEntry:
        if item_type is None:
            raise ValidationError("借出物类型缺失，无法查询罚款规则", code="ITEM_TYPE_REQUIRED")
        try:
            key = ItemType(item_type)
        except ValueError as exc:
            raise ValidationError(f"未知的借出物类型: {item_type}", code="UNKNOWN_ITEM_TYPE") from exc
        entry = self._entries.get(key)
        if entry is None:
            raise ValidationError(f"未配置借出物类型 {key.value} 的罚款规则", code="RULE_NOT_CONFIGURED")
        return entry

    # ---- 维护（BR-049） --------------------------------------------------

    def update(
        self,
        item_type: ItemType | str,
        daily_price: Money | Decimal | str | int,
        grace_days: int,
        max_amount: Money | Decimal | str | int,
        operator=None,
    ) -> FineRuleEntry:
        """在线修改罚款规则。**不追溯**已生成的罚款（BR-050）。"""
        key = ItemType(item_type)
        price = daily_price if isinstance(daily_price, Money) else Money.of(daily_price)
        cap = max_amount if isinstance(max_amount, Money) else Money.of(max_amount)
        if price.amount < Decimal("0"):
            raise ValidationError("日单价不得为负", code="INVALID_PARAMETER")
        if cap.amount < Decimal("0"):
            raise ValidationError("封顶金额不得为负", code="INVALID_PARAMETER")
        if int(grace_days) < 0:
            raise ValidationError("宽限天数不得为负", code="INVALID_PARAMETER")
        if key not in self._entries:
            raise ValidationError(f"未配置借出物类型 {key.value}", code="RULE_NOT_CONFIGURED")
        entry = FineRuleEntry(
            item_type=key,
            daily_price=price,
            grace_days=int(grace_days),
            max_amount=cap,
            updated_at=_utc_now(),
            updated_by=getattr(operator, "account_id", None) or getattr(operator, "admin_id", None),
        )
        self._entries[key] = entry
        return entry
