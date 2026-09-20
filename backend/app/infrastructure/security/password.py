"""密码哈希（bcrypt）。

BR-045：密码使用 bcrypt 哈希存储，长度 6-24 位，无复杂度要求。
NFR-004：严禁明文或 MD5 等弱摘要。
"""

from __future__ import annotations

import os

import bcrypt

MIN_PASSWORD_LENGTH = 6
MAX_PASSWORD_LENGTH = 24

#: bcrypt cost factor。生产保持 12；**测试可经环境变量调低**以避免拖慢测试套件
#: （每个哈希约 0.3s，几十个用例就会累积到分钟级）。
BCRYPT_ROUNDS = int(os.environ.get("LIBRARY_BCRYPT_ROUNDS", "12"))


def validate_password_length(password: str) -> None:
    """长度校验（6-24 位，BR-045）。"""
    if not isinstance(password, str):
        raise ValueError("密码必须是字符串")
    if not MIN_PASSWORD_LENGTH <= len(password) <= MAX_PASSWORD_LENGTH:
        raise ValueError(
            f"密码长度须在 {MIN_PASSWORD_LENGTH}-{MAX_PASSWORD_LENGTH} 位之间"
        )


def hash_password(password: str) -> str:
    """生成 bcrypt 哈希（固定 60 字符，与 `readers.password_hash VARCHAR(60)` 对齐）。"""
    validate_password_length(password)
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt(rounds=BCRYPT_ROUNDS)).decode(
        "utf-8"
    )


def verify_password(password: str, password_hash: str) -> bool:
    """校验密码。哈希非法或为空时返回 False，不抛异常（避免泄露信息）。"""
    if not password or not password_hash:
        return False
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except (ValueError, TypeError):
        return False
