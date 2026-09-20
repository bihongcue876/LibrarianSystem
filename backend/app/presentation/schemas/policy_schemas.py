"""规则维护 DTO（`14-api-spec.md` §7）。"""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.domain.enums import ItemType, ReaderType


class UpdateBorrowPolicyRequest(BaseModel):
    reader_type: ReaderType
    max_borrow_count: int = Field(..., ge=1)
    borrow_days: int = Field(..., ge=1)


class UpdateFineRuleRequest(BaseModel):
    item_type: ItemType
    daily_price: str = Field(..., description="定点小数字符串，如 \"0.20\"")
    grace_days: int = Field(..., ge=0)
    max_amount: str = Field(..., description="定点小数字符串，如 \"100.00\"")


class BorrowPolicyItem(BaseModel):
    reader_type: str
    max_borrow_count: int
    borrow_days: int
    updated_at: str | None = None
    updated_by: int | None = None


class FineRuleItem(BaseModel):
    item_type: str
    daily_price: str
    grace_days: int
    max_amount: str
    updated_at: str | None = None
    updated_by: int | None = None


class PoliciesResponse(BaseModel):
    borrow_policies: list[BorrowPolicyItem]
    fine_rules: list[FineRuleItem]
