"""`PolicyService`（`09-design-model.md` §1.2）。

借阅规则与罚款规则的查询与维护。

**规则必须存库**（BR-049）：修改后立即生效于**新业务**，
**不追溯**已有记录——`loans.due_at` 与 `fine_records.unit_price` 均为生成时快照（BR-050）。
"""

from __future__ import annotations

from app.application.ports import PolicyRepository
from app.application.unit_of_work import UnitOfWork
from app.domain.enums import ItemType, ReaderType
from app.domain.exceptions import ValidationError


class PolicyService:
    """规则维护应用服务。"""

    def __init__(self, uow: UnitOfWork, policies: PolicyRepository) -> None:
        self._uow = uow
        self._policies = policies

    # ---- 查询（读者也需知晓本人额度与期限） ------------------------------

    def get_all(self) -> dict:
        borrow = self._policies.get_borrow_policy()
        fine = self._policies.get_fine_rule()
        return {
            "borrow_policies": [
                {
                    "reader_type": rule.reader_type.value,
                    "max_borrow_count": rule.max_borrow_count,
                    "borrow_days": rule.borrow_days,
                    "updated_at": rule.updated_at,
                    "updated_by": rule.updated_by,
                }
                for rule in borrow.entries()
            ],
            "fine_rules": [
                {
                    "item_type": entry.item_type.value,
                    "daily_price": entry.daily_price.to_text(),
                    "grace_days": entry.grace_days,
                    "max_amount": entry.max_amount.to_text(),
                    "updated_at": entry.updated_at,
                    "updated_by": entry.updated_by,
                }
                for entry in fine.entries()
            ],
        }

    # ---- 维护（UC-213 / FR-027） ----------------------------------------

    def update_borrow_policy(
        self, reader_type: ReaderType | str, max_borrow_count: int, borrow_days: int, operator
    ) -> dict:
        """维护借阅规则。数值非法（≤0）→ 400。"""
        if int(max_borrow_count) < 1:
            raise ValidationError("最大借阅数量必须 ≥ 1", code="INVALID_PARAMETER")
        if int(borrow_days) < 1:
            raise ValidationError("借阅期限必须 ≥ 1 天", code="INVALID_PARAMETER")

        with self._uow:
            policy = self._policies.get_borrow_policy()
            rule = policy.update(reader_type, int(max_borrow_count), int(borrow_days), operator)
            self._policies.save_borrow_policy(policy)
            self._uow.commit()

        return {
            "reader_type": rule.reader_type.value,
            "max_borrow_count": rule.max_borrow_count,
            "borrow_days": rule.borrow_days,
            "updated_at": rule.updated_at,
            "updated_by": rule.updated_by,
        }

    # ---- 维护（UC-214 / FR-028） ----------------------------------------

    def update_fine_rule(
        self,
        item_type: ItemType | str,
        daily_price,
        grace_days: int,
        max_amount,
        operator,
    ) -> dict:
        """维护罚款规则。金额为定点小数字符串；负数 → 400。"""
        with self._uow:
            rule = self._policies.get_fine_rule()
            entry = rule.update(item_type, daily_price, int(grace_days), max_amount, operator)
            self._policies.save_fine_rule(rule)
            self._uow.commit()

        return {
            "item_type": entry.item_type.value,
            "daily_price": entry.daily_price.to_text(),
            "grace_days": entry.grace_days,
            "max_amount": entry.max_amount.to_text(),
            "updated_at": entry.updated_at,
            "updated_by": entry.updated_by,
        }
