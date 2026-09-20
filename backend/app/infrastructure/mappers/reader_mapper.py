"""账号相关 Mapper：`readers` / `librarians` / `system_admins` ↔ 领域对象。

`readers` 是**单表继承**，因此重建时由 `ReaderFactory` 按 `reader_type` 分派到
`StudentReader` / `TeacherReader`。
"""

from __future__ import annotations

from datetime import datetime

from app.domain.entities.reader import Librarian, Reader, SystemAdmin
from app.domain.enums import ReaderType
from app.domain.factories import ReaderFactory
from app.infrastructure.mappers._time import to_db
from app.infrastructure.models import LibrarianModel, ReaderModel, SystemAdminModel


class ReaderMapper:
    """`Reader` 继承体系 ↔ `readers` 表。"""

    @staticmethod
    def to_domain(model: ReaderModel) -> Reader:
        fields = {
            "reader_id": model.reader_id,
            "name": model.name,
            "department": model.department,
            "username": model.username,
            "password_hash": model.password_hash,
            "is_deleted": bool(model.is_deleted),
        }
        if ReaderType(model.reader_type) is ReaderType.TEACHER:
            return ReaderFactory.create(ReaderType.TEACHER, **fields)
        return ReaderFactory.create(model.student_type or model.reader_type, **fields)

    @staticmethod
    def to_model(reader: Reader, model: ReaderModel | None = None) -> ReaderModel:
        target = model or ReaderModel()
        target.reader_id = reader.reader_id
        target.name = reader.name
        target.department = reader.department
        target.reader_type = reader.reader_type.value if reader.reader_type else ""
        student_type = getattr(reader, "student_type", None)
        target.student_type = student_type.value if student_type is not None else None
        target.username = reader.username
        target.password_hash = reader.password_hash
        target.is_deleted = 1 if reader.is_deleted else 0
        return target

    @staticmethod
    def sync_timestamps(model: ReaderModel, created_at: datetime | None = None) -> None:
        if created_at is not None:
            model.created_at = to_db(created_at)


class LibrarianMapper:
    """`Librarian` ↔ `librarians` 表。"""

    @staticmethod
    def to_domain(model: LibrarianModel) -> Librarian:
        return Librarian(
            librarian_id=model.librarian_id,
            name=model.name,
            username=model.username,
            password_hash=model.password_hash,
            is_deleted=bool(model.is_deleted),
        )

    @staticmethod
    def to_model(librarian: Librarian, model: LibrarianModel | None = None) -> LibrarianModel:
        target = model or LibrarianModel()
        target.librarian_id = librarian.librarian_id
        target.name = librarian.name
        target.username = librarian.username
        target.password_hash = librarian.password_hash
        target.is_deleted = 1 if librarian.is_deleted else 0
        return target


class SystemAdminMapper:
    """`SystemAdmin` ↔ `system_admins` 表。"""

    @staticmethod
    def to_domain(model: SystemAdminModel) -> SystemAdmin:
        return SystemAdmin(
            admin_id=model.admin_id,
            name=model.name,
            username=model.username,
            password_hash=model.password_hash,
            is_deleted=bool(model.is_deleted),
        )

    @staticmethod
    def to_model(admin: SystemAdmin, model: SystemAdminModel | None = None) -> SystemAdminModel:
        target = model or SystemAdminModel()
        target.admin_id = admin.admin_id
        target.name = admin.name
        target.username = admin.username
        target.password_hash = admin.password_hash
        target.is_deleted = 1 if admin.is_deleted else 0
        return target


__all__ = ["LibrarianMapper", "ReaderMapper", "SystemAdminMapper"]
