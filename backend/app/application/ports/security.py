"""安全能力接口（Ports）——`07-architecture.md` 包图规则 R-2。

**为什么需要这一层**：应用层需要「校验密码」「签发 Token」两项能力，
但具体实现（bcrypt、JWT 库）属于基础设施关注点。
若 `application/services/auth_service.py` 直接 `import app.infrastructure.security`，
就违反了 R-2（应用层不得依赖基础设施层的具体类）。

因此这里以 Protocol 形式声明**应用层需要的能力**，
由 `presentation/dependencies.py` 在装配时绑定具体实现（依赖倒置）。
"""

from __future__ import annotations

from datetime import datetime
from typing import Protocol, runtime_checkable


@runtime_checkable
class PasswordHasher(Protocol):
    """密码哈希能力。"""

    def hash(self, password: str) -> str:
        """生成哈希（bcrypt，固定 60 字符）。"""

    def verify(self, password: str, password_hash: str) -> bool:
        """校验密码。哈希非法时返回 `False`，不抛异常。"""


@runtime_checkable
class TokenIssuer(Protocol):
    """JWT 签发能力。"""

    def issue(self, account_id: int, role: str, username: str = "") -> tuple[str, datetime]:
        """签发 Token，返回 `(token, 过期时刻)`。"""
