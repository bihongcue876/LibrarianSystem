"""共享测试夹具。

**隔离策略**：每个测试用**独立的内存 SQLite 库**（`StaticPool` 保证同一连接），
通过覆盖 `get_session` 依赖把应用指向测试库。测试之间互不影响，可重复运行。

**测试分层**（`15-test-plan.md` §1.1）：

- `tests/unit/` —— 领域层，**不依赖数据库与 Web 框架**
- `tests/integration/` —— API 端到端
"""

from __future__ import annotations

import os

# 必须在导入应用模块之前设置：`password.py` 在导入时读取该环境变量。
# 这是**测试专用**加速手段，不改变生产强度（生产仍为 bcrypt cost 12）。
os.environ.setdefault("LIBRARY_BCRYPT_ROUNDS", "4")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import Session, sessionmaker  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

from app.infrastructure.db.base import Base  # noqa: E402
from app.infrastructure.db.session import get_session  # noqa: E402
from app.infrastructure.models import (  # noqa: E402
    BorrowPolicyModel,
    FineRuleModel,
    LibrarianModel,
    SystemAdminModel,
    load_all_models,
)
from app.infrastructure.security.password import hash_password  # noqa: E402
from app.main import app  # noqa: E402
from scripts.init_db import BORROW_POLICY_SEED, FINE_RULE_SEED  # noqa: E402

ADMIN_PASSWORD = "admin12345"
LIBRARIAN_PASSWORD = "lib123456"
READER_PASSWORD = "reader123"


@pytest.fixture()
def engine():
    """每个测试一个独立的内存库。"""
    test_engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    load_all_models()
    Base.metadata.create_all(bind=test_engine)
    yield test_engine
    Base.metadata.drop_all(bind=test_engine)
    test_engine.dispose()


@pytest.fixture()
def session_factory(engine) -> sessionmaker:
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False, future=True)


@pytest.fixture()
def session(session_factory) -> Session:
    db = session_factory()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture()
def seeded(session) -> Session:
    """播种规则、系统管理员、图书管理员。"""
    for reader_type, max_count, days in BORROW_POLICY_SEED:
        session.add(
            BorrowPolicyModel(
                reader_type=reader_type, max_borrow_count=max_count, borrow_days=days
            )
        )
    for item_type, price, grace, cap in FINE_RULE_SEED:
        session.add(
            FineRuleModel(
                item_type=item_type, daily_price=price, grace_days=grace, max_amount=cap
            )
        )
    session.add(
        SystemAdminModel(
            name="系统管理员", username="admin", password_hash=hash_password(ADMIN_PASSWORD)
        )
    )
    session.add(
        LibrarianModel(
            name="图书管理员",
            username="librarian",
            password_hash=hash_password(LIBRARIAN_PASSWORD),
        )
    )
    session.commit()
    return session


@pytest.fixture()
def client(seeded, session_factory) -> TestClient:
    """覆盖 `get_session`，把应用指向测试库。"""
    db_factory = session_factory

    def override_get_session():
        db = db_factory()
        try:
            yield db
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    app.dependency_overrides[get_session] = override_get_session
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# 登录辅助
# ---------------------------------------------------------------------------

def login(client: TestClient, username: str, password: str, role: str = "READER") -> str:
    response = client.post(
        "/api/auth/login", json={"username": username, "password": password, "role": role}
    )
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


def auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture()
def admin_token(client) -> str:
    return login(client, "admin", ADMIN_PASSWORD, "SYSTEM_ADMIN")


@pytest.fixture()
def librarian_token(client) -> str:
    return login(client, "librarian", LIBRARIAN_PASSWORD, "LIBRARIAN")


@pytest.fixture()
def reader_token(client) -> str:
    """注册一名读者并返回其 Token（本科，5 册 / 30 天）。"""
    client.post(
        "/api/auth/register",
        json={
            "username": "reader001",
            "password": READER_PASSWORD,
            "name": "张三",
            "department": "计算机学院",
            "reader_type": "UNDERGRADUATE",
        },
    )
    return login(client, "reader001", READER_PASSWORD, "READER")


