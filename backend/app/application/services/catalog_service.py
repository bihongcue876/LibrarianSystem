"""`CatalogService`（`09-design-model.md` §7）。

题录与馆藏副本的增删改。**仅系统管理员**可操作（BR-041）。
类型分派交给 `LibraryItemFactory`，服务里不写 `if/elif`。
"""

from __future__ import annotations

from datetime import date

from app.application.ports import CatalogRepository
from app.application.unit_of_work import UnitOfWork
from app.domain.entities.book_title import BookTitle
from app.domain.entities.library_item import LibraryItem
from app.domain.enums import ItemStatus, ItemType
from app.domain.exceptions import ConflictError, NotFoundError, ValidationError
from app.domain.factories import LibraryItemFactory
from app.domain.value_objects.barcode import Barcode
from app.domain.value_objects.isbn import Isbn
from app.domain.value_objects.money import Money


class CatalogService:
    """书目与馆藏应用服务。"""

    def __init__(self, uow: UnitOfWork, catalog: CatalogRepository) -> None:
        self._uow = uow
        self._catalog = catalog

    # ---- 题录（UC-208 / UC-209） ----------------------------------------

    def add_book_title(
        self,
        title: str,
        author: str,
        item_type: ItemType | str,
        isbn: str | None = None,
        publisher: str | None = None,
        publish_year: int | None = None,
        language: str | None = None,
    ) -> BookTitle:
        """添加题录（FR-010）。

        - ISBN 格式非法 → 400 `INVALID_ISBN`
        - ISBN 与**活跃**题录重复 → 409（部分唯一索引语义）
        - 允许在无任何副本的状态下创建（BR-014）
        """
        try:
            key = ItemType(item_type)
        except ValueError as exc:
            raise ValidationError(
                f"未知的借出物类型: {item_type}", code="INVALID_PARAMETER"
            ) from exc

        normalized_isbn: Isbn | None = None
        if isbn:
            if not Isbn.is_valid(isbn):
                raise ValidationError(f"ISBN 格式非法: {isbn}", code="INVALID_ISBN")
            normalized_isbn = Isbn(isbn)
            if self._catalog.find_title_by_isbn(str(normalized_isbn), only_active=True) is not None:
                raise ConflictError("该 ISBN 已存在活跃题录", code="ISBN_EXISTS")

        entity = BookTitle(
            title=title,
            author=author,
            isbn=normalized_isbn,
            publisher=publisher,
            publish_year=publish_year,
            item_type=key,
            language=language,
        )
        with self._uow:
            self._catalog.add_title(entity)
            self._uow.commit()
        return entity

    def delete_book_title(self, title_id: int) -> BookTitle:
        """软删除题录，其下副本同步置 `REMOVED`（FR-011 验收 3）。

        **若存在未归还的副本，删除不失败**——该副本保持 `BORROWED` 直至归还，
        归还后置为 `REMOVED`（FR-011 验收 4）。
        """
        title = self._catalog.find_title_by_id(title_id)
        if title is None or title.is_deleted:
            raise NotFoundError("图书标题不存在", code="TITLE_NOT_FOUND")
        with self._uow:
            title.remove()
            self._catalog.update_title(title)
            for item in title.items:
                self._catalog.update_item(item)
            self._uow.commit()
        return title

    # ---- 副本（UC-210 / UC-211 / UC-212） -------------------------------

    def add_library_item(
        self,
        title_id: int,
        location: str | None = None,
        price: str | None = None,
        acquired_at: date | None = None,
    ) -> LibraryItem:
        """添加馆藏副本（FR-012）：条码全局唯一、初始状态 `AVAILABLE`。"""
        title = self._catalog.find_title_by_id(title_id)
        if title is None or title.is_deleted:
            raise NotFoundError("图书标题不存在", code="TITLE_NOT_FOUND")

        barcode = Barcode.generate(self._catalog.next_barcode_sequence())
        if self._catalog.find_item_by_barcode(str(barcode)) is not None:
            raise ConflictError("条码已存在", code="BARCODE_EXISTS")

        try:
            parsed_price = Money.parse(price) if price else None
        except ValueError as exc:
            # `Money.parse` 对非法金额字符串抛 ValueError，规格要求 400
            raise ValidationError(f"非法金额: {price!r}", code="INVALID_PARAMETER") from exc

        item = LibraryItemFactory.create(
            title=title,
            barcode=barcode,
            location=location,
            acquired_at=acquired_at,
            price=parsed_price,
        )
        with self._uow:
            self._catalog.add_item(item)
            self._uow.commit()
        return item

    def delete_library_item(self, item_id: int) -> LibraryItem:
        """软删除副本。`BORROWED` 状态**不允许**直接删除（FR-013 验收 4，返回 400）。"""
        item = self._require_item(item_id)
        with self._uow:
            item.remove()
            self._catalog.update_item(item)
            self._uow.commit()
        return item

    def mark_item_status(self, item_id: int, status: ItemStatus | str) -> LibraryItem:
        """标记副本为 `LOST` / `DAMAGED`，或恢复为 `AVAILABLE`（FR-013）。"""
        item = self._require_item(item_id)
        try:
            target = ItemStatus(status)
        except ValueError as exc:
            raise ValidationError(f"非法状态: {status}", code="INVALID_PARAMETER") from exc

        with self._uow:
            if target is ItemStatus.LOST:
                item.mark_lost()
            elif target is ItemStatus.DAMAGED:
                item.mark_damaged()
            elif target is ItemStatus.AVAILABLE:
                item.mark_available()
            elif target is ItemStatus.REMOVED:
                item.remove()
            else:
                raise ValidationError(f"不支持标记为 {target.value}", code="INVALID_PARAMETER")
            self._catalog.update_item(item)
            self._uow.commit()
        return item

    # ---- 查询 ------------------------------------------------------------

    def get_title(self, title_id: int) -> BookTitle:
        title = self._catalog.find_title_by_id(title_id)
        if title is None:
            raise NotFoundError("图书标题不存在", code="TITLE_NOT_FOUND")
        return title

    def get_item(self, item_id: int) -> LibraryItem:
        return self._require_item(item_id)

    # ---- 内部 ------------------------------------------------------------

    def _require_item(self, item_id: int) -> LibraryItem:
        item = self._catalog.find_item_by_id(item_id)
        if item is None:
            raise NotFoundError("馆藏副本不存在", code="ITEM_NOT_FOUND")
        return item
