"""借阅证路由（Controller）——`14-api-spec.md` §3。

全部管理动作限**系统管理员**（BR-041）；查询借阅证信息对登录用户开放。
"""

from __future__ import annotations

from fastapi import APIRouter, status

from app.presentation.dependencies import AdminAccount, CardServiceDep, CurrentAccount
from app.presentation.schemas import BorrowCardResponse, IssueCardRequest
from app.presentation.serializers import iso

router = APIRouter(tags=["card"])


def _to_response(card) -> BorrowCardResponse:
    return BorrowCardResponse(
        card_id=card.card_id or 0,
        card_no=str(card.card_no),
        reader_id=card.reader_id or 0,
        status=card.status.value,
        issued_at=iso(card.issued_at),
        issued_by=card.issued_by,
        cancelled_at=iso(card.cancelled_at),
    )


@router.post(
    "/api/admin/borrow-cards",
    status_code=status.HTTP_201_CREATED,
    response_model=BorrowCardResponse,
)
def issue_card(
    payload: IssueCardRequest, account: AdminAccount, service: CardServiceDep
) -> BorrowCardResponse:
    """办理借阅证（UC-201）。一人一证：`ACTIVE`/`SUSPENDED` 计入，`CANCELLED` 不计入（BR-003）。"""
    return _to_response(service.issue_card(payload.reader_id, account))


@router.post("/api/admin/borrow-cards/{card_id}/cancel", response_model=BorrowCardResponse)
def cancel_card(
    card_id: int,
    account: AdminAccount,
    service: CardServiceDep,
) -> BorrowCardResponse:
    """注销借阅证（UC-202）。注销后该读者可重新办证（FR-006 验收 4）。"""
    return _to_response(service.cancel_card(card_id, account))


@router.post("/api/admin/borrow-cards/{card_id}/restore", response_model=BorrowCardResponse)
def restore_card(
    card_id: int, account: AdminAccount, service: CardServiceDep
) -> BorrowCardResponse:
    """恢复已注销的借阅证（UC-203）。"""
    return _to_response(service.restore_card(card_id, account))


@router.post("/api/admin/borrow-cards/{card_id}/suspend", response_model=BorrowCardResponse)
def suspend_card(
    card_id: int, account: AdminAccount, service: CardServiceDep
) -> BorrowCardResponse:
    """挂失借阅证（UC-204）。"""
    return _to_response(service.suspend_card(card_id, account))


@router.post("/api/admin/borrow-cards/{card_id}/resume", response_model=BorrowCardResponse)
def resume_card(card_id: int, account: AdminAccount, service: CardServiceDep) -> BorrowCardResponse:
    """解挂借阅证（UC-204）。"""
    return _to_response(service.resume_card(card_id, account))


@router.get("/api/borrow-cards/{card_no}", response_model=BorrowCardResponse)
def get_card(card_no: str, account: CurrentAccount, service: CardServiceDep) -> BorrowCardResponse:
    """查询借阅证信息（UC-205）。"""
    return _to_response(service.get_by_card_no(card_no))


@router.get("/api/admin/readers/{reader_id}/borrow-cards", response_model=list[BorrowCardResponse])
def list_cards_by_reader(
    reader_id: int, account: AdminAccount, service: CardServiceDep
) -> list[BorrowCardResponse]:
    """按读者查询全部借阅证（含历史注销记录，FR-009 验收 2）。"""
    return [_to_response(card) for card in service.list_by_reader(reader_id)]