@pytest.fixture()
def graduate_setup(client, admin_token, librarian_token) -> dict:
    """准备一个研究生读者（10 册 / 60 天）+ 有效借阅证 + 一个题录与副本。

    返回各对象 ID 与 Token，供借书/还书类测试复用。
    """
    client.post(
        "/api/auth/register",
        json={
            "username": "grad001",
            "password": READER_PASSWORD,
            "name": "李四",
            "department": "软件学院",
            "reader_type": "GRADUATE",
        },
    )
    reader_id = _reader_id(client, admin_token, "grad001")
    card = client.post(
        "/api/admin/borrow-cards", json={"reader_id": reader_id}, headers=auth(admin_token)
    ).json()
    title = client.post(
        "/api/admin/book-titles",
        json={
            "title": "算法导论",
            "author": "Cormen",
            "isbn": "9780262046305",
            "publisher": "MIT Press",
            "publish_year": 2022,
            "item_type": "FOREIGN_BOOK",
        },
        headers=auth(admin_token),
    ).json()
    item = client.post(
        "/api/admin/library-items",
        json={"title_id": title["title_id"], "location": "A-3-12", "price": "128.00"},
        headers=auth(admin_token),
    ).json()
    return {
        "reader_id": reader_id,
        "reader_token": login(client, "grad001", READER_PASSWORD, "READER"),
        "card_no": card["card_no"],
        "title_id": title["title_id"],
        "barcode": item["barcode"],
        "item_id": item["item_id"],
    }


def _reader_id(client: TestClient, admin_token: str, username: str) -> int:
    """通过借阅证接口不便取 reader_id，故直接用登录接口返回的 account_id。"""
    response = client.post(
        "/api/auth/login", json={"username": username, "password": READER_PASSWORD, "role": "READER"}
    )
    assert response.status_code == 200, response.text
    return int(response.json()["account_id"])


def register_reader(
    client: TestClient,
    username: str,
    reader_type: str = "UNDERGRADUATE",
    password: str = READER_PASSWORD,
) -> int:
    """注册读者，返回其 `reader_id`。"""
    response = client.post(
        "/api/auth/register",
        json={
            "username": username,
            "password": password,
            "name": f"读者-{username}",
            "department": "测试学院",
            "reader_type": reader_type,
        },
    )
    assert response.status_code == 201, response.text
    return int(response.json()["account_id"])


def issue_card(client: TestClient, admin_token: str, reader_id: int) -> dict:
    response = client.post(
        "/api/admin/borrow-cards", json={"reader_id": reader_id}, headers=auth(admin_token)
    )
    assert response.status_code == 201, response.text
    return response.json()


def add_title(
    client: TestClient,
    admin_token: str,
    title: str = "测试图书",
    item_type: str = "FOREIGN_BOOK",
    isbn: str | None = None,
) -> dict:
    payload: dict = {"title": title, "author": "作者", "item_type": item_type}
    if isbn:
        payload["isbn"] = isbn
    response = client.post("/api/admin/book-titles", json=payload, headers=auth(admin_token))
    assert response.status_code == 201, response.text
    return response.json()


def add_item(client: TestClient, admin_token: str, title_id: int) -> dict:
    response = client.post(
        "/api/admin/library-items", json={"title_id": title_id}, headers=auth(admin_token)
    )
    assert response.status_code == 201, response.text
    return response.json()


def borrow(
    client: TestClient, librarian_token: str, card_no: str, barcode: str
):
    return client.post(
        "/api/circulation/borrow",
        json={"card_no": card_no, "barcode": barcode},
        headers=auth(librarian_token),
    )


def return_book(client: TestClient, librarian_token: str, barcode: str):
    return client.post(
        "/api/circulation/return", json={"barcode": barcode}, headers=auth(librarian_token)
    )


def force_overdue(session, loan_id: int, days: int) -> None:
    """把某条借阅记录改为「已超期 `days` 天」，用于构造超期场景。

    实现方式是把 `due_at` 设为**当前时刻往前 `days` 天**（绝对值），
    不能写成"在现有 `due_at` 上减几天"——那样对于借期 60 天的记录，
    减去少量天数后应还日仍在未来，并不会真的超期。

    `borrowed_at` 同步前移，以满足 `CHECK (due_at > borrowed_at)`。

    直接改库是**测试专用**手段——`due_at` 在业务上不可修改（它是借出时的快照，BR-050）。
    """
    from datetime import datetime, timedelta, timezone

    from app.infrastructure.mappers._time import to_db
    from app.infrastructure.models import LoanModel

    model = session.get(LoanModel, loan_id)
    assert model is not None, f"借阅记录 {loan_id} 不存在"

    moment = datetime.now(timezone.utc)
    model.due_at = to_db(moment - timedelta(days=days))
    model.borrowed_at = to_db(moment - timedelta(days=days + 30))
    session.commit()


def loan_rows(session) -> list:
    from app.infrastructure.models import LoanModel

    return list(session.query(LoanModel).all())


__all__ = [
    "ADMIN_PASSWORD",
    "LIBRARIAN_PASSWORD",
    "READER_PASSWORD",
    "add_item",
    "add_title",
    "auth",
    "borrow",
    "force_overdue",
    "issue_card",
    "loan_rows",
    "login",
    "register_reader",
    "return_book",
]
