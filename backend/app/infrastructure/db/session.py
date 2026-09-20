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
    """构造默认 SQLite 连接串。

    **路径必须规范化为正斜杠**：本项目工作区路径含中文与全角冒号
    （`D:\\我的文件：D盘\\...`），反斜杠与 POSIX 风格路径（`/d/...`）
    都会让 SQLite 报 `unable to open database file`。
    故统一用 `Path.as_posix()` 转成 `D:/...` 形态。
    """
    base_dir = Path(__file__).resolve().parents[3]  # backend/
    raw = os.environ.get("LIBRARY_DB_PATH")
    db_path = Path(raw).resolve() if raw else (base_dir / DEFAULT_DB_FILENAME).resolve()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    return f"sqlite:///{db_path.as_posix()}"


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
