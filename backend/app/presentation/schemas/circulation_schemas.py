"""流通 DTO（`14-api-spec.md` §5）。"""

from __future__ import annotations

from pydantic import BaseModel, Field


class BorrowBookRequest(BaseModel):
    card_no: str = Field(..., min_length=14, max_length=14, pattern=r"^CARD\d{10}$")
    barcode: str = Field(..., min_length=10, max_length=10, pattern=r"^BC\d{8}$")


class PreCheckRequest(BaseModel):
    card_no: str = Field(..., min_length=14, max_length=14, pattern=r"^CARD\d{10}$")
    barcode: str = Field(..., min_length=10, max_length=10, pattern=r"^BC\d{8}$")


class ReturnBookRequest(BaseModel):
    barcode: str = Field(..., min_length=10, max_length=10, pattern=r"^BC\d{8}$")


class CheckResultDTO(BaseModel):
    step: str
    ok: bool
    code: str = ""
    message: str = ""
    detail: dict = {}


class ReaderBrief(BaseModel):
    reader_id: int
    name: str
    reader_type: str | None = None


class QuotaInfo(BaseModel):
    limit: int
    occupied: int
    remaining: int


class PreCheckResponse(BaseModel):
    reader: ReaderBrief | None = None
    quota: QuotaInfo | None = None
    alerts: dict = {}
    can_borrow: bool = False
    checks: list[CheckResultDTO] = []


class BorrowBookResponse(BaseModel):
    loan_id: int
    reader_id: int
    item_id: int
    barcode: str
    borrowed_at: str | None = None
    due_at: str | None = None
    status: str
    remaining_quota: int


class FineBrief(BaseModel):
    fine_id: int
    amount: str
    status: str


class ReservationAdvance(BaseModel):
    reservation_id: int
    status: str
    reader_id: int | None = None


class ReturnBookResponse(BaseModel):
    loan_id: int
    returned_at: str | None = None
    overdue_days: int
    billed_days: int = 0
    fine: FineBrief | None = None
    item_status: str
    reservation_advanced: ReservationAdvance | None = None


class RenewResponse(BaseModel):
    loan_id: int
    due_at: str | None = None
    renew_count: int
    status: str


class CollectFineResponse(BaseModel):
    fine_id: int
    status: str
    paid_at: str | None = None
    operator_id: int | None = None
    operator_role: str | None = None
