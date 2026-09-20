"""`PasswordHasher` / `TokenIssuer` 的适配器实现。

把基础设施的能力**适配**成应用层定义的 Protocol——
这是依赖倒置的落点：应用层只认识 `application/ports/security.py` 的接口，
具体库（bcrypt / PyJWT）只在这里出现。
"""

from __future__ import annotations

from datetime import datetime

from app.infrastructure.security.jwt import create_access_token
from app.infrastructure.security.password import hash_password, verify_password


class BcryptPasswordHasher:
    """`PasswordHasher` 的实现（bcrypt）。"""

    def hash(self, password: str) -> str:
        return hash_password(password)

    def verify(self, password: str, password_hash: str) -> bool:
        return verify_password(password, password_hash)


class JwtTokenIssuer:
    """`TokenIssuer` 的实现（PyJWT，24 小时有效期）。"""

    def issue(self, account_id: int, role: str, username: str = "") -> tuple[str, datetime]:
        return create_access_token(account_id, role, username)


__all__ = ["BcryptPasswordHasher", "JwtTokenIssuer"]
