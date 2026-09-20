"""还书集成测试（TC-015 ~ TC-019、TC-036，UC-102 / UC-102a / FR-017）。"""

from __future__ import annotations

import pytest

from tests.conftest import add_item, add_title, auth, force_overdue, issue_card, register_reader


def _borrow(client, librarian_token, card_no, barcode):
    response = client.post(
        "/api/circulation/borrow",
        json={"card_no": card_no, "barcode": barcode},
        headers=auth(librarian_token),
    )
    assert response.status_code == 201, response.text
    return response.json()


class TestReturnSuccess:
    """TC-015 还书成功。"""

    def test_return_by_barcode_only(self, client, librarian_token, graduate_setup):
        """FR-017：**仅凭馆藏条码**，请求体不含借阅证号。"""
        _borrow(client, librarian_token, graduate_setup["card_no"], graduate_setup["barcode"])
        response = client.post(
            "/api/circulation/return",
            json={"barcode": graduate_setup["barcode"]},
            headers=auth(librarian_token),
        )
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["fine"] is None
        assert body["item_status"] == "AVAILABLE"
        assert body["overdue_days"] == 0

    def test_loan_becomes_returned(self, client, librarian_token, graduate_setup):
        loan = _borrow(client, librarian_token, graduate_setup["card_no"], graduate_setup["barcode"])
        client.post(
            "/api/circulation/return",
            json={"barcode": graduate_setup["barcode"]},
            headers=auth(librarian_token),
        )
        listed = client.get(
            "/api/me/loans", headers=auth(graduate_setup["reader_token"])
        ).json()
        assert listed["current"] == []
        assert len(listed["history"]) == 1
        assert listed["history"][0]["loan_id"] == loan["loan_id"]
        assert listed["history"][0]["returned_at"] is not None

    def test_item_returns_to_available(self, client, librarian_token, admin_token, graduate_setup):
        _borrow(client, librarian_token, graduate_setup["card_no"], graduate_setup["barcode"])
        client.post(
            "/api/circulation/return",
            json={"barcode": graduate_setup["barcode"]},
            headers=auth(librarian_token),
        )
        found = client.get("/api/books", params={"keyword": "算法导论"}).json()
        assert found["items"][0]["available_items"] == 1

    def test_quota_released_after_return(self, client, librarian_token, graduate_setup):
        _borrow(client, librarian_token, graduate_setup["card_no"], graduate_setup["barcode"])
        client.post(
            "/api/circulation/return",
            json={"barcode": graduate_setup["barcode"]},
            headers=auth(librarian_token),
        )
        precheck = client.post(
            "/api/circulation/precheck",
            json={"card_no": graduate_setup["card_no"], "barcode": graduate_setup["barcode"]},
            headers=auth(librarian_token),
        ).json()
        assert precheck["quota"]["occupied"] == 0


class TestReturnFailures:
    """TC-016 归还非本馆藏书失败。"""

    def test_unknown_barcode(self, client, librarian_token):
        response = client.post(
            "/api/circulation/return",
            json={"barcode": "BC99999999"},
            headers=auth(librarian_token),
        )
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "ITEM_NOT_FOUND"

    """TC-017 无在借记录时还书失败。"""

    def test_item_not_borrowed(self, client, librarian_token, graduate_setup):
        response = client.post(
            "/api/circulation/return",
            json={"barcode": graduate_setup["barcode"]},
            headers=auth(librarian_token),
        )
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "LOAN_NOT_FOUND"

    def test_already_returned(self, client, librarian_token, graduate_setup):
        _borrow(client, librarian_token, graduate_setup["card_no"], graduate_setup["barcode"])
        client.post(
            "/api/circulation/return",
            json={"barcode": graduate_setup["barcode"]},
            headers=auth(librarian_token),
        )
        second = client.post(
            "/api/circulation/return",
            json={"barcode": graduate_setup["barcode"]},
            headers=auth(librarian_token),
        )
        assert second.status_code == 404


