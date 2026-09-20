"""权限集成测试（TC-031、TC-032，BR-040 ~ BR-044）。

**核心断言**：权限校验必须在**服务端**完成，不得依赖前端隐藏按钮（BR-042）。
"""

from __future__ import annotations

import pytest

from tests.conftest import add_item, add_title, auth, issue_card, register_reader


def _call(client, method: str, url: str, body, headers: dict):
    """统一的请求分发。

    `httpx` 的 `get()` **不接受** `json` 关键字，故必须按方法分流；
    这与权限无关，纯属测试客户端 API 的差异。
    """
    if method == "get":
        return client.get(url, headers=headers)
    return getattr(client, method)(url, json=body, headers=headers)


class TestReaderCannotUseAdminEndpoints:
    """TC-031 普通读者不能执行管理员操作。"""

    @pytest.fixture()
    def reader(self, client, admin_token):
        reader_id = register_reader(client, "reader130")
        issue_card(client, admin_token, reader_id)
        token = client.post(
            "/api/auth/login",
            json={"username": "reader130", "password": "reader123", "role": "READER"},
        ).json()["access_token"]
        return {"id": reader_id, "token": token}

    @pytest.mark.parametrize(
        "method,url,body",
        [
            ("post", "/api/admin/book-titles", {"title": "越权", "author": "x",
                                                "item_type": "CHINESE_BOOK"}),
            ("post", "/api/admin/library-items", {"title_id": 1}),
            ("post", "/api/admin/librarians", {"username": "hack", "password": "hack1234",
                                               "name": "越权"}),
            ("post", "/api/admin/borrow-cards", {"reader_id": 1}),
            ("put", "/api/admin/policies/borrow", {"reader_type": "TEACHER",
                                                   "max_borrow_count": 99, "borrow_days": 99}),
            ("put", "/api/admin/policies/fine", {"item_type": "THESIS", "daily_price": "0.01",
                                                 "grace_days": 0, "max_amount": "1.00"}),
            ("get", "/api/admin/collection-stats", None),
            ("get", "/api/admin/librarians", None),
        ],
    )
    def test_all_admin_endpoints_forbidden(self, client, reader, method, url, body):
        response = _call(client, method, url, body, auth(reader["token"]))
        assert response.status_code == 403, f"{method.upper()} {url} 未拒绝读者"
        assert response.json()["error"]["code"] == "PERMISSION_DENIED"

    def test_reader_cannot_borrow(self, client, reader, admin_token):
        """BR-040：借书必须由馆员代理，读者调用返回 403。"""
        title = add_title(client, admin_token, title="读者不能借")
        item = add_item(client, admin_token, title["title_id"])
        response = client.post(
            "/api/circulation/borrow",
            json={"card_no": "CARD2026000001", "barcode": item["barcode"]},
            headers=auth(reader["token"]),
        )
        assert response.status_code == 403

    def test_reader_cannot_return(self, client, reader):
        response = client.post(
            "/api/circulation/return",
            json={"barcode": "BC00000001"},
            headers=auth(reader["token"]),
        )
        assert response.status_code == 403

    def test_reader_cannot_precheck(self, client, reader):
        response = client.post(
            "/api/circulation/precheck",
            json={"card_no": "CARD2026000001", "barcode": "BC00000001"},
            headers=auth(reader["token"]),
        )
        assert response.status_code == 403

    def test_reader_cannot_collect_fine(self, client, reader):
        response = client.post("/api/fines/1/collect", headers=auth(reader["token"]))
        assert response.status_code == 403

    def test_no_side_effects_from_forbidden_attempts(self, client, reader, admin_token, session):
        """越权请求被拒后，数据库不得留下任何痕迹。"""
        from sqlalchemy import select

        from app.infrastructure.models import BookTitleModel

        before = len(session.scalars(select(BookTitleModel)).all())
        client.post(
            "/api/admin/book-titles",
            json={"title": "越权书", "author": "x", "item_type": "CHINESE_BOOK"},
            headers=auth(reader["token"]),
        )
        after = len(session.scalars(select(BookTitleModel)).all())
        assert before == after

    def test_reader_can_use_own_endpoints(self, client, reader):
        assert client.get("/api/me/loans", headers=auth(reader["token"])).status_code == 200
        assert client.get("/api/me/fines", headers=auth(reader["token"])).status_code == 200
        assert client.get("/api/me/reservations", headers=auth(reader["token"])).status_code == 200


