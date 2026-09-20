"""借阅证集成测试（TC-005 ~ TC-007，UC-201 ~ UC-205）。"""

from __future__ import annotations

import re

from tests.conftest import auth, issue_card, register_reader


class TestIssueCard:
    """TC-005 办理借阅证成功。"""

    def test_issue_success(self, client, admin_token):
        reader_id = register_reader(client, "reader010")
        response = client.post(
            "/api/admin/borrow-cards", json={"reader_id": reader_id}, headers=auth(admin_token)
        )
        assert response.status_code == 201, response.text
        body = response.json()
        assert re.match(r"^CARD\d{4}\d{6}$", body["card_no"])
        assert body["status"] == "ACTIVE"
        assert body["issued_by"] is not None

    def test_card_numbers_are_unique_and_sequential(self, client, admin_token):
        first = issue_card(client, admin_token, register_reader(client, "reader011"))
        second = issue_card(client, admin_token, register_reader(client, "reader012"))
        assert first["card_no"] != second["card_no"]
        assert int(second["card_no"][-6:]) == int(first["card_no"][-6:]) + 1

    """TC-006 重复办理失败（一证限制，BR-003）。"""

    def test_duplicate_card_rejected(self, client, admin_token):
        reader_id = register_reader(client, "reader013")
        issue_card(client, admin_token, reader_id)
        response = client.post(
            "/api/admin/borrow-cards", json={"reader_id": reader_id}, headers=auth(admin_token)
        )
        assert response.status_code == 409
        assert response.json()["error"]["code"] == "CARD_ALREADY_EXISTS"

    def test_suspended_card_also_blocks_new_card(self, client, admin_token):
        """BR-003：`SUSPENDED` 同样计入一人一证限制。"""
        reader_id = register_reader(client, "reader014")
        card = issue_card(client, admin_token, reader_id)
        client.post(
            f"/api/admin/borrow-cards/{card['card_id']}/suspend", headers=auth(admin_token)
        )
        response = client.post(
            "/api/admin/borrow-cards", json={"reader_id": reader_id}, headers=auth(admin_token)
        )
        assert response.status_code == 409

    def test_cancelled_card_does_not_block_new_card(self, client, admin_token):
        """FR-006 验收 4：`CANCELLED` 不计入，该读者可重新办证。"""
        reader_id = register_reader(client, "reader015")
        card = issue_card(client, admin_token, reader_id)
        client.post(
            f"/api/admin/borrow-cards/{card['card_id']}/cancel",
            json={},
            headers=auth(admin_token),
        )
        response = client.post(
            "/api/admin/borrow-cards", json={"reader_id": reader_id}, headers=auth(admin_token)
        )
        assert response.status_code == 201

    """TC-007 读者不存在时办证失败。"""

    def test_reader_not_found(self, client, admin_token):
        response = client.post(
            "/api/admin/borrow-cards", json={"reader_id": 9999}, headers=auth(admin_token)
        )
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "READER_NOT_FOUND"

    def test_soft_deleted_reader_cannot_get_card(self, client, admin_token, session):
        reader_id = register_reader(client, "reader016")
        from app.infrastructure.models import ReaderModel

        model = session.get(ReaderModel, reader_id)
        model.is_deleted = 1
        session.commit()
        response = client.post(
            "/api/admin/borrow-cards", json={"reader_id": reader_id}, headers=auth(admin_token)
        )
        assert response.status_code == 404


class TestCardStateMachine:
    def test_suspend_and_resume(self, client, admin_token):
        card = issue_card(client, admin_token, register_reader(client, "reader020"))
        suspended = client.post(
            f"/api/admin/borrow-cards/{card['card_id']}/suspend", headers=auth(admin_token)
        )
        assert suspended.json()["status"] == "SUSPENDED"
        resumed = client.post(
            f"/api/admin/borrow-cards/{card['card_id']}/resume", headers=auth(admin_token)
        )
        assert resumed.json()["status"] == "ACTIVE"

    def test_cancel_then_restore(self, client, admin_token):
        card = issue_card(client, admin_token, register_reader(client, "reader021"))
        client.post(
            f"/api/admin/borrow-cards/{card['card_id']}/cancel",
            json={},
            headers=auth(admin_token),
        )
        restored = client.post(
            f"/api/admin/borrow-cards/{card['card_id']}/restore", headers=auth(admin_token)
        )
        assert restored.status_code == 200
        assert restored.json()["status"] == "ACTIVE"

    def test_restore_non_cancelled_rejected(self, client, admin_token):
        card = issue_card(client, admin_token, register_reader(client, "reader022"))
        response = client.post(
            f"/api/admin/borrow-cards/{card['card_id']}/restore", headers=auth(admin_token)
        )
        assert response.status_code == 400  # FR-007 验收 3

    def test_restore_blocked_when_another_active_card_exists(self, client, admin_token):
        """FR-007 验收 2：恢复时若已有其他有效证 → 409。"""
        reader_id = register_reader(client, "reader023")
        old_card = issue_card(client, admin_token, reader_id)
        client.post(
            f"/api/admin/borrow-cards/{old_card['card_id']}/cancel",
            json={},
            headers=auth(admin_token),
        )
        issue_card(client, admin_token, reader_id)  # 新证（ACTIVE）
        response = client.post(
            f"/api/admin/borrow-cards/{old_card['card_id']}/restore", headers=auth(admin_token)
        )
        assert response.status_code == 409
        assert response.json()["error"]["code"] == "CARD_ALREADY_EXISTS"

    def test_suspend_non_active_rejected(self, client, admin_token):
        card = issue_card(client, admin_token, register_reader(client, "reader024"))
        client.post(
            f"/api/admin/borrow-cards/{card['card_id']}/cancel",
            json={},
            headers=auth(admin_token),
        )
        response = client.post(
            f"/api/admin/borrow-cards/{card['card_id']}/suspend", headers=auth(admin_token)
        )
        assert response.status_code == 400


class TestCardQuery:
    def test_get_by_card_no(self, client, admin_token):
        card = issue_card(client, admin_token, register_reader(client, "reader030"))
        response = client.get(f"/api/borrow-cards/{card['card_no']}", headers=auth(admin_token))
        assert response.status_code == 200
        assert response.json()["card_no"] == card["card_no"]

    def test_unknown_card_no(self, client, admin_token):
        response = client.get("/api/borrow-cards/CARD2026999999", headers=auth(admin_token))
        assert response.status_code == 404

    def test_admin_lists_all_cards_including_cancelled(self, client, admin_token):
        """FR-009 验收 2：含历史注销记录。"""
        reader_id = register_reader(client, "reader031")
        card = issue_card(client, admin_token, reader_id)
        client.post(
            f"/api/admin/borrow-cards/{card['card_id']}/cancel",
            json={},
            headers=auth(admin_token),
        )
        issue_card(client, admin_token, reader_id)

        listed = client.get(
            f"/api/admin/readers/{reader_id}/borrow-cards", headers=auth(admin_token)
        ).json()
        assert len(listed) == 2
        statuses = {item["status"] for item in listed}
        assert statuses == {"CANCELLED", "ACTIVE"}
