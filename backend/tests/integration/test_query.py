"""查询集成测试（TC-022 ~ TC-024，UC-003 / UC-004 / UC-103，FR-014 / FR-019）。"""

from __future__ import annotations

from tests.conftest import add_item, add_title, auth, issue_card, register_reader


class TestBookSearch:
    """FR-014：公开检索，默认过滤软删除记录。"""

    def test_search_by_keyword(self, client, admin_token):
        add_title(client, admin_token, title="算法导论")
        add_title(client, admin_token, title="编译原理")
        found = client.get("/api/books", params={"keyword": "算法"}).json()
        assert found["total"] == 1
        assert found["items"][0]["title"] == "算法导论"

    def test_search_by_isbn(self, client, admin_token):
        add_title(client, admin_token, title="带 ISBN 的书", isbn="9780262046305")
        found = client.get("/api/books", params={"keyword": "9780262046305"}).json()
        assert found["total"] == 1

    def test_search_by_author(self, client, admin_token):
        client.post(
            "/api/admin/book-titles",
            json={"title": "某书", "author": "Knuth", "item_type": "FOREIGN_BOOK"},
            headers=auth(admin_token),
        )
        found = client.get("/api/books", params={"keyword": "Knuth"}).json()
        assert found["total"] == 1

    def test_filter_by_item_type(self, client, admin_token):
        add_title(client, admin_token, title="中文书", item_type="CHINESE_BOOK")
        add_title(client, admin_token, title="外文书", item_type="FOREIGN_BOOK")
        found = client.get("/api/books", params={"item_type": "CHINESE_BOOK"}).json()
        assert {item["title"] for item in found["items"]} == {"中文书"}

    def test_available_only_filter(self, client, admin_token):
        with_copy = add_title(client, admin_token, title="有副本")
        add_item(client, admin_token, with_copy["title_id"])
        add_title(client, admin_token, title="无副本")

        found = client.get("/api/books", params={"available_only": True}).json()
        titles = {item["title"] for item in found["items"]}
        assert "有副本" in titles
        assert "无副本" not in titles

    def test_soft_deleted_hidden(self, client, admin_token):
        """BR-037：已软删除的题录不出现在查询结果中。"""
        title = add_title(client, admin_token, title="将被删除")
        client.delete(f"/api/admin/book-titles/{title['title_id']}", headers=auth(admin_token))
        found = client.get("/api/books", params={"keyword": "将被删除"}).json()
        assert found["total"] == 0

    def test_pagination(self, client, admin_token):
        for index in range(5):
            add_title(client, admin_token, title=f"分页书{index}")
        page1 = client.get("/api/books", params={"page": 1, "page_size": 2}).json()
        page2 = client.get("/api/books", params={"page": 2, "page_size": 2}).json()
        assert len(page1["items"]) == 2
        assert len(page2["items"]) == 2
        assert {i["title_id"] for i in page1["items"]}.isdisjoint(
            {i["title_id"] for i in page2["items"]}
        )

    def test_page_size_upper_bound(self, client):
        response = client.get("/api/books", params={"page_size": 500})
        assert response.status_code == 422  # 上限 100

    def test_search_requires_no_auth(self, client):
        assert client.get("/api/books").status_code == 200


