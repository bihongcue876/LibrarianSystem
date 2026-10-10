"""`PolicyRepository` 接口（借阅规则与罚款规则）。"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from app.domain.policies import BorrowPolicy, FineRule


@runtime_checkable
class PolicyRepository(Protocol):
    """规则持久化接口。

    规则对象是**整体视图**（含全部读者类型 / 借出物类型），
    因此读取返回策略对象、写入接收策略对象的当前值。
    """

    def get_borrow_policy(self) -> BorrowPolicy:
        """读取借阅规则（5 条）。"""

    def get_fine_rule(self) -> FineRule:
        """读取罚款规则（5 条）。"""

    def save_borrow_policy(self, policy: BorrowPolicy) -> None:
        """写回借阅规则（维护接口用，BR-049）。"""

    def save_fine_rule(self, rule: FineRule) -> None:
        """写回罚款规则。"""
