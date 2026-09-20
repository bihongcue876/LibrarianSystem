"""`CatalogRepository` 的 SQLAlchemy 实现。"""

from __future__ import annotations

from typing import Sequence

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.domain.entities.book_title import BookTitle
from app.domain.entities.library_item import LibraryItem
from app.domain.enums import ItemStatus, ItemType
from app.infrastructure.mappers import CatalogMapper
from app.infrastructure.models import BookTitleModel, LibraryItemModel


class SqlAlchemyCatalogRepository:
    """实现 `application.ports.CatalogRepository`。"""

    def __init__(self, session: Session) -> None:
        self._session = session

    # ---- 题录 ------------------------------------------------------------

    def find_title_by_id(self, title_id: int, with_items: bool = True) -> BookTitle | None:
        model = self._session.get(BookTitleModel, title_id)
        if model is None:
            return None
        items = self._items_of(title_id) if with_items else []
        return CatalogMapper.title_to_domain(model, items)

    def find_title_by_isbn(self, isbn: str, only_active: bool = True) -> BookTitle | None:
        statement = select(BookTitleModel).where(BookTitleModel.isbn == isbn)
        if only_active:
            statement = statement.where(BookTitleModel.is_deleted == 0)
        model = self._session.scalar(statement)
        return CatalogMapper.title_to_domain(model, self._items_of(model.title_id)) if model else None

    def search_titles(
        self,
        keyword: str | None = None,
        item_type: ItemType | None = None,
        available_only: bool = False,
        include_deleted: bool = False,
        offset: int = 0,
        limit: int = 20,
    ) -> list[BookTitle]:
        statement = select(BookTitleModel)
        if not include_deleted:
            statement = statement.where(BookTitleModel.is_deleted == 0)  # BR-037 软删除过滤
        if item_type is not None:
            statement = statement.where(BookTitleModel.item_type == ItemType(item_type).value)
        if keyword:
            pattern = f"%{keyword}%"
            statement = statement.where(
                or_(
                    BookTitleModel.title.like(pattern),
                    BookTitleModel.author.like(pattern),
                    BookTitleModel.isbn.like(pattern),
                )
            )
        statement = statement.order_by(BookTitleModel.title_id.asc()).offset(offset).limit(limit)
        models = self._session.scalars(statement).all()
        titles = [CatalogMapper.title_to_domain(model, self._items_of(model.title_id)) for model in models]
        if available_only:
            titles = [title for title in titles if title.has_available_item()]
        return titles

    def count_titles(self, keyword: str | None = None) -> int:
        statement = select(func.count()).select_from(BookTitleModel).where(
            BookTitleModel.is_deleted == 0
        )
        if keyword:
            pattern = f"%{keyword}%"
            statement = statement.where(
                or_(
                    BookTitleModel.title.like(pattern),
                    BookTitleModel.author.like(pattern),
                    BookTitleModel.isbn.like(pattern),
                )
            )
        return int(self._session.scalar(statement) or 0)

    def add_title(self, title: BookTitle) -> BookTitle:
        model = CatalogMapper.title_to_model(title)
        self._session.add(model)
        self._session.flush()
        title.title_id = model.title_id
        return title

    def update_title(self, title: BookTitle) -> None:
        if title.title_id is None:
            return
        model = self._session.get(BookTitleModel, title.title_id)
        if model is None:
            return
        CatalogMapper.title_to_model(title, model)

    # ---- 副本 ------------------------------------------------------------

    def find_item_by_id(self, item_id: int) -> LibraryItem | None:
        model = self._session.get(LibraryItemModel, item_id)
        return CatalogMapper.item_to_domain(model) if model else None

    def find_item_by_barcode(self, barcode: str) -> LibraryItem | None:
        model = self._session.scalar(
            select(LibraryItemModel).where(LibraryItemModel.barcode == barcode)
        )
        return CatalogMapper.item_to_domain(model) if model else None

    def find_items_by_title(self, title_id: int) -> Sequence[LibraryItem]:
        return [CatalogMapper.item_to_domain(model) for model in self._items_of(title_id)]

    def next_barcode_sequence(self) -> int:
        current_max = self._session.scalar(select(func.max(LibraryItemModel.barcode)))
        if not current_max:
            return 1
        return int(str(current_max)[2:10]) + 1

    def add_item(self, item: LibraryItem) -> LibraryItem:
        model = CatalogMapper.item_to_model(item)
        self._session.add(model)
        self._session.flush()
        item.item_id = model.item_id
        return item

    def update_item(self, item: LibraryItem) -> None:
        if item.item_id is None:
            return
        model = self._session.get(LibraryItemModel, item.item_id)
        if model is None:
            return
        CatalogMapper.item_to_model(item, model)

    # ---- 统计 ------------------------------------------------------------

    def collection_stats(self) -> dict:
        title_total = int(
            self._session.scalar(
                select(func.count()).select_from(BookTitleModel).where(BookTitleModel.is_deleted == 0)
            )
            or 0
        )
        items = self._session.scalars(select(LibraryItemModel)).all()
        by_status: dict[str, int] = {status.value: 0 for status in ItemStatus}
        by_type: dict[str, int] = {item_type.value: 0 for item_type in ItemType}
        for item in items:
            by_status[item.status] = by_status.get(item.status, 0) + 1
            by_type[item.item_type] = by_type.get(item.item_type, 0) + 1
        return {
            "titles": title_total,
            "items": len(items),
            "by_status": by_status,
            "by_item_type": by_type,
        }

    # ---- 内部 ------------------------------------------------------------

    def _items_of(self, title_id: int) -> list[LibraryItemModel]:
        return list(
            self._session.scalars(
                select(LibraryItemModel)
                .where(LibraryItemModel.title_id == title_id)
                .order_by(LibraryItemModel.item_id.asc())
            ).all()
        )
