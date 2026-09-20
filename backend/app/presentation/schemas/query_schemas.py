"""查询 DTO（`14-api-spec.md` §4.1、§5.5、§5.8、§8）。"""

from __future__ import annotations

from pydantic import BaseModel


class BookListItem(BaseModel):
    title_id: int
    title: str
    author: str | None = None
    isbn: str | None = None
    publisher: str | None = None
    publish_year: int | None = None
    item_type: str | None = None
    language: str | None = None
    is_deleted: bool = False
    total_items: int = 0
    available_items: int = 0


class BookListResponse(BaseModel):
    page: int
    page_size: int
    total: int
    items: list[BookListItem]


class ReaderLoansResponse(BaseModel):
    reader: dict
    current: list[dict] = []
    history: list[dict] = []
    overdue: list[dict] = []
    reservations: list[dict] = []
    fines: list[dict] = []
    unpaid_total: str = "0.00"


class ReaderFinesResponse(BaseModel):
    unpaid: list[dict] = []
    paid: list[dict] = []
    unpaid_total: str = "0.00"


class CollectionStatsResponse(BaseModel):
    titles: int
    items: int
    by_status: dict
    by_item_type: dict
