"""LibraryItemFactory（`05-domain-model.md` §1.2）。

按题录的 `item_type` 分派创建正确的 `LibraryItem` 子类
（`Book` / `Magazine` / `Thesis`），并挂入题录聚合。

**注意**：`domain/entities/` 不得反向依赖本包（包图规则 D-7）——
因此 `BookTitle.add_item()` 只做挂载，创建职责留在这里。
"""

from __future__ import annotations

from datetime import datetime

from app.domain.entities.book_title import BookTitle
from app.domain.entities.library_item import Book, LibraryItem, Magazine, Thesis
from app.domain.enums import ItemStatus, ItemType
from app.domain.exceptions import ValidationError
from app.domain.value_objects.barcode import Barcode
from app.domain.value_objects.money import Money


_SUBCLASS_BY_TYPE: dict[ItemType, type[LibraryItem]] = {
    ItemType.CHINESE_BOOK: Book,
    ItemType.FOREIGN_BOOK: Book,
    ItemType.CHINESE_MAGAZINE: Magazine,
    ItemType.FOREIGN_MAGAZINE: Magazine,
    ItemType.THESIS: Thesis,
}


class LibraryItemFactory:
    """按借出物类型创建 `LibraryItem` 子类。"""

    @staticmethod
    def create(
        title: BookTitle,
        barcode: Barcode | str,
        location: str | None = None,
        acquired_at: datetime | None = None,
        price: Money | None = None,
        item_type: ItemType | str | None = None,
    ) -> LibraryItem:
        """创建副本并挂入题录聚合。

        `item_type` 缺省时取题录的类型——副本类型由题录决定（受控冗余，自题录同步）。
        """
        resolved = ItemType(item_type) if item_type is not None else title.item_type
        if resolved is None:
            raise ValidationError("题录未指定借出物类型，无法创建副本", code="ITEM_TYPE_REQUIRED")
        subclass = _SUBCLASS_BY_TYPE[resolved]
        item = subclass(
            barcode=barcode,
            title_id=title.title_id,
            status=ItemStatus.AVAILABLE,
            location=location,
            acquired_at=acquired_at,
            price=price,
            item_type=resolved,
        )
        title.add_item(item)
        return item

    @staticmethod
    def subclass_for(item_type: ItemType | str) -> type[LibraryItem]:
        return _SUBCLASS_BY_TYPE[ItemType(item_type)]
