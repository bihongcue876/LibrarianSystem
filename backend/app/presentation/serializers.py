"""表现层序列化辅助。

把领域/应用层返回对象里的 `datetime` 统一转成 ISO 8601 字符串（UTC），
避免 DTO 校验失败。

时间约定（`07-architecture.md` §6.5）：**存 UTC，显示北京时间**——
前端拿到带 `+00:00` 的字符串后自行转换。
"""

from __future__ import annotations

from datetime import date, datetime


def iso(value: datetime | date | None) -> str | None:
    """转为 ISO 8601 字符串；`None` 原样返回。"""
    if value is None:
        return None
    return value.isoformat()


def with_iso(payload: dict, *fields: str) -> dict:
    """把指定字段的 `datetime` 转成 ISO 字符串（原地返回新字典）。"""
    result = dict(payload)
    for field in fields:
        if field in result:
            result[field] = iso(result[field])
    return result


__all__ = ["iso", "with_iso"]