class TestFineGeneration:
    """TC-018 超期还书生成罚款。"""

    def test_overdue_return_creates_fine(self, client, librarian_token, admin_token, session):
        """外文书超期 21 天：计罚 19 天 × 0.50 = 9.50 元。"""
        reader_id = register_reader(client, "reader070")
        card = issue_card(client, admin_token, reader_id)
        title = add_title(client, admin_token, title="罚款书", item_type="FOREIGN_BOOK")
        item = add_item(client, admin_token, title["title_id"])

        loan = _borrow(client, librarian_token, card["card_no"], item["barcode"])
        force_overdue(session, loan["loan_id"], 21)

        response = client.post(
            "/api/circulation/return",
            json={"barcode": item["barcode"]},
            headers=auth(librarian_token),
        )
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["overdue_days"] == 21
        assert body["billed_days"] == 19
        assert body["fine"]["amount"] == "9.50"
        assert body["fine"]["status"] == "UNPAID"

    @pytest.mark.parametrize(
        "item_type,overdue,expected",
        [
            ("CHINESE_BOOK", 5, "0.60"),      # 3 天 × 0.20
            ("FOREIGN_BOOK", 5, "1.50"),      # 3 天 × 0.50
            ("CHINESE_MAGAZINE", 5, "0.30"),  # 3 天 × 0.10
            ("FOREIGN_MAGAZINE", 5, "0.60"),  # 3 天 × 0.20
            ("THESIS", 5, "3.00"),            # 3 天 × 1.00
        ],
    )
    def test_all_item_types(self, client, librarian_token, admin_token, session, item_type, overdue, expected):
        """实验二验收标准 11：不同借出物类型罚款规则可用。"""
        reader_id = register_reader(client, f"reader_{item_type.lower()}")
        card = issue_card(client, admin_token, reader_id)
        title = add_title(client, admin_token, title=f"书-{item_type}", item_type=item_type)
        item = add_item(client, admin_token, title["title_id"])

        loan = _borrow(client, librarian_token, card["card_no"], item["barcode"])
        force_overdue(session, loan["loan_id"], overdue)

        body = client.post(
            "/api/circulation/return",
            json={"barcode": item["barcode"]},
            headers=auth(librarian_token),
        ).json()
        assert body["fine"]["amount"] == expected

    def test_cap_applies_at_100(self, client, librarian_token, admin_token, session):
        reader_id = register_reader(client, "reader071")
        card = issue_card(client, admin_token, reader_id)
        title = add_title(client, admin_token, title="封顶书", item_type="THESIS")
        item = add_item(client, admin_token, title["title_id"])

        loan = _borrow(client, librarian_token, card["card_no"], item["barcode"])
        force_overdue(session, loan["loan_id"], 365)

        body = client.post(
            "/api/circulation/return",
            json={"barcode": item["barcode"]},
            headers=auth(librarian_token),
        ).json()
        assert body["fine"]["amount"] == "100.00"

    def test_fine_visible_in_reader_fines(self, client, librarian_token, admin_token, session):
        reader_id = register_reader(client, "reader072")
        card = issue_card(client, admin_token, reader_id)
        title = add_title(client, admin_token, title="罚款可见")
        item = add_item(client, admin_token, title["title_id"])

        loan = _borrow(client, librarian_token, card["card_no"], item["barcode"])
        force_overdue(session, loan["loan_id"], 21)
        client.post(
            "/api/circulation/return",
            json={"barcode": item["barcode"]},
            headers=auth(librarian_token),
        )

        token = client.post(
            "/api/auth/login",
            json={"username": "reader072", "password": "reader123", "role": "READER"},
        ).json()["access_token"]
        fines = client.get("/api/me/fines", headers=auth(token)).json()
        assert len(fines["unpaid"]) == 1
        assert fines["unpaid"][0]["billed_days"] == 19
        assert fines["unpaid_total"] == "9.50"

    """TC-019 未超期还书不生成罚款。"""

    def test_not_overdue_no_fine(self, client, librarian_token, graduate_setup, session):
        loan = _borrow(client, librarian_token, graduate_setup["card_no"], graduate_setup["barcode"])
        body = client.post(
            "/api/circulation/return",
            json={"barcode": graduate_setup["barcode"]},
            headers=auth(librarian_token),
        ).json()
        assert body["fine"] is None

        from app.infrastructure.models import FineRecordModel
        from sqlalchemy import select

        assert session.scalars(select(FineRecordModel)).all() == []

    def test_within_grace_period_no_fine(self, client, librarian_token, admin_token, session):
        """处于 2 天宽限期内：**不生成**记录（否则会产生 0 元 `UNPAID` 罚款反过来阻断借书）。"""
        reader_id = register_reader(client, "reader073")
        card = issue_card(client, admin_token, reader_id)
        title = add_title(client, admin_token, title="宽限期书")
        item = add_item(client, admin_token, title["title_id"])

        loan = _borrow(client, librarian_token, card["card_no"], item["barcode"])
        force_overdue(session, loan["loan_id"], 2)

        body = client.post(
            "/api/circulation/return",
            json={"barcode": item["barcode"]},
            headers=auth(librarian_token),
        ).json()
        assert body["overdue_days"] == 2
        assert body["billed_days"] == 0
        assert body["fine"] is None

        from sqlalchemy import select

        from app.infrastructure.models import FineRecordModel

        assert session.scalars(select(FineRecordModel)).all() == []


