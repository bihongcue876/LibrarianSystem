"""借书集成测试（TC-008 ~ TC-014，UC-101 / FR-015 / FR-016）。

重点验证三件事：

1. **六项校验的固定顺序**——错误码必须按顺序报，不能乱序
2. **失败时事务回滚**——副本状态不得残留变更、不得产生 `Loan`
3. **`due_at` 按读者类型快照**——GRADUATE 为 60 天
"""

from __future__ import annotations

from datetime import timedelta

from tests.conftest import (
    add_item,
    add_title,
    auth,
    force_overdue,
    issue_card,
    register_reader,
)


class TestBorrowSuccess:
    """TC-009 借书成功。"""

    def test_borrow_success(self, client, librarian_token, graduate_setup):
        response = client.post(
            "/api/circulation/borrow",
            json={
                "card_no": graduate_setup["card_no"],
                "barcode": graduate_setup["barcode"],
            },
            headers=auth(librarian_token),
        )
        assert response.status_code == 201, response.text
        body = response.json()
        assert body["status"] == "BORROWED"
        assert body["remaining_quota"] == 9  # GRADUATE 上限 10

    def test_due_at_follows_reader_type(self, client, librarian_token, graduate_setup):
        """`due_at` = 借出时刻 + 该读者类型的借阅天数（GRADUATE 60 天）。"""
        body = client.post(
            "/api/circulation/borrow",
            json={"card_no": graduate_setup["card_no"], "barcode": graduate_setup["barcode"]},
            headers=auth(librarian_token),
        ).json()

        from datetime import datetime

        borrowed = datetime.fromisoformat(body["borrowed_at"])
        due = datetime.fromisoformat(body["due_at"])
        assert (due - borrowed) == timedelta(days=60)

    def test_item_becomes_borrowed(self, client, librarian_token, graduate_setup, admin_token):
        """TC-014 借书成功更新副本状态为 BORROWED。"""
        client.post(
            "/api/circulation/borrow",
            json={"card_no": graduate_setup["card_no"], "barcode": graduate_setup["barcode"]},
            headers=auth(librarian_token),
        )
        found = client.get("/api/books", params={"keyword": "算法导论"}).json()
        assert found["items"][0]["available_items"] == 0

    def test_same_reader_can_borrow_multiple_copies_of_one_title(self, client, librarian_token, graduate_setup, admin_token):
        """BR-013：允许同一读者借阅同一标题的多个副本。"""
        second = add_item(client, admin_token, graduate_setup["title_id"])
        first = client.post(
            "/api/circulation/borrow",
            json={"card_no": graduate_setup["card_no"], "barcode": graduate_setup["barcode"]},
            headers=auth(librarian_token),
        )
        second_attempt = client.post(
            "/api/circulation/borrow",
            json={"card_no": graduate_setup["card_no"], "barcode": second["barcode"]},
            headers=auth(librarian_token),
        )
        assert first.status_code == 201
        assert second_attempt.status_code == 201


class TestBorrowPreCheck:
    """FR-015 预检查：只读，返回读者信息与三项告警。"""

    def test_precheck_reports_quota_and_alerts(self, client, librarian_token, graduate_setup):
        response = client.post(
            "/api/circulation/precheck",
            json={"card_no": graduate_setup["card_no"], "barcode": graduate_setup["barcode"]},
            headers=auth(librarian_token),
        )
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["reader"]["reader_type"] == "GRADUATE"
        assert body["quota"] == {"limit": 10, "occupied": 0, "remaining": 10}
        assert body["alerts"] == {
            "has_overdue": False,
            "has_unpaid_fine": False,
            "has_due_soon": False,
        }
        assert body["can_borrow"] is True

    def test_precheck_is_read_only(self, client, librarian_token, graduate_setup, session):
        """FR-015 验收 5：不产生任何数据变更。"""
        from tests.conftest import loan_rows

        client.post(
            "/api/circulation/precheck",
            json={"card_no": graduate_setup["card_no"], "barcode": graduate_setup["barcode"]},
            headers=auth(librarian_token),
        )
        assert loan_rows(session) == []

    def test_precheck_reports_invalid_card(self, client, librarian_token, graduate_setup):
        response = client.post(
            "/api/circulation/precheck",
            json={"card_no": "CARD2026999999", "barcode": graduate_setup["barcode"]},
            headers=auth(librarian_token),
        )
        assert response.status_code == 200
        body = response.json()
        assert body["can_borrow"] is False
        assert body["checks"][0]["code"] == "CARD_INVALID"


