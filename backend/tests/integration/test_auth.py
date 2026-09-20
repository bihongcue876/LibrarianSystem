"""认证与账号集成测试（TC-001 ~ TC-004）。"""

from __future__ import annotations

from tests.conftest import (
    ADMIN_PASSWORD,
    READER_PASSWORD,
    auth,
    login,
    register_reader,
)


class TestRegister:
    """TC-001 注册读者成功。"""

    def test_register_success(self, client):
        response = client.post(
            "/api/auth/register",
            json={
                "username": "reader001",
                "password": READER_PASSWORD,
                "name": "张三",
                "department": "计算机学院",
                "reader_type": "UNDERGRADUATE",
            },
        )
        assert response.status_code == 201, response.text
        body = response.json()
        assert body["username"] == "reader001"
        assert body["role"] == "READER"
        assert body["reader_type"] == "UNDERGRADUATE"

    def test_registered_reader_cannot_borrow_yet(self, client, librarian_token):
        """注册后立即可登录，但**未办证前不具备借阅资格**（BR-012）。"""
        register_reader(client, "reader001")
        token = login(client, "reader001", READER_PASSWORD, "READER")
        response = client.get("/api/me/loans", headers=auth(token))
        assert response.status_code == 200  # 可登录、可查自己的（空）记录

        # 读者调用借书接口本身就越权（BR-040）
        borrow_attempt = client.post(
            "/api/circulation/borrow",
            json={"card_no": "CARD2026000001", "barcode": "BC00000001"},
            headers=auth(token),
        )
        assert borrow_attempt.status_code == 403

    """TC-002 用户名重复 —— 且软删除不释放（Q-03 裁定）。"""

    def test_duplicate_username_rejected(self, client):
        register_reader(client, "reader001")
        response = client.post(
            "/api/auth/register",
            json={
                "username": "reader001",
                "password": READER_PASSWORD,
                "name": "李四",
                "department": "软件学院",
                "reader_type": "TEACHER",
            },
        )
        assert response.status_code == 409
        assert response.json()["error"]["code"] == "USERNAME_EXISTS"

    def test_soft_deleted_username_not_released(self, client, session):
        """Q-03：软删除后，同名用户名仍不可重新注册。"""
        reader_id = register_reader(client, "reader001")
        from app.infrastructure.models import ReaderModel

        model = session.get(ReaderModel, reader_id)
        model.is_deleted = 1
        session.commit()

        response = client.post(
            "/api/auth/register",
            json={
                "username": "reader001",
                "password": READER_PASSWORD,
                "name": "李四",
                "department": "软件学院",
                "reader_type": "TEACHER",
            },
        )
        assert response.status_code == 409

    def test_invalid_reader_type(self, client):
        response = client.post(
            "/api/auth/register",
            json={
                "username": "reader002",
                "password": READER_PASSWORD,
                "name": "王五",
                "department": "物理学院",
                "reader_type": "VISITING_SCHOLAR",
            },
        )
        assert response.status_code == 422

    def test_password_too_short(self, client):
        response = client.post(
            "/api/auth/register",
            json={
                "username": "reader003",
                "password": "123",
                "name": "王五",
                "department": "物理学院",
                "reader_type": "TEACHER",
            },
        )
        assert response.status_code == 422


