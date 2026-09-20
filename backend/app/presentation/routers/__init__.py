"""路由包（Controller 层，`07-architecture.md` §3.1 MVC 映射）。

| 路由模块 | 对应实验文档建议名 | 说明 |
|---|---|---|
| `auth_router` | — | 登录、注册、员工账号 |
| `card_router` | `AdminController`（借阅证部分） | 借阅证管理 |
| `catalog_router` | `AdminController`（书目馆藏部分） | 题录与副本管理 |
| `circulation_router` | `LibrarianController` + `ReaderController`（查询部分） | 借书、还书、续借、罚款、借阅查询 |
| `reservation_router` | `ReaderController`（预约部分） | 预约 |
| `query_router` | `ReaderController`（检索部分） | 图书检索、馆藏统计 |
| `policy_router` | `AdminController`（规则部分） | 规则查询与维护 |

本项目路由按**限界上下文**划分而非按角色划分，角色差异由 `require_role` 守卫区分。
"""

from app.presentation.routers import (
    auth_router,
    card_router,
    catalog_router,
    circulation_router,
    policy_router,
    query_router,
    reservation_router,
)

ALL_ROUTERS = (
    auth_router.router,
    card_router.router,
    catalog_router.router,
    circulation_router.router,
    reservation_router.router,
    query_router.router,
    policy_router.router,
)

__all__ = [
    "ALL_ROUTERS",
    "auth_router",
    "card_router",
    "catalog_router",
    "circulation_router",
    "policy_router",
    "query_router",
    "reservation_router",
]
