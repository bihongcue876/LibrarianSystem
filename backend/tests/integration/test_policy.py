"""规则维护集成测试（UC-213 / UC-214，FR-027 / FR-028 / BR-049 / BR-050）。"""

from __future__ import annotations

from tests.conftest import add_item, add_title, auth, force_overdue, issue_card, register_reader


class TestPolicyQuery:
    def test_get_all_rules(self, client, admin_token):
        body = client.get("/api/policies", headers=auth(admin_token)).json()
        assert len(body["borrow_policies"]) == 5
        assert len(body["fine_rules"]) == 5

    def test_borrow_rule_values(self, client, admin_token):
        rules = {
            item["reader_type"]: (item["max_borrow_count"], item["borrow_days"])
            for item in client.get("/api/policies", headers=auth(admin_token)).json()[
                "borrow_policies"
            ]
        }
        assert rules == {
            "COLLEGE": (5, 30),
            "UNDERGRADUATE": (5, 30),
            "GRADUATE": (10, 60),
            "DOCTOR": (15, 90),
            "TEACHER": (20, 90),
        }

    def test_fine_rule_values(self, client, admin_token):
        rules = {
            item["item_type"]: (item["daily_price"], item["grace_days"], item["max_amount"])
            for item in client.get("/api/policies", headers=auth(admin_token)).json()["fine_rules"]
        }
        assert rules["FOREIGN_BOOK"] == ("0.50", 2, "100.00")
        assert rules["THESIS"] == ("1.00", 2, "100.00")

    def test_reader_can_read_policies(self, client, reader_token):
        """读者需知晓本人额度与期限。"""
        assert client.get("/api/policies", headers=auth(reader_token)).status_code == 200


class TestBorrowPolicyMaintenance:
    """UC-213 / FR-027。"""

    def test_update_takes_effect_on_new_loans(self, client, admin_token, librarian_token):
        response = client.put(
            "/api/admin/policies/borrow",
            json={"reader_type": "GRADUATE", "max_borrow_count": 12, "borrow_days": 45},
            headers=auth(admin_token),
        )
        assert response.status_code == 200
        assert response.json()["max_borrow_count"] == 12
        assert response.json()["updated_by"] is not None

        # 新借阅按新期限
        reader_id = register_reader(client, "reader140", "GRADUATE")
        card = issue_card(client, admin_token, reader_id)
        title = add_title(client, admin_token, title="新规则书")
        item = add_item(client, admin_token, title["title_id"])

        from datetime import datetime, timedelta

        loan = client.post(
            "/api/circulation/borrow",
            json={"card_no": card["card_no"], "barcode": item["barcode"]},
            headers=auth(librarian_token),
        ).json()
        span = datetime.fromisoformat(loan["due_at"]) - datetime.fromisoformat(loan["borrowed_at"])
        assert span == timedelta(days=45)

    def test_rule_change_does_not_retroact(self, client, admin_token, librarian_token):
        """**BR-050**：规则修改不追溯已有借阅的 `due_at`。"""
        from datetime import datetime

        reader_id = register_reader(client, "reader141", "GRADUATE")
        card = issue_card(client, admin_token, reader_id)
        title = add_title(client, admin_token, title="不追溯书")
        item = add_item(client, admin_token, title["title_id"])

        loan = client.post(
            "/api/circulation/borrow",
            json={"card_no": card["card_no"], "barcode": item["barcode"]},
            headers=auth(librarian_token),
        ).json()
        original_due = datetime.fromisoformat(loan["due_at"])

        client.put(
            "/api/admin/policies/borrow",
            json={"reader_type": "GRADUATE", "max_borrow_count": 10, "borrow_days": 180},
            headers=auth(admin_token),
        )

        token = client.post(
            "/api/auth/login",
            json={"username": "reader141", "password": "reader123", "role": "READER"},
        ).json()["access_token"]
        listed = client.get("/api/me/loans", headers=auth(token)).json()

        # 两种序列化写法（`+00:00` 与 `Z`）都合法，故比较解析后的时刻而非字符串
        assert datetime.fromisoformat(listed["current"][0]["due_at"]) == original_due

    def test_new_quota_applies_to_new_borrowing(self, client, admin_token, librarian_token):
        """额度规则修改后立即约束新借阅。"""
        client.put(
            "/api/admin/policies/borrow",
            json={"reader_type": "UNDERGRADUATE", "max_borrow_count": 1, "borrow_days": 30},
            headers=auth(admin_token),
        )
        reader_id = register_reader(client, "reader142", "UNDERGRADUATE")
        card = issue_card(client, admin_token, reader_id)
        title = add_title(client, admin_token, title="新额度书")
        first = add_item(client, admin_token, title["title_id"])
        second = add_item(client, admin_token, title["title_id"])

        assert client.post(
            "/api/circulation/borrow",
            json={"card_no": card["card_no"], "barcode": first["barcode"]},
            headers=auth(librarian_token),
        ).status_code == 201
        blocked = client.post(
            "/api/circulation/borrow",
            json={"card_no": card["card_no"], "barcode": second["barcode"]},
            headers=auth(librarian_token),
        )
        assert blocked.status_code == 400
        assert blocked.json()["error"]["detail"] == {"current": 1, "limit": 1}

    def test_invalid_values_rejected(self, client, admin_token):
        assert client.put(
            "/api/admin/policies/borrow",
            json={"reader_type": "GRADUATE", "max_borrow_count": 0, "borrow_days": 60},
            headers=auth(admin_token),
        ).status_code == 422
        assert client.put(
            "/api/admin/policies/borrow",
            json={"reader_type": "GRADUATE", "max_borrow_count": 10, "borrow_days": 0},
            headers=auth(admin_token),
        ).status_code == 422
        assert client.put(
            "/api/admin/policies/borrow",
            json={"reader_type": "UNKNOWN", "max_borrow_count": 10, "borrow_days": 60},
            headers=auth(admin_token),
        ).status_code == 422


