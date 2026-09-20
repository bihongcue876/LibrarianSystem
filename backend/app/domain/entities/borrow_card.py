"""BorrowCard 实体（`05-domain-model.md` §3.1、`06-domain-class-diagram.md` 图 2）。

**聚合根**：证号、状态、签发信息必须在同一事务内一致。

状态机（`06` §3）：`ACTIVE` ⇄ `SUSPENDED`，`ACTIVE`/`SUSPENDED` → `CANCELLED` → `ACTIVE`（恢复）。
状态流转只能经实体自身方法，**不允许外部直接改 `status`**——状态字段对外只读。

`EXPIRED` 保留不用（BR-005：借阅证不设过期时间，`expired_at` 字段保留但不校验）。
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING

from app.domain.enums import CardStatus
from app.domain.exceptions import ValidationError
from app.domain.value_objects.card_number import CardNumber

if TYPE_CHECKING:  # pragma: no cover
    from app.domain.entities.reader import Reader, SystemAdmin


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class BorrowCard:
    """借阅证。"""

    def __init__(
        self,
        card_no: CardNumber | str,
        reader_id: int | None = None,
        card_id: int | None = None,
        status: CardStatus = CardStatus.ACTIVE,
        issued_at: datetime | None = None,
        issued_by: int | None = None,
        cancelled_at: datetime | None = None,
        expired_at: datetime | None = None,
    ) -> None:
        self.card_id = card_id
        self.card_no = card_no if isinstance(card_no, CardNumber) else CardNumber.parse(card_no)
        self.reader_id = reader_id
        self._status = CardStatus(status)
        self.issued_at = issued_at or _utc_now()
        self.issued_by = issued_by
        self.cancelled_at = cancelled_at
        self.expired_at = expired_at  # 保留不用（BR-005）

    # ---- 只读状态 --------------------------------------------------------

    @property
    def status(self) -> CardStatus:
        return self._status

    def _transition(self, target: CardStatus, action: str) -> None:
        self._status = target
        if target is CardStatus.CANCELLED:
            self.cancelled_at = _utc_now()

    # ---- 构造（工厂方法） ------------------------------------------------

    @classmethod
    def issue(cls, reader: "Reader", admin: "SystemAdmin", card_number: CardNumber) -> "BorrowCard":
        """签发新借阅证，状态 `ACTIVE`。"""
        if reader is None or reader.reader_id is None:
            raise ValidationError("读者不存在，无法办证", code="READER_NOT_FOUND", http_status=404)
        if getattr(reader, "is_deleted", False):
            raise ValidationError("读者已软删除，无法办证", code="READER_NOT_FOUND", http_status=404)
        if not admin.may_manage_cards():
            raise PermissionError("仅系统管理员可办理借阅证")
        return cls(
            card_no=card_number,
            reader_id=reader.reader_id,
            status=CardStatus.ACTIVE,
            issued_by=admin.admin_id,
        )

    @classmethod
    def rehydrate(
        cls,
        card_id: int,
        card_no: CardNumber | str,
        reader_id: int,
        status: CardStatus | str,
        issued_at: datetime,
        issued_by: int | None = None,
        cancelled_at: datetime | None = None,
        expired_at: datetime | None = None,
    ) -> "BorrowCard":
        """**仅供 Mapper 从持久化状态重建**。不触发状态机校验。"""
        return cls(
            card_id=card_id,
            card_no=card_no,
            reader_id=reader_id,
            status=CardStatus(status),
            issued_at=issued_at,
            issued_by=issued_by,
            cancelled_at=cancelled_at,
            expired_at=expired_at,
        )

    # ---- 状态流转 --------------------------------------------------------

    def cancel(self, admin: "SystemAdmin") -> None:
        """注销：`ACTIVE` / `SUSPENDED` → `CANCELLED`（FR-006）。"""
        if not admin.may_manage_cards():
            raise PermissionError("仅系统管理员可注销借阅证")
        if self._status not in (CardStatus.ACTIVE, CardStatus.SUSPENDED):
            raise ValidationError(
                f"当前状态 {self._status.value} 不可注销", code="CARD_NOT_CANCELLABLE"
            )
        self._transition(CardStatus.CANCELLED, "cancel")

    def restore(self, admin: "SystemAdmin") -> None:
        """恢复：`CANCELLED` → `ACTIVE`（FR-007）。"""
        if not admin.may_manage_cards():
            raise PermissionError("仅系统管理员可恢复借阅证")
        if self._status is not CardStatus.CANCELLED:
            raise ValidationError(
                f"仅 `CANCELLED` 状态可恢复，当前为 {self._status.value}",
                code="CARD_NOT_RESTORABLE",
            )
        self._transition(CardStatus.ACTIVE, "restore")
        self.cancelled_at = None

    def suspend(self, admin: "SystemAdmin") -> None:
        """挂失：`ACTIVE` → `SUSPENDED`（FR-008）。"""
        if not admin.may_manage_cards():
            raise PermissionError("仅系统管理员可挂失借阅证")
        if self._status is not CardStatus.ACTIVE:
            raise ValidationError(
                f"仅 `ACTIVE` 状态可挂失，当前为 {self._status.value}", code="CARD_NOT_SUSPENDABLE"
            )
        self._transition(CardStatus.SUSPENDED, "suspend")

    def resume(self, admin: "SystemAdmin") -> None:
        """解挂：`SUSPENDED` → `ACTIVE`（FR-008）。"""
        if not admin.may_manage_cards():
            raise PermissionError("仅系统管理员可解挂借阅证")
        if self._status is not CardStatus.SUSPENDED:
            raise ValidationError(
                f"仅 `SUSPENDED` 状态可解挂，当前为 {self._status.value}", code="CARD_NOT_RESUMABLE"
            )
        self._transition(CardStatus.ACTIVE, "resume")

    # ---- 判定 ------------------------------------------------------------

    def is_valid(self) -> bool:
        """是否有效（`ACTIVE`）。"""
        return self._status is CardStatus.ACTIVE

    def counts_towards_one_card_limit(self) -> bool:
        """是否占用一人一证限制（BR-003：`ACTIVE` 与 `SUSPENDED` 计入）。"""
        return self._status.counts_towards_one_card_limit

    def __str__(self) -> str:  # pragma: no cover
        return f"BorrowCard({self.card_no}, {self._status.value})"

    def __repr__(self) -> str:  # pragma: no cover
        return self.__str__()
