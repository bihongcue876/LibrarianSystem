"""书目与馆藏 DTO（`14-api-spec.md` §4）。"""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel, Field

from app.domain.enums import ItemStatus, ItemType


class AddBookTitleRequest(BaseModel):
    title: str = Field(..., min_length=1)
    author: str = Field(default="", max_length=128)
    isbn: str | None = Field(default=None, max_length=20)
    publisher: str | None = Field(default=None, max_length=128)
    publish_year: int | None = Field(default=None, ge=1000, le=2100)
    item_type: ItemType
    language: str | None = Field(default=None, max_length=20)


class AddLibraryItemRequest(BaseModel):
    title_id: int = Field(..., ge=1)
    location: str | None = Field(default=None, max_length=64)
    price: str | None = Field(default=None, description="定点小数字符串，如 \"128.00\"")
    acquired_at: date | None = None


class MarkItemStatusRequest(BaseModel):
    status: ItemStatus


class BookTitleResponse(BaseModel):
    title_id: int
    title: str
    author: str | None = None
    isbn: str | None = None
    publisher: str | None = None
    publish_year: int | None = None
    item_type: str
    language: str | None = None
    is_deleted: bool = False
    total_items: int = 0
    available_items: int = 0


class LibraryItemResponse(BaseModel):
    item_id: int
    barcode: str
    title_id: int
    item_type: str | None = None
    status: str
    location: str | None = None
    price: str | None = None