class TestFineRuleMaintenance:
    """UC-214 / FR-028。"""

    def test_update_takes_effect_on_new_fines(self, client, admin_token, librarian_token, session):
        client.put(
            "/api/admin/policies/fine",
            json={"item_type": "FOREIGN_BOOK", "daily_price": "1.00", "grace_days": 0,
                  "max_amount": "50.00"},
            headers=auth(admin_token),
        )

        reader_id = register_reader(client, "reader143")
        card = issue_card(client, admin_token, reader_id)
        title = add_title(client, admin_token, title="新罚款规则")
        item = add_item(client, admin_token, title["title_id"])
        loan = client.post(
            "/api/circulation/borrow",
            json={"card_no": card["card_no"], "barcode": item["barcode"]},
            headers=auth(librarian_token),
        ).json()
        force_overdue(session, loan["loan_id"], 5)

        body = client.post(
            "/api/circulation/return",
            json={"barcode": item["barcode"]},
            headers=auth(librarian_token),
        ).json()
        assert body["billed_days"] == 5  # 宽限期改为 0
        assert body["fine"]["amount"] == "5.00"

    def test_rule_change_does_not_retroact_existing_fine(
        self, client, admin_token, librarian_token, session
    ):
        """**BR-050**：`FineRecord` 快照 `unit_price`，规则修改不影响已生成的罚款。"""
        reader_id = register_reader(client, "reader144")
        card = issue_card(client, admin_token, reader_id)
        title = add_title(client, admin_token, title="快照书")
        item = add_item(client, admin_token, title["title_id"])
        loan = client.post(
            "/api/circulation/borrow",
            json={"card_no": card["card_no"], "barcode": item["barcode"]},
            headers=auth(librarian_token),
        ).json()
        force_overdue(session, loan["loan_id"], 21)
        fine = client.post(
            "/api/circulation/return",
            json={"barcode": item["barcode"]},
            headers=auth(librarian_token),
        ).json()["fine"]
        assert fine["amount"] == "9.50"

        client.put(
            "/api/admin/policies/fine",
            json={"item_type": "FOREIGN_BOOK", "daily_price": "9.99", "grace_days": 0,
                  "max_amount": "999.00"},
            headers=auth(admin_token),
        )

        token = client.post(
            "/api/auth/login",
            json={"username": "reader144", "password": "reader123", "role": "READER"},
        ).json()["access_token"]
        record = client.get("/api/me/fines", headers=auth(token)).json()["unpaid"][0]
        assert record["amount"] == "9.50"
        assert record["unit_price"] == "0.50"  # 单价仍是生成时的快照

    def test_negative_values_rejected(self, client, admin_token):
        assert client.put(
            "/api/admin/policies/fine",
            json={"item_type": "THESIS", "daily_price": "-1.00", "grace_days": 2,
                  "max_amount": "100.00"},
            headers=auth(admin_token),
        ).status_code == 400
        assert client.put(
            "/api/admin/policies/fine",
            json={"item_type": "THESIS", "daily_price": "1.00", "grace_days": -1,
                  "max_amount": "100.00"},
            headers=auth(admin_token),
        ).status_code == 422
