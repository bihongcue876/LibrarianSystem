"""规则路由（Controller）——`14-api-spec.md` §7。

查询对**登录用户**开放（读者需知晓本人额度与期限）；维护限系统管理员（BR-041）。
"""

from __future__ import annotations

from fastapi import APIRouter

from app.presentation.dependencies import (
    AdminAccount,
    CurrentAccount,
    PolicyServiceDep,
)
from app.presentation.schemas import (
    PoliciesResponse,
    UpdateBorrowPolicyRequest,
    UpdateFineRuleRequest,
)
from app.presentation.schemas.policy_schemas import BorrowPolicyItem, FineRuleItem
from app.presentation.serializers import iso

router = APIRouter(tags=["policy"])


@router.get("/api/policies", response_model=PoliciesResponse)
def get_policies(_: CurrentAccount, service: PolicyServiceDep) -> PoliciesResponse:
    """查询当前借阅规则与罚款规则（FR-027、FR-028）。"""
    payload = service.get_all()
    return PoliciesResponse(
        borrow_policies=[
            BorrowPolicyItem(**{**item, "updated_at": iso(item.get("updated_at"))})
            for item in payload["borrow_policies"]
        ],
        fine_rules=[
            FineRuleItem(**{**item, "updated_at": iso(item.get("updated_at"))})
            for item in payload["fine_rules"]
        ],
    )


@router.put("/api/admin/policies/borrow", response_model=BorrowPolicyItem)
def update_borrow_policy(
    payload: UpdateBorrowPolicyRequest,
    account: AdminAccount,
    service: PolicyServiceDep,
) -> BorrowPolicyItem:
    """维护借阅规则（UC-213）。

    修改**只影响之后创建的借阅**，已存在的 `Loan.due_at` 不受影响（BR-050）。
    """
    result = service.update_borrow_policy(
        payload.reader_type, payload.max_borrow_count, payload.borrow_days, account
    )
    return BorrowPolicyItem(**{**result, "updated_at": iso(result.get("updated_at"))})


@router.put("/api/admin/policies/fine", response_model=FineRuleItem)
def update_fine_rule(
    payload: UpdateFineRuleRequest,
    account: AdminAccount,
    service: PolicyServiceDep,
) -> FineRuleItem:
    """维护罚款规则（UC-214）。`FineRecord` 快照 `unit_price`，修改不追溯（BR-050）。"""
    result = service.update_fine_rule(
        payload.item_type,
        payload.daily_price,
        payload.grace_days,
        payload.max_amount,
        account,
    )
    return FineRuleItem(**{**result, "updated_at": iso(result.get("updated_at"))})
