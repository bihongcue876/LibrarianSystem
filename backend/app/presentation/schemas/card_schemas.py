"""借阅证 DTO（`14-api-spec.md` §3）。"""

from __future__ import annotations

from pydantic import BaseModel, Field


class IssueCardRequest(BaseModel):
    reader_id: int = Field(..., ge=1)


class CardActionRequest(BaseModel):
    reason: str | None = Field(default=None, max_length=128)


class BorrowCardResponse(BaseModel):
    card_id: int
    card_no: str
    reader_id: int
    status: str
    issued_at: str | None = None
    issued_by: int | None = None
    cancelled_at: str | None = None
