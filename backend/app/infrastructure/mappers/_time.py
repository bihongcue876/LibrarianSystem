"""时间转换辅助（Mapper 专用）。

**为什么需要**：领域层使用**带时区**的 UTC `datetime`（`datetime.now(timezone.utc)`），
而 SQLite 的 `DATETIME` 列存的是**朴素**时间字符串。若不做转换，
从库里读出的 `due_at` 是 naive，与领域层的 aware `now` 比较会抛
`TypeError: can't compare offset-naive and offset-aware datetimes`。

约定（`07-architecture.md` §6.5）：**存 UTC（naive 形态），显示北京时间**。
"""

from __future__ import annotations

from datetime import date, datetime, timezone


def to_db(moment: datetime | None) -> datetime | None:
    """领域 → 数据库：转为 naive UTC。"""
    if moment is None:
        return None
    if moment.tzinfo is None:
        return moment
    return moment.astimezone(timezone.utc).replace(tzinfo=None)


def to_domain(moment: datetime | None) -> datetime | None:
    """数据库 → 领域：补上 UTC 时区。"""
    if moment is None:
        return None
    if moment.tzinfo is not None:
        return moment.astimezone(timezone.utc)
    return moment.replace(tzinfo=timezone.utc)


def date_to_domain(value: date | None) -> date | None:
    """日期列（无时区问题），保持原样。"""
    return value
