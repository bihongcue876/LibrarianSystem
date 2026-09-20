"""规则表 Mapper：`borrow_policies` / `fine_rules` ↔ 策略对象。

策略对象是**全部规则的可查询视图**（见 `domain/policies/*` 的形态说明），
因此这里做的是「多行 → 一个策略对象」的装配，而不是逐行映射。
"""

from __future__ import annotations

from typing import Sequence

from app.domain.policies import BorrowPolicy, FineRule
from app.infrastructure.mappers._time import to_db, to_domain
from app.infrastructure.models import BorrowPolicyModel, FineRuleModel


class PolicyMapper:
    """规则双向转换。"""

    # ---- 借阅规则 --------------------------------------------------------

    @staticmethod
    def borrow_rows(models: Sequence[BorrowPolicyModel]) -> list[dict]:
        return [
            {
                "reader_type": model.reader_type,
                "max_borrow_count": model.max_borrow_count,
                "borrow_days": model.borrow_days,
                "updated_at": to_domain(model.updated_at),
                "updated_by": model.updated_by,
            }
            for model in models
        ]

    @staticmethod
    def to_borrow_policy(models: Sequence[BorrowPolicyModel]) -> BorrowPolicy:
        return BorrowPolicy.from_rows(PolicyMapper.borrow_rows(models))

    @staticmethod
    def apply_borrow_policy(policy: BorrowPolicy, models: Sequence[BorrowPolicyModel]) -> None:
        """把策略对象的当前值写回 ORM 行。"""
        by_type = {model.reader_type: model for model in models}
        for rule in policy.entries():
            model = by_type.get(rule.reader_type.value)
            if model is None:
                continue
            model.max_borrow_count = rule.max_borrow_count
            model.borrow_days = rule.borrow_days
            model.updated_at = to_db(rule.updated_at)
            model.updated_by = rule.updated_by

    # ---- 罚款规则 --------------------------------------------------------

    @staticmethod
    def fine_rows(models: Sequence[FineRuleModel]) -> list[dict]:
        return [
            {
                "item_type": model.item_type,
                "daily_price": str(model.daily_price),
                "grace_days": model.grace_days,
                "max_amount": str(model.max_amount),
                "updated_at": to_domain(model.updated_at),
                "updated_by": model.updated_by,
            }
            for model in models
        ]

    @staticmethod
    def to_fine_rule(models: Sequence[FineRuleModel]) -> FineRule:
        return FineRule.from_rows(PolicyMapper.fine_rows(models))

    @staticmethod
    def apply_fine_rule(rule: FineRule, models: Sequence[FineRuleModel]) -> None:
        by_type = {model.item_type: model for model in models}
        for entry in rule.entries():
            model = by_type.get(entry.item_type.value)
            if model is None:
                continue
            model.daily_price = entry.daily_price
            model.grace_days = entry.grace_days
            model.max_amount = entry.max_amount
            model.updated_at = to_db(entry.updated_at)
            model.updated_by = entry.updated_by
