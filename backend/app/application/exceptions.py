"""应用层异常（`09-design-model.md` §10）。

与领域异常并列，共同由 `main.py` 的全局异常处理器映射为 `ErrorResponse`。
"""

from __future__ import annotations

from typing import Any


class ApplicationError(Exception):
    """应用层异常基类。"""

    code: str = "APPLICATION_ERROR"
    http_status: int = 500

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
        return {"code": self.code, "message": self.message, "detail": self.detail}


class UnauthorizedError(ApplicationError):
    """未登录、Token 过期或凭据错误。

    BR-047：登录失败提示统一为"用户名或密码错误"，**不区分**用户名不存在与密码错误。
    """

    code = "UNAUTHORIZED"
    http_status = 401

    def __init__(self, message: str = "用户名或密码错误", **kwargs: Any) -> None:
        super().__init__(message, **kwargs)


class ForbiddenError(ApplicationError):
    """角色越权或读者访问他人数据（BR-039、BR-042）。"""

    code = "PERMISSION_DENIED"
    http_status = 403

    def __init__(self, message: str = "无权执行该操作", **kwargs: Any) -> None:
        super().__init__(message, **kwargs)
