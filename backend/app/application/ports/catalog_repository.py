"""`CatalogRepository` 接口（题录与馆藏副本）。"""

from __future__ import annotations

from typing import Protocol, Sequence, runtime_checkable

from app.domain.entities.book_title import BookTitle
from app.domain.entities.library_item import LibraryItem
from app.domain.enums import ItemType


@runtime_checkable
class CatalogRepository(Protocol):
    """题录与副本的持久化接口。"""

    # ---- 题录 ------------------------------------------------------------

    def find_title_by_id(self, title_id: int, with_items: bool = True) -> BookTitle | None: ...

    def find_title_by_isbn(self, isbn: str, only_active: bool = True) -> BookTitle | None:
        """按 ISBN 查活跃题录（部分唯一索引语义，`13` §4.5）。"""

    def search_titles(
        self,
        keyword: str | None = None,
        item_type: ItemType | None = None,
        available_only: bool = False,
        include_deleted: bool = False,
        offset: int = 0,
        limit: int = 20,
    ) -> list[BookTitle]: ...

    def count_titles(self, keyword: str | None = None) -> int: ...

    def add_title(self, title: BookTitle) -> BookTitle: ...

    def update_title(self, title: BookTitle) -> None: ...

    # ---- 副本 ------------------------------------------------------------

    def find_item_by_id(self, item_id: int) -> LibraryItem | None: ...

    def find_item_by_barcode(self, barcode: str) -> LibraryItem | None: ...

    def find_items_by_title(self, title_id: int) -> Sequence[LibraryItem]: ...

    def next_barcode_sequence(self) -> int:
        """取下一个可用条码序号（MAX + 1，从 1 开始）。"""

    def add_item(self, item: LibraryItem) -> LibraryItem: ...

    def update_item(self, item: LibraryItem) -> None: ...

    # ---- 统计 ------------------------------------------------------------

    def collection_stats(self) -> dict:
        """馆藏统计：题录总数、副本总数、按状态与类型分组（FR-029）。"""
