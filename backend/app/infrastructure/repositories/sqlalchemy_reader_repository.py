"""`ReaderRepository` 的 SQLAlchemy 实现。"""

from __future__ import annotations

from typing import Sequence

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.domain.entities.reader import Librarian, Reader, SystemAdmin
from app.domain.enums import ReaderType
from app.infrastructure.mappers import LibrarianMapper, ReaderMapper, SystemAdminMapper
from app.infrastructure.models import LibrarianModel, ReaderModel, SystemAdminModel

ROLE_READER = "READER"
ROLE_LIBRARIAN = "LIBRARIAN"
ROLE_SYSTEM_ADMIN = "SYSTEM_ADMIN"


class SqlAlchemyReaderRepository:
    """实现 `application.ports.ReaderRepository`。只读写，不提交事务。"""

    def __init__(self, session: Session) -> None:
        self._session = session

    # ---- 读者 ------------------------------------------------------------

    def find_by_id(self, reader_id: int) -> Reader | None:
        model = self._session.get(ReaderModel, reader_id)
        return ReaderMapper.to_domain(model) if model else None

    def find_active_by_id(self, reader_id: int) -> Reader | None:
        model = self._session.get(ReaderModel, reader_id)
        if model is None or model.is_deleted:
            return None
        return ReaderMapper.to_domain(model)

    def find_by_username(self, username: str) -> Reader | None:
        model = self._session.scalar(select(ReaderModel).where(ReaderModel.username == username))
        return ReaderMapper.to_domain(model) if model else None

    def list_by_type(self, reader_type: ReaderType) -> Sequence[Reader]:
        models = self._session.scalars(
            select(ReaderModel).where(ReaderModel.reader_type == reader_type.value)
        ).all()
        return [ReaderMapper.to_domain(model) for model in models]

    def add(self, reader: Reader) -> Reader:
        model = ReaderMapper.to_model(reader)
        self._session.add(model)
        self._session.flush()
        reader.reader_id = model.reader_id
        return reader

    def update(self, reader: Reader) -> None:
        if reader.reader_id is None:
            return
        model = self._session.get(ReaderModel, reader.reader_id)
        if model is None:
            return
        ReaderMapper.to_model(reader, model)

    # ---- 图书管理员 ------------------------------------------------------

    def find_librarian_by_id(self, librarian_id: int) -> Librarian | None:
        model = self._session.get(LibrarianModel, librarian_id)
        return LibrarianMapper.to_domain(model) if model else None

    def find_librarian_by_username(self, username: str) -> Librarian | None:
        model = self._session.scalar(
            select(LibrarianModel).where(LibrarianModel.username == username)
        )
        return LibrarianMapper.to_domain(model) if model else None

    def add_librarian(self, librarian: Librarian) -> Librarian:
        model = LibrarianMapper.to_model(librarian)
        self._session.add(model)
        self._session.flush()
        librarian.librarian_id = model.librarian_id
        return librarian

    def update_librarian(self, librarian: Librarian) -> None:
        if librarian.librarian_id is None:
            return
        model = self._session.get(LibrarianModel, librarian.librarian_id)
        if model is None:
            return
        LibrarianMapper.to_model(librarian, model)

    def list_librarians(self, include_deleted: bool = False) -> Sequence[Librarian]:
        statement = select(LibrarianModel)
        if not include_deleted:
            statement = statement.where(LibrarianModel.is_deleted == 0)
        models = self._session.scalars(statement).all()
        return [LibrarianMapper.to_domain(model) for model in models]

    # ---- 系统管理员 ------------------------------------------------------

    def find_admin_by_username(self, username: str) -> SystemAdmin | None:
        model = self._session.scalar(
            select(SystemAdminModel).where(SystemAdminModel.username == username)
        )
        return SystemAdminMapper.to_domain(model) if model else None

    def find_admin_by_id(self, admin_id: int) -> SystemAdmin | None:
        model = self._session.get(SystemAdminModel, admin_id)
        return SystemAdminMapper.to_domain(model) if model else None

    def add_admin(self, admin: SystemAdmin) -> SystemAdmin:
        model = SystemAdminMapper.to_model(admin)
        self._session.add(model)
        self._session.flush()
        admin.admin_id = model.admin_id
        return admin

    def count_active_admins(self) -> int:
        return int(
            self._session.scalar(
                select(func.count())
                .select_from(SystemAdminModel)
                .where(SystemAdminModel.is_deleted == 0)
            )
            or 0
        )

    # ---- 登录入口 --------------------------------------------------------

    def find_account_by_username(
        self, username: str, role: str
    ) -> Reader | Librarian | SystemAdmin | None:
        """按角色入口查找账号（BR-044：三类账号可同名，须按入口区分）。"""
        if role == ROLE_SYSTEM_ADMIN:
            return self.find_admin_by_username(username)
        if role == ROLE_LIBRARIAN:
            return self.find_librarian_by_username(username)
        return self.find_by_username(username)