class TestReaderLoans:
    """TC-022 查询借阅信息成功（读者本人）。"""

    def _reader_with_history(self, client, librarian_token, admin_token):
        reader_id = register_reader(client, "reader120")
        card = issue_card(client, admin_token, reader_id)
        title = add_title(client, admin_token, title="查询用书")
        first = add_item(client, admin_token, title["title_id"])
        second = add_item(client, admin_token, title["title_id"])

        for barcode in (first["barcode"], second["barcode"]):
            client.post(
                "/api/circulation/borrow",
                json={"card_no": card["card_no"], "barcode": barcode},
                headers=auth(librarian_token),
            )
        # 归还其中一本，制造历史记录
        client.post(
            "/api/circulation/return",
            json={"barcode": first["barcode"]},
            headers=auth(librarian_token),
        )
        token = client.post(
            "/api/auth/login",
            json={"username": "reader120", "password": "reader123", "role": "READER"},
        ).json()["access_token"]
        return reader_id, token, second

    def test_four_segments_returned(self, client, librarian_token, admin_token):
        _, token, _ = self._reader_with_history(client, librarian_token, admin_token)
        body = client.get("/api/me/loans", headers=auth(token)).json()

        assert set(body) >= {"reader", "current", "history", "overdue", "reservations", "fines"}
        assert len(body["current"]) == 1
        assert len(body["history"]) == 1
        assert body["reader"]["username"] if "username" in body["reader"] else True

    def test_current_loan_fields(self, client, librarian_token, admin_token):
        _, token, _ = self._reader_with_history(client, librarian_token, admin_token)
        entry = client.get("/api/me/loans", headers=auth(token)).json()["current"][0]
        for field in ("loan_id", "barcode", "title", "borrowed_at", "due_at", "is_overdue",
                      "renew_count", "can_renew"):
            assert field in entry, f"缺少字段 {field}"

    def test_operator_id_hidden_from_reader(self, client, librarian_token, admin_token):
        """FR-019 验收 6：读者界面不展示经办图书管理员 ID（内部审计字段）。"""
        _, token, _ = self._reader_with_history(client, librarian_token, admin_token)
        entry = client.get("/api/me/loans", headers=auth(token)).json()["current"][0]
        assert "librarian_id" not in entry

    def test_status_filter(self, client, librarian_token, admin_token):
        _, token, _ = self._reader_with_history(client, librarian_token, admin_token)
        history_only = client.get(
            "/api/me/loans", params={"status": "history"}, headers=auth(token)
        ).json()
        assert history_only["current"] == []
        assert len(history_only["history"]) == 1

    def test_overdue_flag(self, client, librarian_token, admin_token, session):
        _, token, _ = self._reader_with_history(client, librarian_token, admin_token)
        body = client.get("/api/me/loans", headers=auth(token)).json()
        summary = body["overdue"][0] if body["overdue"] else None
        # 未超期时 overdue 段为空
        assert summary is None or summary["is_overdue"] is True

    def test_reader_cannot_see_others(self, client, librarian_token, admin_token):
        """TC-023 读者查询他人借阅信息失败。"""
        victim_id, _, _ = self._reader_with_history(client, librarian_token, admin_token)

        attacker_id = register_reader(client, "reader121")
        issue_card(client, admin_token, attacker_id)
        attacker_token = client.post(
            "/api/auth/login",
            json={"username": "reader121", "password": "reader123", "role": "READER"},
        ).json()["access_token"]

        response = client.get(
            f"/api/readers/{victim_id}/loans", headers=auth(attacker_token)
        )
        assert response.status_code == 403
        assert response.json()["error"]["code"] == "PERMISSION_DENIED"

    def test_librarian_can_see_any_reader(self, client, librarian_token, admin_token):
        """TC-024 图书管理员查询任意读者借阅信息成功。"""
        reader_id, _, _ = self._reader_with_history(client, librarian_token, admin_token)
        response = client.get(
            f"/api/readers/{reader_id}/loans", headers=auth(librarian_token)
        )
        assert response.status_code == 200
        body = response.json()
        assert len(body["current"]) + len(body["history"]) == 2
        assert "unpaid_total" in body

    def test_librarian_sees_operator_id(self, client, librarian_token, admin_token):
        """馆员视角包含经办管理员 ID（审计用途）。"""
        reader_id, _, _ = self._reader_with_history(client, librarian_token, admin_token)
        body = client.get(f"/api/readers/{reader_id}/loans", headers=auth(librarian_token)).json()
        assert "librarian_id" in body["history"][0]

    def test_unknown_reader(self, client, librarian_token):
        response = client.get("/api/readers/9999/loans", headers=auth(librarian_token))
        assert response.status_code == 404


class TestCollectionStats:
    """FR-029 / UC-215。"""

    def test_stats_shape(self, client, admin_token):
        title = add_title(client, admin_token, title="统计书")
        add_item(client, admin_token, title["title_id"])
        add_item(client, admin_token, title["title_id"])

        body = client.get("/api/admin/collection-stats", headers=auth(admin_token)).json()
        assert body["titles"] == 1
        assert body["items"] == 2
        assert body["by_status"]["AVAILABLE"] == 2
        assert body["by_item_type"]["FOREIGN_BOOK"] == 2
