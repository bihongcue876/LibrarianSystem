"""书目与馆藏 ORM 模型：`book_titles`、`library_items`
（`13-database-design.md` §4.5、§4.6）。

`library_items` 承载 `LibraryItem` ← `Book` / `Magazine` / `Thesis` 的**单表继承**（D-50），
判别字段为 `item_type`。
"""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.db.base import Base, EnumText, MoneyType

ITEM_TYPES = "'CHINESE_BOOK','FOREIGN_BOOK','CHINESE_MAGAZINE','FOREIGN_MAGAZINE','THESIS'"
ITEM_STATUSES = "'AVAILABLE','BORROWED','RESERVED','LOST','DAMAGED','REMOVED'"


class BookTitleModel(Base):
    """`book_titles` 表（题录）。"""

    __tablename__ = "book_titles"

    title_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    author: Mapped[str | None] = mapped_column(String(128), nullable=True)
    isbn: Mapped[str | None] = mapped_column(String(20), nullable=True)
    publisher: Mapped[str | None] = mapped_column(String(128), nullable=True)
    publish_year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    item_type: Mapped[str] = mapped_column(EnumText(20), nullable=False)
    language: Mapped[str | None] = mapped_column(String(20), nullable=True)
    is_deleted: Mapped[bool] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )  # SQLite 无原生 BOOLEAN，用 0/1
    created_by: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("system_admins.admin_id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
    updated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    __table_args__ = (
        CheckConstraint(f"item_type IN ({ITEM_TYPES})", name="ck_book_titles_item_type"),
        CheckConstraint(
            "publish_year IS NULL OR (publish_year BETWEEN 1000 AND 2100)",
            name="ck_book_titles_publish_year",
        ),
        # ISBN 部分唯一索引：仅约束活跃题录，允许已下架书重新采购
        Index(
            "uq_book_titles_isbn_active",
            "isbn",
            unique=True,
            sqlite_where=text("isbn IS NOT NULL AND is_deleted = 0"),
        ),
        Index("idx_book_titles_title", "title"),
    )


class LibraryItemModel(Base):
    """`library_items` 表（馆藏副本）。"""

    __tablename__ = "library_items"

    item_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    barcode: Mapped[str] = mapped_column(String(10), nullable=False, unique=True)
    title_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("book_titles.title_id"), nullable=False
    )
    item_type: Mapped[str] = mapped_column(EnumText(20), nullable=False)  # 受控冗余，自题录同步
    status: Mapped[str] = mapped_column(EnumText(20), nullable=False)
    location: Mapped[str | None] = mapped_column(String(64), nullable=True)
    acquired_at: Mapped[date | None] = mapped_column(Date, nullable=True)
    price: Mapped[object | None] = mapped_column(MoneyType, nullable=True)
    created_by: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("system_admins.admin_id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())

    __table_args__ = (
        CheckConstraint(f"status IN ({ITEM_STATUSES})", name="ck_library_items_status"),
        CheckConstraint(f"item_type IN ({ITEM_TYPES})", name="ck_library_items_item_type"),
        CheckConstraint(
            "length(barcode) = 10 AND barcode LIKE 'BC%'", name="ck_library_items_barcode"
        ),
        Index("idx_library_items_title_status", "title_id", "status"),
    )
