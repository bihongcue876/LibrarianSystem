"""`PolicyRepository` 的 SQLAlchemy 实现。

规则表由 `scripts/init_db.py` 播种（5 + 5 行）。此处只读写，
规则数值**永不出现在代码分支中**（BR-049）。
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.policies import BorrowPolicy, FineRule
from app.infrastructure.mappers import PolicyMapper
from app.infrastructure.models import BorrowPolicyModel, FineRuleModel


class SqlAlchemyPolicyRepository:
    """实现 `application.ports.PolicyRepository`。"""

    def __init__(self, session: Session) -> None:
        self._session = session

    def get_borrow_policy(self) -> BorrowPolicy:
        return PolicyMapper.to_borrow_policy(self._borrow_rows())

    def get_fine_rule(self) -> FineRule:
        return PolicyMapper.to_fine_rule(self._fine_rows())

    def save_borrow_policy(self, policy: BorrowPolicy) -> None:
        PolicyMapper.apply_borrow_policy(policy, self._borrow_rows())

    def save_fine_rule(self, rule: FineRule) -> None:
        PolicyMapper.apply_fine_rule(rule, self._fine_rows())

    def _borrow_rows(self) -> list[BorrowPolicyModel]:
        return list(
            self._session.scalars(
                select(BorrowPolicyModel).order_by(BorrowPolicyModel.policy_id.asc())
            ).all()
        )

    def _fine_rows(self) -> list[FineRuleModel]:
        return list(
            self._session.scalars(select(FineRuleModel).order_by(FineRuleModel.rule_id.asc())).all()
        )
