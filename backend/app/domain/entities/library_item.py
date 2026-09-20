"""LibraryItem 实体族（`05-domain-model.md` §4.2、§4.3）。

继承体系：`LibraryItem`（抽象）← `Book` / `Magazine` / `Thesis`。
子类**仅承担语义分类**，无额外属性——中外文差异由 `item_type` 取值表达，
罚款单价由 `FineRule` 按 `item_type` 查表决定，**不在子类硬编码**。

持久化层用**单表继承**（决策 D-50）：`library_items` 表加 `item_type` 判别列，不拆表。
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from app.domain.enums import ItemStatus, ItemType
from app.domain.exceptions import ValidationError
from app.domain.value_objects.barcode import Barcode

if TYPE_CHECKING:  # pragma: no cover
    from app.domain.value_objects.money import Money


class LibraryItem:
    """馆藏副本（抽象基类）。以 `barcode` 为业务唯一标识。"""

    IS_ABSTRACT = True

    def __init__(
        self,
        barcode: Barcode | str,
        title_id: int | None = None,
        item_id: int | None = None,
        status: ItemStatus = ItemStatus.AVAILABLE,
        location: str | None = None,
        acquired_at: datetime | None = None,
        price: "Money | None" = None,
        item_type: ItemType | str | None = None,
    ) -> None:
        self.item_id = item_id
        self.barcode = barcode if isinstance(barcode, Barcode) else Barcode.parse(barcode)
        self.title_id = title_id
        self._status = ItemStatus(status)
        self.location = location
        self.acquired_at = acquired_at
        self.price = price
        self._item_type = ItemType(item_type) if item_type is not None else None

    # ---- 只读状态 --------------------------------------------------------

    @property
    def status(self) -> ItemStatus:
        return self._status

    @property
    def item_type(self) -> ItemType | None:
        """受控冗余：自题录同步（`13-database-design.md` §6.1）。"""
        return self._item_type

    # ---- 重建（供 Mapper） ----------------------------------------------

    @classmethod
    def rehydrate(cls, **kwargs) -> "LibraryItem":
        """**仅供 Mapper 从持久化状态重建**。按 `item_type` 分派到正确子类。"""
        raw_type = kwargs.get("item_type")
        key = ItemType(raw_type) if raw_type is not None else None
        return _SUBCLASS_BY_ITEM_TYPE.get(key, Book)(**kwargs)

    # ---- 状态机 ----------------------------------------------------------

    def _require_status(self, allowed: tuple[ItemStatus, ...], action: str) -> None:
        if self._status not in allowed:
            raise ValidationError(
                f"当前状态 {self._status.value} 不允许 {action}",
                code="INVALID_ITEM_TRANSITION",
                detail={"status": self._status.value, "action": action},
            )

    def is_available(self) -> bool:
        return self._status is ItemStatus.AVAILABLE

    def mark_borrowed(self) -> None:
        """借出：仅 `AVAILABLE` 可借（BR-033）。"""
        self._require_status((ItemStatus.AVAILABLE,), "借出")
        self._status = ItemStatus.BORROWED

    def mark_returned(self, has_reservation: bool = False) -> None:
        """归还：`BORROWED` → `RESERVED`（有预约）或 `AVAILABLE`（无预约）。"""
        self._require_status((ItemStatus.BORROWED,), "归还")
        self._status = ItemStatus.RESERVED if has_reservation else ItemStatus.AVAILABLE

    def mark_reserved(self) -> None:
        """为预约者预留（BR-024）。

        允许从 `AVAILABLE`、`BORROWED`（还书交接）或 `RESERVED`（预约顺延交接）
        进入——第三种情况正是 BR-024a 的副本转交。
        """
        self._require_status(
            (ItemStatus.AVAILABLE, ItemStatus.BORROWED, ItemStatus.RESERVED), "预留"
        )
        self._status = ItemStatus.RESERVED

    def release_reservation(self) -> None:
        """解除预留、释放为可借。**仅当该标题的预约队列已无有效预约**时调用（BR-024a）。"""
        self._require_status((ItemStatus.RESERVED,), "解除预留")
        self._status = ItemStatus.AVAILABLE

    def mark_lost(self) -> None:
        self._require_status(
            (ItemStatus.AVAILABLE, ItemStatus.BORROWED, ItemStatus.RESERVED), "标记丢失"
        )
        self._status = ItemStatus.LOST

    def mark_damaged(self) -> None:
        self._require_status(
            (ItemStatus.AVAILABLE, ItemStatus.BORROWED, ItemStatus.RESERVED), "标记破损"
        )
        self._status = ItemStatus.DAMAGED

    def remove(self) -> None:
        """下架/软删除。`BORROWED` 状态不可直接删除，须先归还（BR-034、FR-013 验收 4）。"""
        self._require_status(
            (ItemStatus.AVAILABLE, ItemStatus.RESERVED, ItemStatus.LOST, ItemStatus.DAMAGED),
            "删除",
        )
        self._status = ItemStatus.REMOVED

    def mark_available(self) -> None:
        """恢复为可借（用于 `LOST`/`DAMAGED` 纠正）。"""
        self._require_status((ItemStatus.LOST, ItemStatus.DAMAGED), "恢复可借")
        self._status = ItemStatus.AVAILABLE

    def __str__(self) -> str:  # pragma: no cover
        return f"{type(self).__name__}({self.barcode}, {self._status.value})"

    def __repr__(self) -> str:  # pragma: no cover
        return self.__str__()


class Book(LibraryItem):
    """图书。`item_type` 为 `CHINESE_BOOK` 或 `FOREIGN_BOOK`。"""


class Magazine(LibraryItem):
    """杂志。`item_type` 为 `CHINESE_MAGAZINE` 或 `FOREIGN_MAGAZINE`。"""


class Thesis(LibraryItem):
    """论文。`item_type` 为 `THESIS`。"""


_SUBCLASS_BY_ITEM_TYPE: dict[ItemType | None, type[LibraryItem]] = {
    ItemType.CHINESE_BOOK: Book,
    ItemType.FOREIGN_BOOK: Book,
    ItemType.CHINESE_MAGAZINE: Magazine,
    ItemType.FOREIGN_MAGAZINE: Magazine,
    ItemType.THESIS: Thesis,
}
