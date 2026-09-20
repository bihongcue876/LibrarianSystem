"""罚款规则策略单元测试（TC-020、TC-021，TASK-008 验收标准）。

公式（BR-027）：`计罚天数 = max(超期天数 − 宽限天数, 0)`；`金额 = min(计罚天数 × 单价, 封顶)`。
"""

from __future__ import annotations

import pytest

from app.domain.exceptions import ValidationError
from app.domain.policies import FineRule

RULE_ROWS = [
    {"item_type": "CHINESE_BOOK", "daily_price": "0.20", "grace_days": 2, "max_amount": "100.00"},
    {"item_type": "FOREIGN_BOOK", "daily_price": "0.50", "grace_days": 2, "max_amount": "100.00"},
    {"item_type": "CHINESE_MAGAZINE", "daily_price": "0.10", "grace_days": 2, "max_amount": "100.00"},
    {"item_type": "FOREIGN_MAGAZINE", "daily_price": "0.20", "grace_days": 2, "max_amount": "100.00"},
    {"item_type": "THESIS", "daily_price": "1.00", "grace_days": 2, "max_amount": "100.00"},
]


@pytest.fixture()
def rule() -> FineRule:
    return FineRule.from_rows(RULE_ROWS)


class TestGracePeriod:
    """TC-020：宽限期（默认 2 天）内不罚。"""

    @pytest.mark.parametrize(
        "overdue_days,billed,amount",
        [(0, 0, "0.00"), (1, 0, "0.00"), (2, 0, "0.00"), (3, 1, "0.50"), (5, 3, "1.50")],
    )
    def test_foreign_book(self, rule, overdue_days, billed, amount):
        assert rule.billed_days(overdue_days, "FOREIGN_BOOK") == billed
        assert rule.calculate_fine("FOREIGN_BOOK", overdue_days).to_text() == amount


class TestUnitPrice:
    @pytest.mark.parametrize(
        "item_type,amount",
        [
            ("CHINESE_BOOK", "0.60"),      # 计罚 3 天 × 0.20
            ("FOREIGN_BOOK", "1.50"),      # 计罚 3 天 × 0.50
            ("CHINESE_MAGAZINE", "0.30"),  # 计罚 3 天 × 0.10
            ("FOREIGN_MAGAZINE", "0.60"),  # 计罚 3 天 × 0.20
            ("THESIS", "3.00"),            # 计罚 3 天 × 1.00
        ],
    )
    def test_five_types(self, rule, item_type, amount):
        assert rule.calculate_fine(item_type, 5).to_text() == amount


class TestCap:
    """TC-021：单笔封顶 100 元（BR-030），且各笔独立不合并封顶。"""

    def test_cap_applies(self, rule):
        assert rule.calculate_fine("THESIS", 365).to_text() == "100.00"

    def test_cap_not_reached(self, rule):
        assert rule.calculate_fine("THESIS", 30).to_text() == "28.00"  # 28 天 × 1.00

    def test_amount_uses_decimal(self, rule):
        from decimal import Decimal

        amount = rule.calculate_fine("CHINESE_BOOK", 5)  # 3 天 × 0.20
        assert amount.amount == Decimal("0.60")
        assert amount.to_text() == "0.60"


class TestRealWorldExample:
    """与 `11-sequence-return-book.md` §3 的计算示例表对齐。"""

    @pytest.mark.parametrize(
        "overdue_days,expected",
        [(1, "0.00"), (2, "0.00"), (3, "0.50"), (21, "9.50"), (365, "100.00")],
    )
    def test_matches_sequence_diagram_examples(self, rule, overdue_days, expected):
        assert rule.calculate_fine("FOREIGN_BOOK", overdue_days).to_text() == expected


class TestMaintenance:
    def test_update_takes_effect(self, rule):
        rule.update("FOREIGN_BOOK", "0.80", 3, "200.00", operator=None)
        assert rule.unit_price_of("FOREIGN_BOOK").to_text() == "0.80"
        assert rule.grace_days_of("FOREIGN_BOOK") == 3
        assert rule.max_amount_of("FOREIGN_BOOK").to_text() == "200.00"
        # 超期 5 天 → 计罚 2 天 × 0.80 = 1.60
        assert rule.calculate_fine("FOREIGN_BOOK", 5).to_text() == "1.60"

    @pytest.mark.parametrize(
        "price,grace,cap",
        [("-0.10", 2, "100.00"), ("0.50", -1, "100.00"), ("0.50", 2, "-1.00")],
    )
    def test_update_rejects_negatives(self, rule, price, grace, cap):
        with pytest.raises(ValidationError):
            rule.update("FOREIGN_BOOK", price, grace, cap)

    def test_unknown_item_type(self, rule):
        with pytest.raises(ValidationError):
            rule.calculate_fine("DVD", 5)

    def test_entries_count(self, rule):
        assert len(rule.entries()) == 5
