"""值对象单元测试（TC-020b 前半）。

**硬约束**：本文件及整个 `tests/unit/` 目录**不得**导入
`fastapi`、`sqlalchemy`、`Session`（宪法第五条 / 包图规则 R-3）。
若领域层单测需要连数据库，即说明分层被破坏。
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from app.domain.value_objects import Barcode, CardNumber, DateRange, Isbn, Money


class TestMoney:
    """金额精度是 Q-04 的核心，必须严格验证。"""

    def test_decimal_not_float(self):
        """0.20 × 3 必须精确等于 0.60，而非 0.6000000000000001。"""
        result = Money.of("0.20").multiply(3)
        assert result.to_text() == "0.60"
        assert isinstance(result.amount, Decimal)

    def test_float_input_is_stringified(self):
        """`Money.of(0.2)` 不得把二进制浮点误差带进来。"""
        assert Money.of(0.2).to_text() == "0.20"

    def test_quantize_two_decimals(self):
        assert Money.of("1.005").to_text() == "1.01"

    def test_zero(self):
        assert Money.zero().is_zero() is True
        assert Money.zero().is_positive() is False

    def test_min_with_cap(self):
        assert Money.of("363.00").min_with_cap(Money.of("100.00")).to_text() == "100.00"
        assert Money.of("9.50").min_with_cap(Money.of("100.00")).to_text() == "9.50"

    def test_add_subtract(self):
        total = Money.of("0.20").add(Money.of("0.50"))
        assert total.to_text() == "0.70"
        assert Money.of("1.00").subtract(Money.of("0.40")).to_text() == "0.60"

    def test_parse_roundtrip(self):
        assert Money.parse("9.50").to_text() == "9.50"
        assert Money.parse(None).is_zero()

    def test_currency_mismatch_raises(self):
        with pytest.raises(ValueError):
            Money.of("1.00", "CNY").add(Money.of("1.00", "USD"))

    def test_is_immutable(self):
        original = Money.of("1.00")
        original.multiply(5)
        assert original.to_text() == "1.00"


class TestCardNumber:
    def test_generate_format(self):
        assert str(CardNumber.generate(2026, 1)) == "CARD2026000001"
        assert str(CardNumber.generate(2026, 999999)) == "CARD2026999999"

    @pytest.mark.parametrize(
        "value,expected",
        [
            ("CARD2026000001", True),
            ("CARD999", False),
            ("CARD20260000011", False),
            ("card2026000001", False),
            ("BC00000001", False),
        ],
    )
    def test_is_valid(self, value, expected):
        assert CardNumber.is_valid(value) is expected

    def test_parse_rejects_invalid(self):
        with pytest.raises(ValueError):
            CardNumber.parse("CARD999")

    def test_year_and_sequence(self):
        card_no = CardNumber.parse("CARD2026000042")
        assert card_no.year == 2026
        assert card_no.sequence == 42

    def test_generate_out_of_range(self):
        with pytest.raises(ValueError):
            CardNumber.generate(2026, 0)


class TestBarcode:
    def test_generate_format(self):
        assert str(Barcode.generate(1)) == "BC00000001"
        assert str(Barcode.generate(12345678)) == "BC12345678"

    @pytest.mark.parametrize(
        "value,expected",
        [("BC00000001", True), ("BC1", False), ("BC000000001", False), ("CARD2026000001", False)],
    )
    def test_is_valid(self, value, expected):
        assert Barcode.is_valid(value) is expected

    def test_sequence(self):
        assert Barcode.parse("BC00000042").sequence == 42


class TestIsbn:
    @pytest.mark.parametrize(
        "value,expected",
        [
            ("9780262046305", True),   # ISBN-13 合法
            ("978-0-262-04630-5", True),  # 含连字符应被规范化
            ("9780262046306", False),  # 校验位错
            ("0131103628", True),      # ISBN-10 合法
            ("0131103629", False),     # ISBN-10 校验位错
            ("12345", False),
        ],
    )
    def test_is_valid(self, value, expected):
        assert Isbn.is_valid(value) is expected

    def test_normalize_strips_separators(self):
        assert Isbn.normalize("978-0-262-04630-5") == "9780262046305"

    def test_parse_rejects_invalid(self):
        with pytest.raises(ValueError):
            Isbn("9780262046306")


class TestDateRange:
    def test_extend_returns_new_object(self):
        """`extend_days` 必须返回新对象——不可变性是续借可重放的前提。"""
        start = datetime(2026, 9, 20, tzinfo=timezone.utc)
        original = DateRange(start, start + timedelta(days=30))
        extended = original.extend_days(7)

        assert original.end == start + timedelta(days=30)
        assert extended.end == start + timedelta(days=37)
        assert extended is not original

    def test_days(self):
        start = datetime(2026, 9, 20, tzinfo=timezone.utc)
        assert DateRange(start, start + timedelta(days=60)).days() == 60

    def test_contains(self):
        start = datetime(2026, 9, 20, tzinfo=timezone.utc)
        span = DateRange(start, start + timedelta(days=30))
        assert span.contains(start + timedelta(days=10)) is True
        assert span.contains(start + timedelta(days=31)) is False

    def test_elapsed_days(self):
        start = datetime(2026, 9, 20, tzinfo=timezone.utc)
        span = DateRange(start, start + timedelta(days=10))
        assert span.elapsed_days(start + timedelta(days=13)) == 3
        assert span.elapsed_days(start + timedelta(days=8)) == -2

    def test_invalid_range_raises(self):
        start = datetime(2026, 9, 20, tzinfo=timezone.utc)
        with pytest.raises(ValueError):
            DateRange(start, start - timedelta(days=1))