class TestBorrowFailures:
    """TC-008 借阅证无效时借书失败。"""

    def test_missing_card(self, client, librarian_token, graduate_setup, session):
        from tests.conftest import loan_rows

        response = client.post(
            "/api/circulation/borrow",
            json={"card_no": "CARD2026999999", "barcode": graduate_setup["barcode"]},
            headers=auth(librarian_token),
        )
        assert response.status_code == 400
        assert response.json()["error"]["code"] == "CARD_INVALID"
        assert loan_rows(session) == []

    def test_suspended_card(self, client, librarian_token, admin_token, graduate_setup, session):
        from tests.conftest import loan_rows

        listed = client.get(
            f"/api/admin/readers/{graduate_setup['reader_id']}/borrow-cards",
            headers=auth(admin_token),
        ).json()
        client.post(
            f"/api/admin/borrow-cards/{listed[0]['card_id']}/suspend", headers=auth(admin_token)
        )

        response = client.post(
            "/api/circulation/borrow",
            json={"card_no": graduate_setup["card_no"], "barcode": graduate_setup["barcode"]},
            headers=auth(librarian_token),
        )
        assert response.status_code == 400
        assert response.json()["error"]["code"] == "CARD_INVALID"
        assert loan_rows(session) == []

    def test_cancelled_card(self, client, librarian_token, admin_token, graduate_setup):
        listed = client.get(
            f"/api/admin/readers/{graduate_setup['reader_id']}/borrow-cards",
            headers=auth(admin_token),
        ).json()
        client.post(
            f"/api/admin/borrow-cards/{listed[0]['card_id']}/cancel",
            json={},
            headers=auth(admin_token),
        )
        response = client.post(
            "/api/circulation/borrow",
            json={"card_no": graduate_setup["card_no"], "barcode": graduate_setup["barcode"]},
            headers=auth(librarian_token),
        )
        assert response.status_code == 400
        assert response.json()["error"]["code"] == "CARD_INVALID"

    """TC-010 超过借阅数量时借书失败。"""

    def test_borrow_limit_exceeded(self, client, librarian_token, admin_token, session):
        """按本科生（上限 5）构造：先借满，再借第 6 本。"""
        reader_id = register_reader(client, "reader050", "UNDERGRADUATE")
        card = issue_card(client, admin_token, reader_id)
        title = add_title(client, admin_token, title="额度测试")
        barcodes = [add_item(client, admin_token, title["title_id"])["barcode"] for _ in range(6)]

        for barcode in barcodes[:5]:
            ok = client.post(
                "/api/circulation/borrow",
                json={"card_no": card["card_no"], "barcode": barcode},
                headers=auth(librarian_token),
            )
            assert ok.status_code == 201, ok.text

        response = client.post(
            "/api/circulation/borrow",
            json={"card_no": card["card_no"], "barcode": barcodes[5]},
            headers=auth(librarian_token),
        )
        assert response.status_code == 400
        body = response.json()
        assert body["error"]["code"] == "BORROW_LIMIT_EXCEEDED"
        assert body["error"]["detail"] == {"current": 5, "limit": 5}

        from tests.conftest import loan_rows

        assert len(loan_rows(session)) == 5  # 第 6 本未创建记录

    def test_reservations_count_towards_quota(self, client, librarian_token, admin_token):
        """BR-007：有效预约占用额度——5 上限下 4 借阅 + 1 预约即满。"""
        reader_id = register_reader(client, "reader051", "UNDERGRADUATE")
        card = issue_card(client, admin_token, reader_id)

        # 造 4 本可借 + 1 个全部副本不可借的题录（供预约）
        available_title = add_title(client, admin_token, title="可借书")
        borrow_barcodes = [
            add_item(client, admin_token, available_title["title_id"])["barcode"] for _ in range(5)
        ]
        for barcode in borrow_barcodes[:4]:
            assert client.post(
                "/api/circulation/borrow",
                json={"card_no": card["card_no"], "barcode": barcode},
                headers=auth(librarian_token),
            ).status_code == 201

        reserved_title = add_title(client, admin_token, title="不可借书")
        reserved_item = add_item(client, admin_token, reserved_title["title_id"])
        # 让该题录下所有副本都不可借：借出（用另一个读者占住）
        other_id = register_reader(client, "reader052")
        other_card = issue_card(client, admin_token, other_id)
        client.post(
            "/api/circulation/borrow",
            json={"card_no": other_card["card_no"], "barcode": reserved_item["barcode"]},
            headers=auth(librarian_token),
        )

        token = client.post(
            "/api/auth/login",
            json={"username": "reader051", "password": "reader123", "role": "READER"},
        ).json()["access_token"]
        reservation = client.post(
            "/api/reservations",
            json={"title_id": reserved_title["title_id"]},
            headers=auth(token),
        )
        assert reservation.status_code == 201, reservation.text  # 第 5 个额度

        response = client.post(
            "/api/circulation/borrow",
            json={"card_no": card["card_no"], "barcode": borrow_barcodes[4]},
            headers=auth(librarian_token),
        )
        assert response.status_code == 400
        assert response.json()["error"]["code"] == "BORROW_LIMIT_EXCEEDED"

    """TC-011 存在超期未还图书时借书失败。"""

    def test_overdue_blocks_borrowing(self, client, librarian_token, admin_token, session):
        reader_id = register_reader(client, "reader053")
        card = issue_card(client, admin_token, reader_id)
        title = add_title(client, admin_token, title="超期测试")
        first = add_item(client, admin_token, title["title_id"])
        second = add_item(client, admin_token, title["title_id"])

        loan = client.post(
            "/api/circulation/borrow",
            json={"card_no": card["card_no"], "barcode": first["barcode"]},
            headers=auth(librarian_token),
        ).json()
        force_overdue(session, loan["loan_id"], 5)

        response = client.post(
            "/api/circulation/borrow",
            json={"card_no": card["card_no"], "barcode": second["barcode"]},
            headers=auth(librarian_token),
        )
        assert response.status_code == 400
        assert response.json()["error"]["code"] == "OVERDUE_LOAN_EXISTS"

    """TC-012 存在未缴罚款时借书失败。"""

    def test_unpaid_fine_blocks_borrowing(self, client, librarian_token, admin_token, session):
        reader_id = register_reader(client, "reader054")
        card = issue_card(client, admin_token, reader_id)
        title = add_title(client, admin_token, title="罚款测试")
        first = add_item(client, admin_token, title["title_id"])
        second = add_item(client, admin_token, title["title_id"])

        loan = client.post(
            "/api/circulation/borrow",
            json={"card_no": card["card_no"], "barcode": first["barcode"]},
            headers=auth(librarian_token),
        ).json()
        force_overdue(session, loan["loan_id"], 21)
        returned = client.post(
            "/api/circulation/return",
            json={"barcode": first["barcode"]},
            headers=auth(librarian_token),
        ).json()
        assert returned["fine"] is not None

        response = client.post(
            "/api/circulation/borrow",
            json={"card_no": card["card_no"], "barcode": second["barcode"]},
            headers=auth(librarian_token),
        )
        assert response.status_code == 400
        assert response.json()["error"]["code"] == "UNPAID_FINE_EXISTS"

    def test_borrowing_resumes_after_fine_paid(self, client, librarian_token, admin_token, session):
        reader_id = register_reader(client, "reader055")
        card = issue_card(client, admin_token, reader_id)
        title = add_title(client, admin_token, title="缴费后借书")
        first = add_item(client, admin_token, title["title_id"])
        second = add_item(client, admin_token, title["title_id"])

        loan = client.post(
            "/api/circulation/borrow",
            json={"card_no": card["card_no"], "barcode": first["barcode"]},
            headers=auth(librarian_token),
        ).json()
        force_overdue(session, loan["loan_id"], 21)
        fine = client.post(
            "/api/circulation/return",
            json={"barcode": first["barcode"]},
            headers=auth(librarian_token),
        ).json()["fine"]

        client.post(f"/api/fines/{fine['fine_id']}/collect", headers=auth(librarian_token))

        response = client.post(
            "/api/circulation/borrow",
            json={"card_no": card["card_no"], "barcode": second["barcode"]},
            headers=auth(librarian_token),
        )
        assert response.status_code == 201, response.text

    """TC-013 图书不可借时借书失败。"""

    def test_borrowed_item_cannot_be_borrowed_again(self, client, librarian_token, admin_token):
        reader_id = register_reader(client, "reader056")
        card = issue_card(client, admin_token, reader_id)
        other_id = register_reader(client, "reader057")
        other_card = issue_card(client, admin_token, other_id)
        title = add_title(client, admin_token, title="重复借出")
        item = add_item(client, admin_token, title["title_id"])

        client.post(
            "/api/circulation/borrow",
            json={"card_no": card["card_no"], "barcode": item["barcode"]},
            headers=auth(librarian_token),
        )
        response = client.post(
            "/api/circulation/borrow",
            json={"card_no": other_card["card_no"], "barcode": item["barcode"]},
            headers=auth(librarian_token),
        )
        assert response.status_code == 400
        assert response.json()["error"]["code"] == "ITEM_NOT_AVAILABLE"

    def test_unknown_barcode(self, client, librarian_token, graduate_setup):
        response = client.post(
            "/api/circulation/borrow",
            json={"card_no": graduate_setup["card_no"], "barcode": "BC99999999"},
            headers=auth(librarian_token),
        )
        assert response.status_code == 400
        assert response.json()["error"]["code"] == "ITEM_NOT_AVAILABLE"


