"""`ReaderRepository` 接口（读者与两类员工账号）。"""

from __future__ import annotations

from typing import Protocol, Sequence, runtime_checkable

from app.domain.entities.reader import Librarian, Reader, SystemAdmin
from app.domain.enums import ReaderType


@runtime_checkable
class ReaderRepository(Protocol):
    """读者与账号的持久化接口。"""

    # ---- 读者 ------------------------------------------------------------

    def find_by_id(self, reader_id: int) -> Reader | None:
        """按 ID 取读者。**含已软删除**（调用方自行判断 `is_deleted`）。"""

    def find_active_by_id(self, reader_id: int) -> Reader | None:
        """按 ID 取未软删除的读者。"""

    def find_by_username(self, username: str) -> Reader | None:
        """按用户名取读者（用户名全局唯一，软删除不释放，Q-03）。"""

    def list_by_type(self, reader_type: ReaderType) -> Sequence[Reader]:
        """按读者类型列出读者。"""

    def add(self, reader: Reader) -> Reader:
        """新增读者，返回带自增 ID 的实体。"""

    def update(self, reader: Reader) -> None:
        """更新读者。"""

    # ---- 图书管理员 ------------------------------------------------------

    def find_librarian_by_id(self, librarian_id: int) -> Librarian | None: ...

    def find_librarian_by_username(self, username: str) -> Librarian | None: ...

    def add_librarian(self, librarian: Librarian) -> Librarian: ...

    def update_librarian(self, librarian: Librarian) -> None: ...

    def list_librarians(self, include_deleted: bool = False) -> Sequence[Librarian]: ...

    # ---- 系统管理员 ------------------------------------------------------

    def find_admin_by_username(self, username: str) -> SystemAdmin | None: ...

    def find_admin_by_id(self, admin_id: int) -> SystemAdmin | None: ...

    def add_admin(self, admin: SystemAdmin) -> SystemAdmin: ...

    def count_active_admins(self) -> int:
        """统计可用系统管理员数量（BR-043：至少保留一个）。"""

    def find_account_by_username(self, username: str, role: str) -> Reader | Librarian | SystemAdmin | None:
        """按角色入口查找账号（登录用）。"""
