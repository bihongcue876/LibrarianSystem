"""领域异常体系。

归属：领域层。**不得**导入 fastapi / sqlalchemy（宪法第五条、包图规则 R-3）。

设计依据：`09-design-model.md` §10、`07-architecture.md` §6.2。

注意：`07-architecture.md` §6.2 的异常→HTTP 映射是**层级通用约定**；
具体接口的状态码与错误码以 `02-requirements.md` 各 FR 的验收标准为准
（例如 FR-016 把借书业务规则失败规定为 400）。
"""

from __future__ import annotations

from typing import Any


class DomainError(Exception):
    """领域异常基类。携带错误码、可读消息、HTTP 状态码与上下文明细。"""

    code: str = "DOMAIN_ERROR"
    http_status: int = 400

    def __init__(
        self,
        message: str,
        code: str | None = None,
        http_status: int | None = None,
        detail: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        if code is not None:
            self.code = code
        if http_status is not None:
            self.http_status = http_status
        self.detail = detail or {}

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "message": self.message,
            "detail": self.detail,
        }


class NotFoundError(DomainError):
    """资源不存在。"""

    code = "NOT_FOUND"
    http_status = 404


class ValidationError(DomainError):
    """参数或状态不合法。"""

    code = "VALIDATION_ERROR"
    http_status = 400


class BusinessRuleError(DomainError):
    """违反业务规则。

    HTTP 状态码默认 400 —— 与 `02` FR-016 的验收标准一致
    （借书业务规则失败为 400，而非 `07` §6.2 通用表里的 409）。
    """

    code = "BUSINESS_RULE_VIOLATION"
    http_status = 400


class ConflictError(DomainError):
    """资源冲突（重复预约、重复办证、唯一键重复）。"""

    code = "CONFLICT"
    http_status = 409


# ---------------------------------------------------------------------------
# 具体错误码（便于调用方与测试直接引用，避免字符串散落）
# ---------------------------------------------------------------------------

CARD_INVALID = "CARD_INVALID"
CARD_ALREADY_EXISTS = "CARD_ALREADY_EXISTS"
CARD_REQUIRED = "CARD_REQUIRED"
BORROW_LIMIT_EXCEEDED = "BORROW_LIMIT_EXCEEDED"
OVERDUE_LOAN_EXISTS = "OVERDUE_LOAN_EXISTS"
UNPAID_FINE_EXISTS = "UNPAID_FINE_EXISTS"
ITEM_NOT_AVAILABLE = "ITEM_NOT_AVAILABLE"
ITEM_AVAILABLE_NO_RESERVATION = "ITEM_AVAILABLE_NO_RESERVATION"
DUPLICATE_RESERVATION = "DUPLICATE_RESERVATION"
RESERVATION_QUEUE_FULL = "RESERVATION_QUEUE_FULL"
RESERVATION_NOT_CANCELLABLE = "RESERVATION_NOT_CANCELLABLE"
RENEW_LIMIT_EXCEEDED = "RENEW_LIMIT_EXCEEDED"
RENEW_OVERDUE = "RENEW_OVERDUE"
USERNAME_EXISTS = "USERNAME_EXISTS"
ISBN_EXISTS = "ISBN_EXISTS"
INVALID_ISBN = "INVALID_ISBN"
BARCODE_EXISTS = "BARCODE_EXISTS"
FINE_ALREADY_PAID = "FINE_ALREADY_PAID"
LOAN_NOT_FOUND = "LOAN_NOT_FOUND"
ITEM_NOT_FOUND = "ITEM_NOT_FOUND"
CARD_NOT_FOUND = "CARD_NOT_FOUND"
READER_NOT_FOUND = "READER_NOT_FOUND"
TITLE_NOT_FOUND = "TITLE_NOT_FOUND"
ACCOUNT_NOT_FOUND = "ACCOUNT_NOT_FOUND"
RESERVATION_NOT_FOUND = "RESERVATION_NOT_FOUND"
FINE_NOT_FOUND = "FINE_NOT_FOUND"
