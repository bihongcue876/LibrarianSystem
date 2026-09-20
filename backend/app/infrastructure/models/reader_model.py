"""账号相关 ORM 模型：`readers`、`librarians`、`system_admins`
（`13-database-design.md` §4.1 ~ §4.3）。

`readers` 承载 `Reader` ← `StudentReader` / `TeacherReader` 的**单表继承**（D-49），
判别字段为 `reader_type`。
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Integer,
    String,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.db.base import Base, EnumText

READER_TYPES = "'COLLEGE','UNDERGRADUATE','GRADUATE','DOCTOR','TEACHER'"
STUDENT_TYPES = "'COLLEGE','UNDERGRADUATE','GRADUATE','DOCTOR'"


class ReaderModel(Base):
    """`readers` 表。"""

    __tablename__ = "readers"

    reader_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    department: Mapped[str] = mapped_column(String(128), nullable=False)
    reader_type: Mapped[str] = mapped_column(EnumText(20), nullable=False)
    student_type: Mapped[str | None] = mapped_column(EnumText(20), nullable=True)
    username: Mapped[str] = mapped_column(String(32), nullable=False, unique=True)
    password_hash: Mapped[str] = mapped_column(String(60), nullable=False)
    is_deleted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="0")
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
    updated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    __table_args__ = (
        CheckConstraint(f"reader_type IN ({READER_TYPES})", name="ck_readers_reader_type"),
        CheckConstraint(
            f"student_type IS NULL OR student_type IN ({STUDENT_TYPES})",
            name="ck_readers_student_type",
        ),
        # 学生读者必有 student_type，教师必无
        CheckConstraint(
            "(reader_type = 'TEACHER' AND student_type IS NULL) "
            "OR (reader_type <> 'TEACHER' AND student_type IS NOT NULL)",
            name="ck_readers_student_type_required",
        ),
    )


class LibrarianModel(Base):
    """`librarians` 表。**不继承** `readers`（06 §10.2），故独立建表。"""

    __tablename__ = "librarians"

    librarian_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    username: Mapped[str] = mapped_column(String(32), nullable=False, unique=True)
    password_hash: Mapped[str] = mapped_column(String(60), nullable=False)
    is_deleted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="0")
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
    updated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class SystemAdminModel(Base):
    """`system_admins` 表。**仅由初始化脚本创建**（决策 D-04）。"""

    __tablename__ = "system_admins"

    admin_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    username: Mapped[str] = mapped_column(String(32), nullable=False, unique=True)
    password_hash: Mapped[str] = mapped_column(String(60), nullable=False)
    is_deleted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="0")
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
    updated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
