"""BorrowPolicy 策略对象（`05-domain-model.md` §8.1、`09-design-model.md` §12）。

**Strategy 模式的落点**：读者类型差异通过**查表**体现，而非在代码中写
`if reader_type == ...` 分支。规则存数据库、可在线维护（BR-049）。

**纪律要求（可机械检查）**：本文件**不得出现** `== 5`、`== 10`、`== 15`、`== 20`、
`30`、`60`、`90` 等规则数值——它们属于**数据**，不是**代码**。

形态说明：`06-domain-class-diagram.md` 图 6 按"每行一条规则"给出字段
（`policyId`/`readerType`/`maxBorrowCount`/`borrowDays`），那是**持久化视角**；
领域侧的策略对象是这些规则的**整体可查询视图**（一个 `BorrowPolicy` 持有全部 5 条规则），
因为 `limit_for(reader_type)` 这个签名本身就要求它能按类型查表。
每行的 ORM 映射由 `infrastructure/models/policy_model.py` 承担。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Iterable, Mapping

from app.domain.enums import ReaderType
from app.domain.exceptions import ValidationError


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(frozen=True, slots=True)
class BorrowRule:
    """单条借阅规则（值对象）。"""

    reader_type: ReaderType
    max_borrow_count: int
    borrow_days: int
    updated_at: datetime | None = None
    updated_by: int | None = None


class BorrowPolicy:
    """借阅规则策略。持有全部读者类型的规则，按类型查表返回。"""

    def __init__(self, rules: Mapping[ReaderType | str, BorrowRule] | None = None) -> None:
        self._rules: dict[ReaderType, BorrowRule] = {}
        if rules:
            for key, rule in rules.items():
                self._rules[ReaderType(key)] = rule

    # ---- 装配 ------------------------------------------------------------

    @classmethod
    def from_rows(cls, rows: Iterable[dict]) -> "BorrowPolicy":
        """从持久化行装配（供 Mapper / Repository 使用）。"""
        rules: dict[ReaderType, BorrowRule] = {}
        for row in rows:
            reader_type = ReaderType(row["reader_type"])
            rules[reader_type] = BorrowRule(
                reader_type=reader_type,
                max_borrow_count=int(row["max_borrow_count"]),
                borrow_days=int(row["borrow_days"]),
                updated_at=row.get("updated_at"),
                updated_by=row.get("updated_by"),
            )
        return cls(rules)

    # ---- 查询（策略接口） ------------------------------------------------

    def limit_for(self, reader_type: ReaderType | str | None) -> int:
        """该读者类型的最大借阅数量。"""
        return self._rule(reader_type).max_borrow_count

    def days_for(self, reader_type: ReaderType | str | None) -> int:
        """该读者类型的借阅期限（天）。"""
        return self._rule(reader_type).borrow_days

    def rule_of(self, reader_type: ReaderType | str | None) -> BorrowRule:
        return self._rule(reader_type)

    def entries(self) -> list[BorrowRule]:
        """全部规则（供查询接口与持久化使用）。"""
        return list(self._rules.values())

    def _rule(self, reader_type: ReaderType | str | None) -> BorrowRule:
        if reader_type is None:
            raise ValidationError("读者类型缺失，无法查询借阅规则", code="READER_TYPE_REQUIRED")
        try:
            key = ReaderType(reader_type)
        except ValueError as exc:
            raise ValidationError(f"未知的读者类型: {reader_type}", code="UNKNOWN_READER_TYPE") from exc
        rule = self._rules.get(key)
        if rule is None:
            raise ValidationError(f"未配置读者类型 {key.value} 的借阅规则", code="POLICY_NOT_CONFIGURED")
        return rule

    # ---- 维护（BR-049） --------------------------------------------------

    def update(
        self,
        reader_type: ReaderType | str,
        max_borrow_count: int,
        borrow_days: int,
        operator=None,
    ) -> BorrowRule:
        """在线修改规则。**只影响之后创建的借阅**，已有 `Loan.due_at` 不变（BR-050）。"""
        key = ReaderType(reader_type)
        if max_borrow_count < 1:
            raise ValidationError("最大借阅数量必须 ≥ 1", code="INVALID_PARAMETER")
        if borrow_days < 1:
            raise ValidationError("借阅期限必须 ≥ 1 天", code="INVALID_PARAMETER")
        if key not in self._rules:
            raise ValidationError(f"未配置读者类型 {key.value}", code="POLICY_NOT_CONFIGURED")
        rule = BorrowRule(
            reader_type=key,
            max_borrow_count=int(max_borrow_count),
            borrow_days=int(borrow_days),
            updated_at=_utc_now(),
            updated_by=getattr(operator, "account_id", None) or getattr(operator, "admin_id", None),
        )
        self._rules[key] = rule
        return rule