class TestLibrarianCannotUseAdminEndpoints:
    """TC-032 图书管理员不能执行系统管理员操作（BR-041）。"""

    @pytest.mark.parametrize(
        "method,url,body",
        [
            ("post", "/api/admin/borrow-cards", {"reader_id": 1}),
            ("post", "/api/admin/book-titles", {"title": "越权", "author": "x",
                                                "item_type": "CHINESE_BOOK"}),
            ("post", "/api/admin/library-items", {"title_id": 1}),
            ("put", "/api/admin/policies/fine", {"item_type": "THESIS", "daily_price": "0.01",
                                                 "grace_days": 0, "max_amount": "1.00"}),
            ("get", "/api/admin/collection-stats", None),
        ],
    )
    def test_admin_only_endpoints_forbidden(self, client, librarian_token, method, url, body):
        response = _call(client, method, url, body, auth(librarian_token))
        assert response.status_code == 403, f"{method.upper()} {url} 未拒绝图书管理员"

    def test_librarian_cannot_manage_accounts(self, client, librarian_token):
        response = client.post(
            "/api/admin/librarians",
            json={"username": "lib999", "password": "lib123456", "name": "越权"},
            headers=auth(librarian_token),
        )
        assert response.status_code == 403

    def test_librarian_can_do_circulation(self, client, librarian_token, admin_token):
        """馆员权限内的操作不受影响。"""
        reader_id = register_reader(client, "reader131")
        card = issue_card(client, admin_token, reader_id)
        title = add_title(client, admin_token, title="馆员可操作")
        item = add_item(client, admin_token, title["title_id"])

        borrowed = client.post(
            "/api/circulation/borrow",
            json={"card_no": card["card_no"], "barcode": item["barcode"]},
            headers=auth(librarian_token),
        )
        assert borrowed.status_code == 201
        assert client.post(
            "/api/circulation/return",
            json={"barcode": item["barcode"]},
            headers=auth(librarian_token),
        ).status_code == 200

    def test_librarian_can_read_policies(self, client, librarian_token):
        assert client.get("/api/policies", headers=auth(librarian_token)).status_code == 200


class TestSystemAdminCanDoEverything:
    def test_admin_can_borrow_and_return(self, client, admin_token):
        """BR-040 允许系统管理员代行流通业务。"""
        reader_id = register_reader(client, "reader132")
        card = issue_card(client, admin_token, reader_id)
        title = add_title(client, admin_token, title="管理员代行")
        item = add_item(client, admin_token, title["title_id"])

        assert client.post(
            "/api/circulation/borrow",
            json={"card_no": card["card_no"], "barcode": item["barcode"]},
            headers=auth(admin_token),
        ).status_code == 201
        assert client.post(
            "/api/circulation/return",
            json={"barcode": item["barcode"]},
            headers=auth(admin_token),
        ).status_code == 200

    def test_admin_borrow_records_null_librarian(self, client, admin_token, session):
        """取舍：系统管理员代行时 `librarian_id` 为 `NULL`（`13` §4.7 已披露）。"""
        from sqlalchemy import select

        from app.infrastructure.models import LoanModel

        reader_id = register_reader(client, "reader133")
        card = issue_card(client, admin_token, reader_id)
        title = add_title(client, admin_token, title="管理员经办")
        item = add_item(client, admin_token, title["title_id"])
        client.post(
            "/api/circulation/borrow",
            json={"card_no": card["card_no"], "barcode": item["barcode"]},
            headers=auth(admin_token),
        )
        loan = session.scalars(select(LoanModel)).all()[-1]
        assert loan.librarian_id is None


class TestAuthenticationRequired:
    @pytest.mark.parametrize(
        "method,url",
        [
            ("get", "/api/me/loans"),
            ("get", "/api/me/fines"),
            ("get", "/api/me/reservations"),
            ("get", "/api/policies"),
            ("post", "/api/circulation/borrow"),
            ("post", "/api/admin/book-titles"),
        ],
    )
    def test_unauthenticated_rejected(self, client, method, url):
        if method == "post":
            response = client.post(url, json={})
        else:
            response = client.get(url)
        assert response.status_code == 401
        assert response.json()["error"]["code"] == "UNAUTHORIZED"

    def test_expired_token_rejected(self, client, admin_token):
        """BR-046：Token 过期需重新登录。"""
        import jwt

        from app.infrastructure.security.jwt import ALGORITHM, SECRET_KEY

        payload = {"sub": "1", "role": "SYSTEM_ADMIN", "exp": 1_000_000_000, "iat": 1}
        expired = jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)
        response = client.get("/api/admin/librarians", headers=auth(expired))
        assert response.status_code == 401
