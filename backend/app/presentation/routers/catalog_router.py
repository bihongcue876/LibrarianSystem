"""书目与馆藏路由（Controller）——`14-api-spec.md` §4。

写操作限**系统管理员**（BR-041）。
"""

from __future__ import annotations

from fastapi import APIRouter, status

from app.presentation.dependencies import AdminAccount, CatalogServiceDep
from app.presentation.schemas import (
    AddBookTitleRequest,
    AddLibraryItemRequest,
    BookTitleResponse,
    LibraryItemResponse,
    MarkItemStatusRequest,
)

router = APIRouter(tags=["catalog"])


def _title_response(title) -> BookTitleResponse:
    return BookTitleResponse(
        title_id=title.title_id or 0,
        title=title.title,
        author=title.author or None,
        isbn=str(title.isbn) if title.isbn is not None else None,
        publisher=title.publisher,
        publish_year=title.publish_year,
        item_type=title.item_type.value if title.item_type else "",
        language=title.language,
        is_deleted=title.is_deleted,
        total_items=title.total_items(),
        available_items=len(title.available_items()),
    )


def _item_response(item) -> LibraryItemResponse:
    return LibraryItemResponse(
        item_id=item.item_id or 0,
        barcode=str(item.barcode),
        title_id=item.title_id or 0,
        item_type=item.item_type.value if item.item_type else None,
        status=item.status.value,
        location=item.location,
        price=item.price.to_text() if item.price is not None else None,
    )


@router.post(
    "/api/admin/book-titles",
    status_code=status.HTTP_201_CREATED,
    response_model=BookTitleResponse,
)
def add_book_title(
    payload: AddBookTitleRequest, _: AdminAccount, service: CatalogServiceDep
) -> BookTitleResponse:
    """添加图书标题（UC-208）。

    允许在**无任何副本**的状态下创建（BR-014）；
    ISBN 采用部分唯一索引：仅与**活跃**题录查重，已下架的书可重新采购。
    """
    title = service.add_book_title(
        title=payload.title,
        author=payload.author,
        item_type=payload.item_type,
        isbn=payload.isbn,
        publisher=payload.publisher,
        publish_year=payload.publish_year,
        language=payload.language,
    )
    return _title_response(title)


@router.delete("/api/admin/book-titles/{title_id}", status_code=status.HTTP_200_OK)
def delete_book_title(title_id: int, _: AdminAccount, service: CatalogServiceDep) -> dict:
    """删除图书标题（UC-209，软删除）。

    其下副本同步置 `REMOVED`；**若存在未归还副本，删除不失败**，
    该副本保持 `BORROWED` 直至归还后置 `REMOVED`（FR-011 验收 3/4）。
    """
    title = service.delete_book_title(title_id)
    return {"deleted": True, "title_id": title.title_id}


@router.post(
    "/api/admin/library-items",
    status_code=status.HTTP_201_CREATED,
    response_model=LibraryItemResponse,
)
def add_library_item(
    payload: AddLibraryItemRequest, _: AdminAccount, service: CatalogServiceDep
) -> LibraryItemResponse:
    """添加馆藏副本（UC-210）。条码自动生成且全局唯一，初始状态 `AVAILABLE`。"""
    item = service.add_library_item(
        title_id=payload.title_id,
        location=payload.location,
        price=payload.price,
        acquired_at=payload.acquired_at,
    )
    return _item_response(item)


@router.delete("/api/admin/library-items/{item_id}", status_code=status.HTTP_200_OK)
def delete_library_item(item_id: int, _: AdminAccount, service: CatalogServiceDep) -> dict:
    """删除馆藏副本（UC-211）。`BORROWED` 状态不允许直接删除（FR-013 验收 4）。"""
    item = service.delete_library_item(item_id)
    return {"deleted": True, "item_id": item.item_id, "status": item.status.value}


@router.post("/api/admin/library-items/{item_id}/status", response_model=LibraryItemResponse)
def mark_item_status(
    item_id: int,
    payload: MarkItemStatusRequest,
    _: AdminAccount,
    service: CatalogServiceDep,
) -> LibraryItemResponse:
    """标记副本丢失/破损，或恢复为可借（UC-212）。"""
    return _item_response(service.mark_item_status(item_id, payload.status))