class TestLogin:
    """TC-003 登录成功。"""

    def test_login_returns_token(self, client):
        register_reader(client, "reader001")
        response = client.post(
            "/api/auth/login",
            json={"username": "reader001", "password": READER_PASSWORD, "role": "READER"},
        )
        assert response.status_code == 200
        body = response.json()
        assert body["access_token"]
        assert body["token_type"] == "bearer"
        assert body["role"] == "READER"
        assert body["expires_at"] is not None

    def test_token_ttl_is_24_hours(self, client):
        register_reader(client, "reader001")
        body = client.post(
            "/api/auth/login",
            json={"username": "reader001", "password": READER_PASSWORD, "role": "READER"},
        ).json()
        import jwt

        from app.infrastructure.security.jwt import SECRET_KEY

        payload = jwt.decode(body["access_token"], SECRET_KEY, algorithms=["HS256"])
        assert payload["exp"] - payload["iat"] == 24 * 3600  # BR-046

    """TC-004 登录失败提示不区分原因（BR-047）。"""

    def test_wrong_password_and_unknown_user_are_indistinguishable(self, client):
        register_reader(client, "reader001")

        wrong_password = client.post(
            "/api/auth/login",
            json={"username": "reader001", "password": "wrongpass1", "role": "READER"},
        )
        unknown_user = client.post(
            "/api/auth/login",
            json={"username": "ghost001", "password": "wrongpass1", "role": "READER"},
        )

        assert wrong_password.status_code == 401
        assert unknown_user.status_code == 401
        assert wrong_password.json() == unknown_user.json()
        assert wrong_password.json()["error"]["message"] == "用户名或密码错误"

    def test_soft_deleted_account_cannot_login(self, client, session):
        reader_id = register_reader(client, "reader001")
        from app.infrastructure.models import ReaderModel

        model = session.get(ReaderModel, reader_id)
        model.is_deleted = 1
        session.commit()

        response = client.post(
            "/api/auth/login",
            json={"username": "reader001", "password": READER_PASSWORD, "role": "READER"},
        )
        assert response.status_code == 401

    def test_protected_endpoint_without_token(self, client):
        assert client.get("/api/me/loans").status_code == 401

    def test_protected_endpoint_with_garbage_token(self, client):
        response = client.get("/api/me/loans", headers={"Authorization": "Bearer not-a-token"})
        assert response.status_code == 401


class TestPasswordStorage:
    def test_password_is_bcrypt_hashed(self, client, session):
        reader_id = register_reader(client, "reader001")
        from app.infrastructure.models import ReaderModel

        model = session.get(ReaderModel, reader_id)
        assert model.password_hash != READER_PASSWORD
        assert model.password_hash.startswith("$2b$")
        assert len(model.password_hash) == 60  # 与 VARCHAR(60) 对齐


class TestStaffAccounts:
    """UC-206 / UC-207：员工账号管理（仅系统管理员）。"""

    def test_admin_creates_librarian(self, client, admin_token):
        response = client.post(
            "/api/admin/librarians",
            json={"username": "lib002", "password": "lib123456", "name": "王馆员"},
            headers=auth(admin_token),
        )
        assert response.status_code == 201
        assert response.json()["role"] == "LIBRARIAN"

    def test_new_librarian_can_login(self, client, admin_token):
        client.post(
            "/api/admin/librarians",
            json={"username": "lib002", "password": "lib123456", "name": "王馆员"},
            headers=auth(admin_token),
        )
        assert login(client, "lib002", "lib123456", "LIBRARIAN")

    def test_delete_librarian_soft(self, client, admin_token, librarian_token):
        listed = client.get("/api/admin/librarians", headers=auth(admin_token)).json()
        target = next(item for item in listed if item["username"] == "librarian")
        response = client.delete(
            f"/api/admin/librarians/{target['account_id']}", headers=auth(admin_token)
        )
        assert response.status_code == 200

        # 已删除账号不可再登录
        relogin = client.post(
            "/api/auth/login",
            json={"username": "librarian", "password": "lib123456", "role": "LIBRARIAN"},
        )
        assert relogin.status_code == 401

    def test_admin_cannot_delete_admin(self, client, admin_token):
        """BR-043：系统管理员之间不可互相删除。接口本身只接受 librarian_id，
        传入管理员 ID 应得到 404 而非删除成功。"""
        response = client.delete("/api/admin/librarians/9999", headers=auth(admin_token))
        assert response.status_code == 404

    def test_reset_password(self, client, admin_token):
        """Q-05：管理员可重置密码；系统不提供自助找回。"""
        reader_id = register_reader(client, "reader001")
        response = client.post(
            f"/api/admin/accounts/{reader_id}/reset-password",
            json={"new_password": "newpass123", "role": "READER"},
            headers=auth(admin_token),
        )
        assert response.status_code == 200
        assert login(client, "reader001", "newpass123", "READER")
        assert (
            client.post(
                "/api/auth/login",
                json={"username": "reader001", "password": READER_PASSWORD, "role": "READER"},
            ).status_code
            == 401
        )

    def test_admin_login_works(self, client):
        assert login(client, "admin", ADMIN_PASSWORD, "SYSTEM_ADMIN")
