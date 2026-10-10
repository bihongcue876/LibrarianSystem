"""流通路由（Controller）——`14-api-spec.md` §5。

借书、还书限**图书管理员 / 系统管理员**（BR-040）；
续借允许读者本人自助；查询借阅信息按角色区分数据范围（BR-039）。
"""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Query, status

from app.presentation.dependencies import (
    CirculationServiceDep,
    CurrentAccount,
    QueryServiceDep,
    ReaderAccount,
    StaffAccount,
)
from app.presentation.schemas import (
    BorrowBookRequest,
    BorrowBookResponse,
    CollectFineResponse,
    PreCheckRequest,
    PreCheckResponse,
    ReaderFinesResponse,
    ReaderLoansResponse,
    RenewResponse,
    ReturnBookRequest,
    ReturnBookResponse,
)
from app.presentation.serializers import iso

router = APIRouter(tags=["circulation"])


# ---------------------------------------------------------------------------
# 借书
# ---------------------------------------------------------------------------

@router.post("/api/circulation/precheck", response_model=PreCheckResponse)
def precheck(
    payload: PreCheckRequest, _: StaffAccount, service: CirculationServiceDep
) -> PreCheckResponse:
    """借书前置校验（FR-015）。**只读**，不产生任何数据变更。"""
    return PreCheckResponse(**service.precheck(payload.card_no, payload.barcode))


@router.post(
    "/api/circulation/borrow",
    status_code=status.HTTP_201_CREATED,
    response_model=BorrowBookResponse,
)
def borrow_book(
    payload: BorrowBookRequest, account: StaffAccount, service: CirculationServiceDep
) -> BorrowBookResponse:
    """办理借书（UC-101）。

    六项校验按固定顺序「借阅证 → 数量 → 超期 → 罚款 → 副本」，
    遇首个失败即返回；整个操作在单个事务内，失败全部回滚。
    """
    result = service.borrow_book(payload.card_no, payload.barcode, account)
    result["borrowed_at"] = iso(result["borrowed_at"])
    result["due_at"] = iso(result["due_at"])
    return BorrowBookResponse(**result)


# ---------------------------------------------------------------------------
# 还书与罚款
# ---------------------------------------------------------------------------

@router.post("/api/circulation/return", response_model=ReturnBookResponse)
def return_book(
    payload: ReturnBookRequest, account: StaffAccount, service: CirculationServiceDep
) -> ReturnBookResponse:
    """办理还书（UC-102）。**仅凭馆藏条码，不要求借阅证**。"""
    result = service.return_book(payload.barcode, account)
    result["returned_at"] = iso(result["returned_at"])
    return ReturnBookResponse(**result)


@router.post("/api/circulation/loans/{loan_id}/renew", response_model=RenewResponse)
def renew_loan(
    loan_id: int, account: CurrentAccount, service: CirculationServiceDep
) -> RenewResponse:
    """续借图书（UC-007）。读者仅可续借本人记录；最多 2 次、每次 +7 天（BR-015）。"""
    result = service.renew_loan(loan_id, account)
    result["due_at"] = iso(result["due_at"])
    return RenewResponse(**result)


@router.post("/api/fines/{fine_id}/collect", response_model=CollectFineResponse)
def collect_fine(
    fine_id: int, account: StaffAccount, service: CirculationServiceDep
) -> CollectFineResponse:
    """收缴罚款（UC-104）。系统**不接入在线支付**（BR-031）。"""
    result = service.collect_fine(fine_id, account)
    result["paid_at"] = iso(result["paid_at"])
    return CollectFineResponse(**result)


# ---------------------------------------------------------------------------
# 查询
# ---------------------------------------------------------------------------

@router.get("/api/me/loans", response_model=ReaderLoansResponse)
def my_loans(
    account: ReaderAccount,
    service: QueryServiceDep,
    status_filter: Literal["current", "history", "overdue"] | None = Query(
        default=None, alias="status"
    ),
) -> ReaderLoansResponse:
    """查询本人借阅信息（UC-004）。

    返回四段结构：当前借阅、历史借阅、预约列表、罚款记录（FR-019 验收 1~4）；
    **不返回经办管理员 ID**（FR-019 验收 6）。
    """
    reader_id = getattr(account, "reader_id")
    return ReaderLoansResponse(**service.get_reader_loans(reader_id, account, status_filter))


@router.get("/api/readers/{reader_id}/loans", response_model=ReaderLoansResponse)
def reader_loans(
    reader_id: int,
    account: StaffAccount,
    service: QueryServiceDep,
    status_filter: str | None = Query(default=None, alias="status"),
) -> ReaderLoansResponse:
    """查询读者借阅信息（UC-103）。图书管理员与系统管理员可查任意读者。"""
    return ReaderLoansResponse(**service.get_reader_loans(reader_id, account, status_filter))


@router.get("/api/me/fines", response_model=ReaderFinesResponse)
def my_fines(account: ReaderAccount, service: QueryServiceDep) -> ReaderFinesResponse:
    """查询本人罚款记录（FR-026）。"""
    reader_id = getattr(account, "reader_id")
    return ReaderFinesResponse(**service.get_reader_fines(reader_id, account))
