"""预约 DTO（`14-api-spec.md` §6）。"""

from __future__ import annotations

from pydantic import BaseModel, Field


class CreateReservationRequest(BaseModel):
    """**注意**：请求体不含 `reader_id`——预约人取自 JWT 身份（BR-039）。"""

    title_id: int = Field(..., ge=1)


class ReservationResponse(BaseModel):
    reservation_id: int
    title_id: int
    reader_id: int | None = None
    status: str
    created_at: str | None = None
    ready_at: str | None = None
    queue_position: int = 0
    expires_at: str | None = None
    is_expired: bool = False


class CancelReservationResponse(BaseModel):
    reservation_id: int
    status: str
    advanced_to: dict | None = None
