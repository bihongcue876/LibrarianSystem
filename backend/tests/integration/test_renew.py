"""续借集成测试（TC-035，UC-007 / FR-018）。

**最容易实现错的一点**：存在预约排队**不影响**续借资格（BR-018）。
本文件专门验证它。
"""

from __future__ import annotations

from datetime import datetime, timedelta

from tests.conftest import add_item, add_title, auth, force_overdue, issue_card, register_reader


def _borrow(client, librarian_token, card_no, barcode):
    response = client.post(
        "/api/circulation/borrow",
        json={"card_no": card_no, "barcode": barcode},
        headers=auth(librarian_token),
    )
    assert response.status_code == 201, response.text
    return response.json()


class TestRenew:
    def test_renew_extends_seven_days(self, client, librarian_token, graduate_setup):
        loan = _borrow(client, librarian_token, graduate_setup["card_no"], graduate_setup["barcode"])
        original_due = datetime.fromisoformat(loan["due_at"])

        response = client.post(
            f"/api/circulation/loans/{loan['loan_id']}/renew",
            headers=auth(graduate_setup["reader_token"]),
        )
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["renew_count"] == 1
        assert datetime.fromisoformat(body["due_at"]) - original_due == timedelta(days=7)

    def test_renew_twice_then_rejected(self, client, librarian_token, graduate_setup):
        loan = _borrow(client, librarian_token, graduate_setup["card_no"], graduate_setup["barcode"])
        url = f"/api/circulation/loans/{loan['loan_id']}/renew"
        headers = auth(graduate_setup["reader_token"])

        assert client.post(url, headers=headers).json()["renew_count"] == 1
        assert client.post(url, headers=headers).json()["renew_count"] == 2

        third = client.post(url, headers=headers)
        assert third.status_code == 400
        assert third.json()["error"]["code"] == "RENEW_LIMIT_EXCEEDED"

    def test_renew_does_not_consume_extra_quota(self, client, librarian_token, graduate_setup):
        """BR-019：续借不额外占用借阅额度。"""
        loan = _borrow(client, librarian_token, graduate_setup["card_no"], graduate_setup["barcode"])
        before = client.post(
            "/api/circulation/precheck",
            json={"card_no": graduate_setup["card_no"], "barcode": graduate_setup["barcode"]},
            headers=auth(librarian_token),
        ).json()["quota"]["occupied"]

        client.post(
            f"/api/circulation/loans/{loan['loan_id']}/renew",
            headers=auth(graduate_setup["reader_token"]),
        )
        after = client.post(
            "/api/circulation/precheck",
            json={"card_no": graduate_setup["card_no"], "barcode": graduate_setup["barcode"]},
            headers=auth(librarian_token),
        ).json()["quota"]["occupied"]
        assert before == after

    def test_overdue_loan_cannot_renew(self, client, librarian_token, graduate_setup, session):
        loan = _borrow(client, librarian_token, graduate_setup["card_no"], graduate_setup["barcode"])
        force_overdue(session, loan["loan_id"], 3)

        response = client.post(
            f"/api/circulation/loans/{loan['loan_id']}/renew",
            headers=auth(graduate_setup["reader_token"]),
        )
        assert response.status_code == 400
        assert response.json()["error"]["code"] == "RENEW_OVERDUE"

    def test_returned_loan_cannot_renew(self, client, librarian_token, graduate_setup):
        loan = _borrow(client, librarian_token, graduate_setup["card_no"], graduate_setup["barcode"])
        client.post(
            "/api/circulation/return",
            json={"barcode": graduate_setup["barcode"]},
            headers=auth(librarian_token),
        )
        response = client.post(
            f"/api/circulation/loans/{loan['loan_id']}/renew",
            headers=auth(graduate_setup["reader_token"]),
        )
        assert response.status_code == 400

    def test_unknown_loan(self, client, graduate_setup):
        response = client.post(
            "/api/circulation/loans/9999/renew",
            headers=auth(graduate_setup["reader_token"]),
        )
        assert response.status_code == 404

    def test_reader_cannot_renew_others_loan(self, client, librarian_token, graduate_setup, admin_token):
        loan = _borrow(client, librarian_token, graduate_setup["card_no"], graduate_setup["barcode"])

        other_id = register_reader(client, "reader090")
        issue_card(client, admin_token, other_id)
        other_token = client.post(
            "/api/auth/login",
            json={"username": "reader090", "password": "reader123", "role": "READER"},
        ).json()["access_token"]

        response = client.post(
            f"/api/circulation/loans/{loan['loan_id']}/renew", headers=auth(other_token)
        )
        assert response.status_code == 403

    def test_librarian_can_renew_for_reader(self, client, librarian_token, graduate_setup):
        loan = _borrow(client, librarian_token, graduate_setup["card_no"], graduate_setup["barcode"])
        response = client.post(
            f"/api/circulation/loans/{loan['loan_id']}/renew", headers=auth(librarian_token)
        )
        assert response.status_code == 200

    def test_pending_reservation_does_not_block_renewal(
        self, client, librarian_token, admin_token, graduate_setup
    ):
        """**BR-018 / FR-018 验收 7**：存在预约排队**不影响**续借资格。

        构造：读者借走唯一副本 → 另一读者对该题录预约成功 → 持书人仍可续借。
        （这是最容易实现错的地方：很多实现会误加"有人预约则禁续"的限制。）
        """
        loan = _borrow(client, librarian_token, graduate_setup["card_no"], graduate_setup["barcode"])

        # 让另一位读者对该题录产生有效预约（此时全部副本已被借出，符合 BR-020）
        reserver_id = register_reader(client, "reader092")
        issue_card(client, admin_token, reserver_id)
        reserver_token = client.post(
            "/api/auth/login",
            json={"username": "reader092", "password": "reader123", "role": "READER"},
        ).json()["access_token"]
        reservation = client.post(
            "/api/reservations",
            json={"title_id": graduate_setup["title_id"]},
            headers=auth(reserver_token),
        )
        assert reservation.status_code == 201, reservation.text

        response = client.post(
            f"/api/circulation/loans/{loan['loan_id']}/renew",
            headers=auth(graduate_setup["reader_token"]),
        )
        assert response.status_code == 200, response.text
        assert response.json()["renew_count"] == 1

    def test_renew_rejected_when_quota_exceeded(self, client, librarian_token, admin_token, session):
        """BR-017：占用额度超上限时不可续借。

        构造方式：先借满 5 本，再把该读者类型的额度规则下调为 1。
        规则修改不追溯已有借阅的 `due_at`（BR-050），但**会**参与之后的额度判定。
        """
        reader_id = register_reader(client, "reader091", "UNDERGRADUATE")
        card = issue_card(client, admin_token, reader_id)
        title = add_title(client, admin_token, title="超额续借")
        barcodes = [add_item(client, admin_token, title["title_id"])["barcode"] for _ in range(5)]

        loans = [_borrow(client, librarian_token, card["card_no"], barcode) for barcode in barcodes]
        reader_token = client.post(
            "/api/auth/login",
            json={"username": "reader091", "password": "reader123", "role": "READER"},
        ).json()["access_token"]

        client.put(
            "/api/admin/policies/borrow",
            json={"reader_type": "UNDERGRADUATE", "max_borrow_count": 1, "borrow_days": 30},
            headers=auth(admin_token),
        )

        response = client.post(
            f"/api/circulation/loans/{loans[0]['loan_id']}/renew", headers=auth(reader_token)
        )
        assert response.status_code == 400
        assert response.json()["error"]["code"] == "BORROW_LIMIT_EXCEEDED"
