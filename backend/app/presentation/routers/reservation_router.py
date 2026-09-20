"""预约路由（Controller）——`14-api-spec.md` §6。

预约人一律取自 **JWT 身份**，请求体**不含** `reader_id`（BR-039）。
"""

from __future__ import annotations

from fastapi import APIRouter, status

from app.presentation.dependencies import ReaderAccount, ReservationServiceDep
from app.presentation.schemas import (
    CancelReservationResponse,
    CreateReservationRequest,
    ReservationResponse,
)
from app.presentation.serializers import iso

router = APIRouter(tags=["reservation"])


def _to_response(payload: dict) -> ReservationResponse:
    return ReservationResponse(
        reservation_id=payload["reservation_id"],
        title_id=payload["title_id"],
        reader_id=payload["reader_id"],
        status=payload["status"],
        created_at=iso(payload.get("created_at")),
        ready_at=iso(payload.get("ready_at")),
        queue_position=payload.get("queue_position", 0),
        expires_at=iso(payload.get("expires_at")),
        is_expired=payload.get("is_expired", False),
    )


@router.post(
    "/api/reservations",
    status_code=status.HTTP_201_CREATED,
    response_model=ReservationResponse,
)
def create_reservation(
    payload: CreateReservationRequest,
    account: ReaderAccount,
    service: ReservationServiceDep,
) -> ReservationResponse:
    """预约图书（UC-005）。

    - 仅当该标题下**所有副本均不可借**时才可预约（BR-020）
    - 队列上限 5 人（BR-022）、同一读者不得重复预约（BR-023）
    - 排队顺序按 `created_at`（BR-021）
    """
    result = service.create_reservation(getattr(account, "reader_id"), payload.title_id)
    return _to_response(result)


@router.delete("/api/reservations/{reservation_id}", response_model=CancelReservationResponse)
def cancel_reservation(
    reservation_id: int, account: ReaderAccount, service: ReservationServiceDep
) -> CancelReservationResponse:
    """取消预约（UC-006）。`ACTIVE` 与 `READY` 均可取消（BR-025a）。

    若持有 `RESERVED` 副本，副本转交下一位预约者并保持 `RESERVED`（BR-024a）。
    """
    return CancelReservationResponse(**service.cancel_reservation(reservation_id, account))


@router.get("/api/me/reservations", response_model=list[ReservationResponse])
def my_reservations(
    account: ReaderAccount, service: ReservationServiceDep, only_active: bool = False
) -> list[ReservationResponse]:
    """查询预约状态（FR-024 / UC-004 步骤 5）。含排队位置。"""
    records = service.list_by_reader(getattr(account, "reader_id"), only_active=only_active)
    return [_to_response(record) for record in records]
