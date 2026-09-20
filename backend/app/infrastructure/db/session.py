"""数据库会话工厂。

默认使用 SQLite 文件库；测试可注入内存库（见 `tests/conftest.py`）。
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

DEFAULT_DB_FILENAME = "library.db"


def _default_url() -> str:
    base_dir = Path(__file__).resolve().parents[3]  # backend/
    db_path = os.environ.get("LIBRARY_DB_PATH", str(base_dir / DEFAULT_DB_FILENAME))
    return f"sqlite:///{db_path}"


DATABASE_URL = os.environ.get("LIBRARY_DATABASE_URL") or _default_url()

engine: Engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},
    future=True,
)


@event.listens_for(engine, "connect")
def _enable_sqlite_foreign_keys(dbapi_connection, connection_record) -> None:  # pragma: no cover
    """SQLite 默认不强制外键，需显式开启。"""
    cursor = dbapi_connection.cursor()
    try:
        cursor.execute("PRAGMA foreign_keys=ON")
    finally:
        cursor.close()


SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False, future=True)


def get_session() -> Iterator[Session]:
    """FastAPI 依赖：每请求一个会话，异常回滚。

    **注意**：事务提交的最终决定权在应用服务（`UnitOfWork`），
    本依赖只负责会话生命周期与失败回滚。
    """
    session = SessionLocal()
    try:
        yield session
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def create_all() -> None:
    """建表（初始化脚本与测试使用）。"""
    from app.infrastructure.models import load_all_models  # noqa: PLC0415

    load_all_models()
    from app.infrastructure.db.base import Base  # noqa: PLC0415

    Base.metadata.create_all(bind=engine)
