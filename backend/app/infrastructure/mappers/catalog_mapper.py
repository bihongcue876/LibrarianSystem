"""`BookTitle` / `LibraryItem` ↔ `book_titles` / `library_items`
（`library_items` 为单表继承，按 `item_type` 分派到 `Book`/`Magazine`/`Thesis`）。
"""

from __future__ import annotations

from typing import Sequence

from app.domain.entities.book_title import BookTitle
from app.domain.entities.library_item import LibraryItem
from app.domain.enums import ItemStatus, ItemType
from app.domain.value_objects.isbn import Isbn
from app.infrastructure.models import BookTitleModel, LibraryItemModel


class CatalogMapper:
    """题录与副本的双向转换。"""

    # ---- 题录 ------------------------------------------------------------

    @staticmethod
    def title_to_domain(
        model: BookTitleModel, items: Sequence[LibraryItemModel] | None = None
    ) -> BookTitle:
        title = BookTitle(
            title_id=model.title_id,
            title=model.title,
            author=model.author or "",
            isbn=_safe_isbn(model.isbn),
            publisher=model.publisher,
            publish_year=model.publish_year,
            item_type=ItemType(model.item_type),
            language=model.language,
            is_deleted=bool(model.is_deleted),
        )
        for item_model in items or []:
            title.items.append(CatalogMapper.item_to_domain(item_model))
        return title

    @staticmethod
    def title_to_model(title: BookTitle, model: BookTitleModel | None = None) -> BookTitleModel:
        target = model or BookTitleModel()
        target.title_id = title.title_id
        target.title = title.title
        target.author = title.author or None
        target.isbn = str(title.isbn) if title.isbn is not None else None
        target.publisher = title.publisher
        target.publish_year = title.publish_year
        target.item_type = title.item_type.value if title.item_type else ""
        target.language = title.language
        target.is_deleted = 1 if title.is_deleted else 0
        return target

    # ---- 副本 ------------------------------------------------------------

    @staticmethod
    def item_to_domain(model: LibraryItemModel) -> LibraryItem:
        return LibraryItem.rehydrate(
            item_id=model.item_id,
            barcode=model.barcode,
            title_id=model.title_id,
            status=ItemStatus(model.status),
            location=model.location,
            acquired_at=model.acquired_at,
            price=model.price,
            item_type=ItemType(model.item_type),
        )

    @staticmethod
    def item_to_model(item: LibraryItem, model: LibraryItemModel | None = None) -> LibraryItemModel:
        target = model or LibraryItemModel()
        target.item_id = item.item_id
        target.barcode = str(item.barcode)
        target.title_id = item.title_id
        target.item_type = item.item_type.value if item.item_type else ""
        target.status = item.status.value
        target.location = item.location
        target.acquired_at = item.acquired_at
        target.price = item.price
        return target


def _safe_isbn(value: str | None) -> Isbn | None:
    """数据库中的 ISBN 可能为空或历史遗留非法值，转换失败时不阻断读取。"""
    if not value:
        return None
    try:
        return Isbn(value)
    except ValueError:
        return None


__all__ = ["CatalogMapper"]
