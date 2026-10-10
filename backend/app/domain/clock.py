"""统一时钟（全后端唯一的 `utc_now` 定义）。

时间约定（`07-architecture.md` §6.5）：**存 UTC，显示北京时间**。
领域实体、领域服务与应用服务一律从本模块取当前时刻，
便于未来注入假时钟做测试（本课程项目暂以模块函数 + `now` 参数透传的方式实现）。
"""

from __future__ import annotations

from datetime import datetime, timezone


def utc_now() -> datetime:
    """当前 UTC 时刻（带时区）。"""
    return datetime.now(timezone.utc)
