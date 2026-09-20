"""查询与统计路由（Controller）——`14-api-spec.md` §4.1、§8。

图书检索对所有人开放；馆藏统计限系统管理员。
纯查询**不经过领域层**（`08-package-diagram.md` §1 已披露该设计）。
"""

from __future__ import annotations

from fastapi import APIRouter, Query

from app.domain.enums import ItemType
from app.presentation.dependencies import AdminAccount, QueryServiceDep
from app.presentation.schemas import BookListResponse, CollectionStatsResponse

router = APIRouter(tags=["query"])


@router.get("/api/books", response_model=BookListResponse)
def search_books(
    service: QueryServiceDep,
    keyword: str | None = None,
    item_type: ItemType | None = None,
    available_only: bool = False,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> BookListResponse:
    """查询图书（UC-003）。

    已软删除的题录与副本**不出现在结果中**（BR-037）。
    """
    return BookListResponse(
        **service.search_books(
            keyword=keyword,
            item_type=item_type,
            available_only=available_only,
            page=page,
            page_size=page_size,
        )
    )


@router.get("/api/admin/collection-stats", response_model=CollectionStatsResponse)
def collection_stats(_: AdminAccount, service: QueryServiceDep) -> CollectionStatsResponse:
    """查询馆藏统计（UC-215）：题录总数、副本总数、按状态与类型分组（FR-029）。"""
    return CollectionStatsResponse(**service.collection_stats())
