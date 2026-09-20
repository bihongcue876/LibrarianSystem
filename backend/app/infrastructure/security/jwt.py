"""JWT 签发与解析（简化版）。

BR-046：Token 有效期 **24 小时**，**不提供** refresh token，过期需重新登录。

Token 载荷：

```json
{"sub": "<account_id>", "role": "READER", "username": "...", "exp": 1234567890}
```
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from typing import Any

import jwt

ALGORITHM = "HS256"
TOKEN_TTL_HOURS = 24

#: 生产环境必须通过环境变量注入；此处默认值仅用于课程演示
SECRET_KEY = os.environ.get("LIBRARY_JWT_SECRET", "dev-secret-change-me-in-production")


def create_access_token(account_id: int, role: str, username: str = "") -> tuple[str, datetime]:
    """签发 Token，返回 `(token, 过期时刻)`。"""
    expires_at = datetime.now(timezone.utc) + timedelta(hours=TOKEN_TTL_HOURS)
    payload: dict[str, Any] = {
        "sub": str(account_id),
        "role": role,
        "username": username,
        "exp": expires_at,
        "iat": datetime.now(timezone.utc),
    }
    token = jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)
    return token, expires_at


def decode_token(token: str) -> dict[str, Any]:
    """解析 Token。过期或非法时抛 `jwt.PyJWTError` 的子类，由调用方转成 401。"""
    return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
