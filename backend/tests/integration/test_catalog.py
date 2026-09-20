"""书目与馆藏集成测试（TC-033、TC-034，UC-208 ~ UC-212）。"""

from __future__ import annotations

import re

from tests.conftest import add_item, add_title, auth, register_reader


class TestBookTitle:
    """TC-033 添加图书标题成功。"""

    def test_add_title_success(self, client, admin_token):
        response = client.post(
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
        )
        assert response.status_code == 201, response.text
        body = response.json()
        assert body["title"] == "算法导论"
        assert body["total_items"] == 0
        assert body["available_items"] == 0

    def test_title_without_items_allowed(self, client, admin_token):
        """BR-014：允许题录在无任何副本的状态下存在。"""
        title = add_title(client, admin_token, title="待采购的书")
        assert title["total_items"] == 0

    def test_duplicate_active_isbn_rejected(self, client, admin_token):
        add_title(client, admin_token, title="书一", isbn="9780262046305")
        response = client.post(
            "/api/admin/book-titles",
            json={"title": "书二", "author": "x", "item_type": "FOREIGN_BOOK", "isbn": "9780262046305"},
            headers=auth(admin_token),
        )
        assert response.status_code == 409
        assert response.json()["error"]["code"] == "ISBN_EXISTS"

    def test_isbn_partial_unique_index_allows_repurchase(self, client, admin_token):
        """`13` §4.5：ISBN 为**部分唯一索引**——已软删除题录不阻塞重新采购。"""
        title = add_title(client, admin_token, title="书一", isbn="9780262046305")
        client.delete(f"/api/admin/book-titles/{title['title_id']}", headers=auth(admin_token))

        response = client.post(
            "/api/admin/book-titles",
            json={"title": "书一（重新采购）", "author": "x", "item_type": "FOREIGN_BOOK",
                  "isbn": "9780262046305"},
            headers=auth(admin_token),
        )
        assert response.status_code == 201, response.text

    def test_invalid_isbn_rejected(self, client, admin_token):
        response = client.post(
            "/api/admin/book-titles",
            json={"title": "坏 ISBN", "author": "x", "item_type": "FOREIGN_BOOK",
                  "isbn": "9780262046306"},
            headers=auth(admin_token),
        )
        assert response.status_code == 400
        assert response.json()["error"]["code"] == "INVALID_ISBN"

    def test_invalid_item_type_rejected(self, client, admin_token):
        response = client.post(
            "/api/admin/book-titles",
            json={"title": "坏类型", "author": "x", "item_type": "DVD"},
            headers=auth(admin_token),
        )
        assert response.status_code == 422


class TestLibraryItem:
    """TC-034 添加馆藏副本成功。"""

    def test_add_item_success(self, client, admin_token):
        title = add_title(client, admin_token)
        response = client.post(
            "/api/admin/library-items",
            json={"title_id": title["title_id"], "location": "A-3-12", "price": "128.00"},
            headers=auth(admin_token),
        )
        assert response.status_code == 201, response.text
        body = response.json()
        assert re.match(r"^BC\d{8}$", body["barcode"])
        assert body["status"] == "AVAILABLE"
        assert body["price"] == "128.00"

    def test_barcodes_unique(self, client, admin_token):
        title = add_title(client, admin_token)
        first = add_item(client, admin_token, title["title_id"])
        second = add_item(client, admin_token, title["title_id"])
        assert first["barcode"] != second["barcode"]

    def test_item_type_inherited_from_title(self, client, admin_token):
        title = add_title(client, admin_token, item_type="THESIS")
        item = add_item(client, admin_token, title["title_id"])
        assert item["item_type"] == "THESIS"

    def test_available_count_reflected_in_search(self, client, admin_token):
        title = add_title(client, admin_token, title="检索用书")
        add_item(client, admin_token, title["title_id"])
        add_item(client, admin_token, title["title_id"])
        found = client.get("/api/books", params={"keyword": "检索用书"}).json()
        assert found["items"][0]["available_items"] == 2

    def test_title_not_found(self, client, admin_token):
        response = client.post(
            "/api/admin/library-items", json={"title_id": 9999}, headers=auth(admin_token)
        )
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "TITLE_NOT_FOUND"


