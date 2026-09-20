"""BookTitle 实体（`05-domain-model.md` §4.1、`06-domain-class-diagram.md` §4）。

**聚合根**。题录（"《算法导论》这本书"）与副本（"编号 BC00000001 的那一本"）分离：
预约（UC-005）针对**标题**，借出（UC-101）针对**副本**——不分离这两层，预约逻辑无法表达（06 §10.1）。

`items` 为聚合内的副本集合，由 Repository 填充。**题录允许无副本存在**（BR-014）。
"""

from __future__ import annotations

from typing import Sequence

from app.domain.entities.library_item import LibraryItem
from app.domain.enums import ItemType
from app.domain.value_objects.isbn import Isbn


class BookTitle:
    """图书标题（题录）。"""

    def __init__(
        self,
        title: str,
        author: str = "",
        isbn: Isbn | str | None = None,
        publisher: str | None = None,
        publish_year: int | None = None,
        item_type: ItemType | str | None = None,
        language: str | None = None,
        title_id: int | None = None,
        is_deleted: bool = False,
        items: Sequence[LibraryItem] | None = None,
    ) -> None:
        self.title_id = title_id
        self.title = title
        self.author = author
        self.isbn = _normalize_isbn(isbn)
        self.publisher = publisher
        self.publish_year = publish_year
        self.item_type = ItemType(item_type) if item_type is not None else None
        self.language = language
        self.is_deleted = is_deleted
        self.items: list[LibraryItem] = list(items or [])

    # ---- 聚合内操作 ------------------------------------------------------

    def add_item(self, item: LibraryItem) -> LibraryItem:
        """把副本纳入题录聚合。

        **注意**：副本的创建（按 `item_type` 分派到 `Book`/`Magazine`/`Thesis`）
        由 `LibraryItemFactory` 负责，本方法只做聚合内的挂载——这是包图规则 **D-7**
        （实体不得依赖 `factories`）与 `06` 图 3 的 `addItem(barcode)` 签名之间的
        取舍：**以 D-7 为准**，创建职责留在工厂，避免 `entities → factories` 依赖。
        """
        item.title_id = self.title_id
        if item.item_type is None:
            item._item_type = self.item_type  # noqa: SLF001 - 同聚合内的受控冗余同步
        self.items.append(item)
        return item

    def remove_item(self, item: LibraryItem) -> None:
        if item in self.items:
            self.items.remove(item)

    # ---- 查询 ------------------------------------------------------------

    def available_items(self) -> list[LibraryItem]:
        return [item for item in self.items if item.is_available()]

    def total_items(self) -> int:
        return len(self.items)

    def has_available_item(self) -> bool:
        return len(self.available_items()) > 0

    def can_be_reserved(self) -> bool:
        """是否可被预约。

        规则：**仅当该标题下所有副本均不可借时才允许预约**（BR-020）。
        题录已被软删除时不可预约。
        按 BR-020 的字面含义，无任何副本的题录也满足"所有副本均不可借"，
        故此处**不额外排除零副本题录**（`02` 未作限制，不得自行加规则）。
        """
        if self.is_deleted:
            return False
        return not self.has_available_item()

    # ---- 软删除 ----------------------------------------------------------

    def remove(self) -> None:
        """软删除题录，其下副本同步置 `REMOVED`（FR-011 验收标准 3）。

        **注意**：若存在未归还的副本（`BORROWED`），删除**不失败**——该副本保持
        `BORROWED` 直至归还，归还后置为 `REMOVED`（FR-011 验收标准 4）。
        """
        self.is_deleted = True
        for item in self.items:
            if item.status.value != "BORROWED":
                item.remove()

    def mark_returned_item_removed(self, item: LibraryItem) -> None:
        """题录已软删除时，副本归还后直接置 `REMOVED`（FR-011 验收标准 4）。"""
        if self.is_deleted:
            item._status = item.status.__class__.REMOVED  # noqa: SLF001

    def __str__(self) -> str:  # pragma: no cover
        return f"BookTitle(id={self.title_id}, title={self.title!r})"

    def __repr__(self) -> str:  # pragma: no cover
        return self.__str__()


def _normalize_isbn(isbn: Isbn | str | None) -> Isbn | None:
    if isbn is None or isbn == "":
        return None
    if isinstance(isbn, Isbn):
        return isbn
    try:
        return Isbn(isbn)
    except ValueError:
        return None
