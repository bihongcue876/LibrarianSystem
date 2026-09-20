"""`AuthService`（`09-design-model.md` §1.2）。

认证与账号生命周期：登录、读者注册、员工账号增删、密码重置。

**职责边界**：只做「取数据 → 调领域对象 → 落库 → 组装结果」，不做业务判定。
事务边界收归本层（宪法第九条）。

**依赖**：本服务只依赖 `application/ports` 定义的接口（Repository Protocol 与
`PasswordHasher` / `TokenIssuer`），**不依赖任何基础设施实现**（包图规则 R-2）。
具体实现由 `presentation/dependencies.py` 在装配时注入。
"""

from __future__ import annotations

from app.application.exceptions import ForbiddenError, UnauthorizedError
from app.application.ports import PasswordHasher, ReaderRepository, TokenIssuer
from app.application.unit_of_work import UnitOfWork
from app.domain.entities.reader import Librarian, Reader, SystemAdmin
from app.domain.enums import ReaderType
from app.domain.exceptions import ConflictError, NotFoundError, ValidationError
from app.domain.factories import ReaderFactory

ROLE_READER = "READER"
ROLE_LIBRARIAN = "LIBRARIAN"
ROLE_SYSTEM_ADMIN = "SYSTEM_ADMIN"


class AuthService:
    """认证与账号管理应用服务。"""

    def __init__(
        self,
        uow: UnitOfWork,
        readers: ReaderRepository,
        hasher: PasswordHasher,
        tokens: TokenIssuer,
    ) -> None:
        self._uow = uow
        self._readers = readers
        self._hasher = hasher
        self._tokens = tokens

    # ---- 登录 ------------------------------------------------------------

    def login(self, username: str, password: str, role: str = ROLE_READER) -> dict:
        """登录并签发 24 小时有效的 JWT（FR-001、BR-046、BR-047）。

        失败一律返回同一提示，**不区分**用户名不存在与密码错误。
        """
        account = self._readers.find_account_by_username(username, role)
        if account is None or getattr(account, "is_deleted", False):
            raise UnauthorizedError()
        if not self._hasher.verify(password, account.password_hash):
            raise UnauthorizedError()
        account_id = _account_id(account)
        token, expires_at = self._tokens.issue(account_id, role, username)
        return {
            "access_token": token,
            "token_type": "bearer",
            "role": role,
            "account_id": account_id,
            "username": username,
            "expires_at": expires_at,
        }

    # ---- 注册 ------------------------------------------------------------

    def register_reader(
        self,
        username: str,
        password: str,
        name: str,
        department: str,
        reader_type: ReaderType | str,
    ) -> Reader:
        """读者自助注册（FR-002）。

        注册后**不具备借阅资格**，须由系统管理员办理借阅证（BR-012）。
        用户名**全局唯一且软删除不释放**（Q-03 裁定）。
        """
        try:
            key = ReaderType(reader_type)
        except ValueError as exc:
            raise ValidationError(
                f"未知的读者类型: {reader_type}", code="INVALID_PARAMETER"
            ) from exc

        if self._readers.find_by_username(username) is not None:
            raise ConflictError(f"用户名 {username} 已被占用", code="USERNAME_EXISTS")

        reader = ReaderFactory.create(
            key,
            name=name,
            department=department,
            username=username,
            password_hash=self._hasher.hash(password),
        )
        with self._uow:
            self._readers.add(reader)
            self._uow.commit()
        return reader

    # ---- 员工账号 --------------------------------------------------------

    def add_librarian(self, username: str, password: str, name: str) -> Librarian:
        """系统管理员创建图书管理员账号（FR-003）。"""
        if self._readers.find_librarian_by_username(username) is not None:
            raise ConflictError(f"用户名 {username} 已被占用", code="USERNAME_EXISTS")
        librarian = Librarian(
            name=name, username=username, password_hash=self._hasher.hash(password)
        )
        with self._uow:
            self._readers.add_librarian(librarian)
            self._uow.commit()
        return librarian

    def delete_librarian(self, librarian_id: int) -> None:
        """软删除图书管理员（FR-003、FR-004、BR-043）。

        系统管理员账号**不可**通过本接口删除（系统管理员之间不可互相删除）。
        """
        librarian = self._readers.find_librarian_by_id(librarian_id)
        if librarian is None:
            raise NotFoundError("账号不存在", code="ACCOUNT_NOT_FOUND")
        if librarian.is_deleted:
            raise NotFoundError("账号不存在", code="ACCOUNT_NOT_FOUND")
        librarian.is_deleted = True
        with self._uow:
            self._readers.update_librarian(librarian)
            self._uow.commit()

    def list_librarians(self, include_deleted: bool = False) -> list[Librarian]:
        return list(self._readers.list_librarians(include_deleted=include_deleted))

    # ---- 密码重置（Q-05 裁定） ------------------------------------------

    def reset_password(self, account_id: int, new_password: str, role: str = ROLE_READER) -> None:
        """系统管理员重置账号密码（FR-003 验收标准 5）。

        系统**不提供自助找回密码**功能。
        """
        with self._uow:
            if role == ROLE_LIBRARIAN:
                librarian = self._readers.find_librarian_by_id(account_id)
                if librarian is None:
                    raise NotFoundError("账号不存在", code="ACCOUNT_NOT_FOUND")
                librarian.password_hash = self._hasher.hash(new_password)
                self._readers.update_librarian(librarian)
            else:
                reader = self._readers.find_by_id(account_id)
                if reader is None:
                    raise NotFoundError("账号不存在", code="ACCOUNT_NOT_FOUND")
                reader.password_hash = self._hasher.hash(new_password)
                self._readers.update(reader)
            self._uow.commit()

    # ---- 校验辅助 --------------------------------------------------------

    def require_system_admin(self, account) -> SystemAdmin:
        if not isinstance(account, SystemAdmin):
            raise ForbiddenError("仅系统管理员可执行该操作")
        return account

    def require_librarian_or_admin(self, account):
        if not isinstance(account, (Librarian, SystemAdmin)):
            raise ForbiddenError("仅图书管理员或系统管理员可执行该操作")
        return account


def _account_id(account) -> int:
    for attr in ("reader_id", "librarian_id", "admin_id"):
        value = getattr(account, attr, None)
        if value is not None:
            return int(value)
    raise UnauthorizedError()