class TestValidationOrder:
    """顺序固定：遇首个失败即返回，不累积错误。"""

    def test_quota_reported_before_overdue(self, client, librarian_token, admin_token, session):
        """同时超额与超期时，必须报额度（排在前）。"""
        reader_id = register_reader(client, "reader060", "UNDERGRADUATE")
        card = issue_card(client, admin_token, reader_id)
        title = add_title(client, admin_token, title="顺序一")
        barcodes = [add_item(client, admin_token, title["title_id"])["barcode"] for _ in range(6)]

        loans = []
        for barcode in barcodes[:5]:
            loans.append(
                client.post(
                    "/api/circulation/borrow",
                    json={"card_no": card["card_no"], "barcode": barcode},
                    headers=auth(librarian_token),
                ).json()
            )
        force_overdue(session, loans[0]["loan_id"], 10)  # 同时制造超期

        response = client.post(
            "/api/circulation/borrow",
            json={"card_no": card["card_no"], "barcode": barcodes[5]},
            headers=auth(librarian_token),
        )
        assert response.json()["error"]["code"] == "BORROW_LIMIT_EXCEEDED"

    def test_card_reported_before_item(self, client, librarian_token, graduate_setup):
        """借阅证与副本同时无效时，报借阅证（排在前）。"""
        response = client.post(
            "/api/circulation/borrow",
            json={"card_no": "CARD2026999999", "barcode": "BC99999999"},
            headers=auth(librarian_token),
        )
        assert response.json()["error"]["code"] == "CARD_INVALID"