class TestDeleteAndMark:
    def test_delete_title_cascades_removed(self, client, admin_token):
        """FR-011 验收 3：副本同步置 `REMOVED`。"""
        title = add_title(client, admin_token)
        item = add_item(client, admin_token, title["title_id"])
        client.delete(f"/api/admin/book-titles/{title['title_id']}", headers=auth(admin_token))

        remaining = client.get("/api/books", params={"keyword": title["title"]}).json()
        assert remaining["items"] == []  # BR-037：软删除记录对读者不可见

        marked = client.post(
            f"/api/admin/library-items/{item['item_id']}/status",
            json={"status": "AVAILABLE"},
            headers=auth(admin_token),
        )
        assert marked.status_code == 400  # 已 REMOVED → 非法流转

    def test_delete_title_with_borrowed_item_does_not_fail(self, client, admin_token, librarian_token):
        """FR-011 验收 4：存在未归还副本时删除**不失败**。"""
        reader_id = register_reader(client, "reader040")
        card = client.post(
            "/api/admin/borrow-cards", json={"reader_id": reader_id}, headers=auth(admin_token)
        ).json()
        title = add_title(client, admin_token)
        item = add_item(client, admin_token, title["title_id"])

        borrowed = client.post(
            "/api/circulation/borrow",
            json={"card_no": card["card_no"], "barcode": item["barcode"]},
            headers=auth(librarian_token),
        )
        assert borrowed.status_code == 201, borrowed.text

        response = client.delete(
            f"/api/admin/book-titles/{title['title_id']}", headers=auth(admin_token)
        )
        assert response.status_code == 200

    def test_delete_borrowed_item_rejected(self, client, admin_token, librarian_token):
        """FR-013 验收 4：`BORROWED` 副本不允许直接删除（400）。"""
        reader_id = register_reader(client, "reader041")
        card = client.post(
            "/api/admin/borrow-cards", json={"reader_id": reader_id}, headers=auth(admin_token)
        ).json()
        title = add_title(client, admin_token)
        item = add_item(client, admin_token, title["title_id"])
        client.post(
            "/api/circulation/borrow",
            json={"card_no": card["card_no"], "barcode": item["barcode"]},
            headers=auth(librarian_token),
        )

        response = client.delete(
            f"/api/admin/library-items/{item['item_id']}", headers=auth(admin_token)
        )
        assert response.status_code == 400

    def test_mark_lost_blocks_borrowing(self, client, admin_token, librarian_token):
        """FR-013 验收 3：`LOST`/`DAMAGED`/`REMOVED` 均不可借。"""
        title = add_title(client, admin_token)
        item = add_item(client, admin_token, title["title_id"])
        client.post(
            f"/api/admin/library-items/{item['item_id']}/status",
            json={"status": "LOST"},
            headers=auth(admin_token),
        )
        reader_id = register_reader(client, "reader042")
        card = client.post(
            "/api/admin/borrow-cards", json={"reader_id": reader_id}, headers=auth(admin_token)
        ).json()

        response = client.post(
            "/api/circulation/borrow",
            json={"card_no": card["card_no"], "barcode": item["barcode"]},
            headers=auth(librarian_token),
        )
        assert response.status_code == 400
        assert response.json()["error"]["code"] == "ITEM_NOT_AVAILABLE"

    def test_mark_damaged_then_restore(self, client, admin_token):
        title = add_title(client, admin_token)
        item = add_item(client, admin_token, title["title_id"])
        damaged = client.post(
            f"/api/admin/library-items/{item['item_id']}/status",
            json={"status": "DAMAGED"},
            headers=auth(admin_token),
        )
        assert damaged.json()["status"] == "DAMAGED"
        restored = client.post(
            f"/api/admin/library-items/{item['item_id']}/status",
            json={"status": "AVAILABLE"},
            headers=auth(admin_token),
        )
        assert restored.json()["status"] == "AVAILABLE"