class TestCollectFine:
    def test_collect_marks_paid(self, client, librarian_token, admin_token, session):
        reader_id = register_reader(client, "reader074")
        card = issue_card(client, admin_token, reader_id)
        title = add_title(client, admin_token, title="收缴书")
        item = add_item(client, admin_token, title["title_id"])

        loan = _borrow(client, librarian_token, card["card_no"], item["barcode"])
        force_overdue(session, loan["loan_id"], 21)
        fine = client.post(
            "/api/circulation/return",
            json={"barcode": item["barcode"]},
            headers=auth(librarian_token),
        ).json()["fine"]

        response = client.post(f"/api/fines/{fine['fine_id']}/collect", headers=auth(librarian_token))
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "PAID"
        assert body["operator_role"] == "LIBRARIAN"
        assert body["paid_at"] is not None

    def test_double_collect_rejected(self, client, librarian_token, admin_token, session):
        reader_id = register_reader(client, "reader075")
        card = issue_card(client, admin_token, reader_id)
        title = add_title(client, admin_token, title="重复收缴")
        item = add_item(client, admin_token, title["title_id"])

        loan = _borrow(client, librarian_token, card["card_no"], item["barcode"])
        force_overdue(session, loan["loan_id"], 21)
        fine = client.post(
            "/api/circulation/return",
            json={"barcode": item["barcode"]},
            headers=auth(librarian_token),
        ).json()["fine"]

        client.post(f"/api/fines/{fine['fine_id']}/collect", headers=auth(librarian_token))
        second = client.post(
            f"/api/fines/{fine['fine_id']}/collect", headers=auth(librarian_token)
        )
        assert second.status_code == 400
        assert second.json()["error"]["code"] == "FINE_ALREADY_PAID"

    def test_unknown_fine(self, client, librarian_token):
        response = client.post("/api/fines/9999/collect", headers=auth(librarian_token))
        assert response.status_code == 404


class TestReservationHandoverOnReturn:
    """TC-036 归还触发预约预留（BR-024a）。"""

    def _setup(self, client, librarian_token, admin_token):
        owner_id = register_reader(client, "reader080")
        owner_card = issue_card(client, admin_token, owner_id)
        title = add_title(client, admin_token, title="预约交接书")
        item = add_item(client, admin_token, title["title_id"])
        _borrow(client, librarian_token, owner_card["card_no"], item["barcode"])

        reserver_id = register_reader(client, "reader081")
        issue_card(client, admin_token, reserver_id)
        token = client.post(
            "/api/auth/login",
            json={"username": "reader081", "password": "reader123", "role": "READER"},
        ).json()["access_token"]
        reservation = client.post(
            "/api/reservations", json={"title_id": title["title_id"]}, headers=auth(token)
        )
        assert reservation.status_code == 201, reservation.text
        return item, token, reservation.json()

    def test_return_reserves_item_and_readies_head(self, client, librarian_token, admin_token):
        item, _, _ = self._setup(client, librarian_token, admin_token)

        body = client.post(
            "/api/circulation/return",
            json={"barcode": item["barcode"]},
            headers=auth(librarian_token),
        ).json()

        assert body["item_status"] == "RESERVED"
        assert body["reservation_advanced"]["status"] == "READY"

    def test_reserved_item_not_available_in_search(self, client, librarian_token, admin_token):
        item, _, _ = self._setup(client, librarian_token, admin_token)
        client.post(
            "/api/circulation/return",
            json={"barcode": item["barcode"]},
            headers=auth(librarian_token),
        )
        found = client.get("/api/books", params={"keyword": "预约交接书"}).json()
        assert found["items"][0]["available_items"] == 0  # BR-024：不进入可借状态

    def test_reserver_sees_ready_status(self, client, librarian_token, admin_token):
        item, token, _ = self._setup(client, librarian_token, admin_token)
        client.post(
            "/api/circulation/return",
            json={"barcode": item["barcode"]},
            headers=auth(librarian_token),
        )
        mine = client.get("/api/me/reservations", headers=auth(token)).json()
        assert mine[0]["status"] == "READY"
        assert mine[0]["ready_at"] is not None
        assert mine[0]["expires_at"] is not None
