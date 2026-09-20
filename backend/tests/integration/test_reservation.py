"""预约集成测试（TC-025 ~ TC-030，UC-005 / UC-006 / FR-021 ~ FR-024）。"""

from __future__ import annotations

from itertools import count

from tests.conftest import add_item, add_title, auth, issue_card, register_reader

#: 生成唯一的 ASCII 用户名后缀——用户名受 `^[A-Za-z0-9_]+$` 约束，
#: 不能直接用中文书名拼接（否则注册会被 422 拒绝）。
_SEQ = count(1)


def _holder_setup(client, librarian_token, admin_token, title_name: str, copies: int = 1):
    """造一个「所有副本均被借出」的题录（预约的前提，BR-020）。

    返回 `(title, reserver_reader_id, reserver_token)`。
    """
    seq = next(_SEQ)
    owner_username = f"owner_{seq}"
    reserver_username = f"reserver_{seq}"

    owner_id = register_reader(client, owner_username)
    owner_card = issue_card(client, admin_token, owner_id)
    title = add_title(client, admin_token, title=title_name)
    for _ in range(copies):
        item = add_item(client, admin_token, title["title_id"])
        response = client.post(
            "/api/circulation/borrow",
            json={"card_no": owner_card["card_no"], "barcode": item["barcode"]},
            headers=auth(librarian_token),
        )
        assert response.status_code == 201, response.text

    reserver_id = register_reader(client, reserver_username)
    issue_card(client, admin_token, reserver_id)
    token = client.post(
        "/api/auth/login",
        json={"username": reserver_username, "password": "reader123", "role": "READER"},
    ).json()["access_token"]
    return title, reserver_id, token


class TestCreateReservation:
    """TC-025 预约图书成功。"""

    def test_create_success(self, client, librarian_token, admin_token):
        title, _, token = _holder_setup(client, librarian_token, admin_token, "预约书A")
        response = client.post(
            "/api/reservations", json={"title_id": title["title_id"]}, headers=auth(token)
        )
        assert response.status_code == 201, response.text
        body = response.json()
        assert body["status"] == "ACTIVE"
        assert body["queue_position"] == 1
        assert body["created_at"] is not None
        assert body["expires_at"] is not None

    def test_expiry_is_seven_days(self, client, librarian_token, admin_token):
        from datetime import datetime, timedelta

        title, _, token = _holder_setup(client, librarian_token, admin_token, "预约书B")
        body = client.post(
            "/api/reservations", json={"title_id": title["title_id"]}, headers=auth(token)
        ).json()
        created = datetime.fromisoformat(body["created_at"])
        expires = datetime.fromisoformat(body["expires_at"])
        assert expires - created == timedelta(days=7)  # BR-025

    def test_reader_id_taken_from_token_not_body(self, client, librarian_token, admin_token):
        """BR-039：预约人取自 JWT，请求体中的 `reader_id` 不被接受。"""
        title, reserver_id, token = _holder_setup(client, librarian_token, admin_token, "预约书C")
        body = client.post(
            "/api/reservations",
            json={"title_id": title["title_id"], "reader_id": 99999},
            headers=auth(token),
        ).json()
        assert body["reader_id"] == reserver_id

    """TC-026 重复预约失败。"""

    def test_duplicate_rejected(self, client, librarian_token, admin_token):
        title, _, token = _holder_setup(client, librarian_token, admin_token, "预约书D")
        first = client.post(
            "/api/reservations", json={"title_id": title["title_id"]}, headers=auth(token)
        )
        assert first.status_code == 201

        second = client.post(
            "/api/reservations", json={"title_id": title["title_id"]}, headers=auth(token)
        )
        assert second.status_code == 409
        assert second.json()["error"]["code"] == "DUPLICATE_RESERVATION"

    def test_past_reservation_does_not_block_new_one(self, client, librarian_token, admin_token, session):
        """已取消的预约不占用唯一性。"""
        title, _, token = _holder_setup(client, librarian_token, admin_token, "预约书E")
        created = client.post(
            "/api/reservations", json={"title_id": title["title_id"]}, headers=auth(token)
        ).json()
        client.delete(f"/api/reservations/{created['reservation_id']}", headers=auth(token))

        again = client.post(
            "/api/reservations", json={"title_id": title["title_id"]}, headers=auth(token)
        )
        assert again.status_code == 201

    """TC-027 有可借副本时预约失败。"""

    def test_available_copy_blocks_reservation(self, client, admin_token):
        reader_id = register_reader(client, "reader100")
        issue_card(client, admin_token, reader_id)
        token = client.post(
            "/api/auth/login",
            json={"username": "reader100", "password": "reader123", "role": "READER"},
        ).json()["access_token"]

        title = add_title(client, admin_token, title="有货的书")
        add_item(client, admin_token, title["title_id"])

        response = client.post(
            "/api/reservations", json={"title_id": title["title_id"]}, headers=auth(token)
        )
        assert response.status_code == 400
        assert response.json()["error"]["code"] == "ITEM_AVAILABLE_NO_RESERVATION"

    def test_lost_copy_is_not_available_so_reservation_allowed(
        self, client, librarian_token, admin_token
    ):
        """`LOST`/`DAMAGED`/`REMOVED` 均不算可借，故可预约。"""
        reader_id = register_reader(client, "reader101")
        issue_card(client, admin_token, reader_id)
        token = client.post(
            "/api/auth/login",
            json={"username": "reader101", "password": "reader123", "role": "READER"},
        ).json()["access_token"]

        title = add_title(client, admin_token, title="丢失的书")
        item = add_item(client, admin_token, title["title_id"])
        client.post(
            f"/api/admin/library-items/{item['item_id']}/status",
            json={"status": "LOST"},
            headers=auth(admin_token),
        )
        response = client.post(
            "/api/reservations", json={"title_id": title["title_id"]}, headers=auth(token)
        )
        assert response.status_code == 201

    """TC-028 预约队列已满失败。"""

    def test_queue_full(self, client, librarian_token, admin_token):
        title, _, _ = _holder_setup(client, librarian_token, admin_token, "队列满的书")

        for index in range(5):
            reader_id = register_reader(client, f"queue{index}")
            issue_card(client, admin_token, reader_id)
            token = client.post(
                "/api/auth/login",
                json={"username": f"queue{index}", "password": "reader123", "role": "READER"},
            ).json()["access_token"]
            created = client.post(
                "/api/reservations", json={"title_id": title["title_id"]}, headers=auth(token)
            )
            assert created.status_code == 201, created.text

        sixth_id = register_reader(client, "queue5")
        issue_card(client, admin_token, sixth_id)
        sixth_token = client.post(
            "/api/auth/login",
            json={"username": "queue5", "password": "reader123", "role": "READER"},
        ).json()["access_token"]

        response = client.post(
            "/api/reservations", json={"title_id": title["title_id"]}, headers=auth(sixth_token)
        )
        assert response.status_code == 409
        assert response.json()["error"]["code"] == "RESERVATION_QUEUE_FULL"

    def test_requires_valid_card(self, client, librarian_token, admin_token):
        """FR-021 验收 5：无有效借阅证不可预约。"""
        title, _, _ = _holder_setup(client, librarian_token, admin_token, "需借阅证的书")
        register_reader(client, "reader102")  # 不办证
        token = client.post(
            "/api/auth/login",
            json={"username": "reader102", "password": "reader123", "role": "READER"},
        ).json()["access_token"]

        response = client.post(
            "/api/reservations", json={"title_id": title["title_id"]}, headers=auth(token)
        )
        assert response.status_code == 400
        assert response.json()["error"]["code"] == "CARD_REQUIRED"

    def test_unknown_title(self, client, admin_token):
        reader_id = register_reader(client, "reader103")
        issue_card(client, admin_token, reader_id)
        token = client.post(
            "/api/auth/login",
            json={"username": "reader103", "password": "reader123", "role": "READER"},
        ).json()["access_token"]

        response = client.post("/api/reservations", json={"title_id": 9999}, headers=auth(token))
        assert response.status_code == 404


class TestQueueOrder:
    """TC-029 预约排队顺序按创建时间。"""

    def test_positions_follow_creation_order(self, client, librarian_token, admin_token):
        title, _, _ = _holder_setup(client, librarian_token, admin_token, "排队书")
        positions = []
        for index in range(3):
            reader_id = register_reader(client, f"order{index}")
            issue_card(client, admin_token, reader_id)
            token = client.post(
                "/api/auth/login",
                json={"username": f"order{index}", "password": "reader123", "role": "READER"},
            ).json()["access_token"]
            body = client.post(
                "/api/reservations", json={"title_id": title["title_id"]}, headers=auth(token)
            ).json()
            positions.append(body["queue_position"])

        assert positions == [1, 2, 3]

    def test_position_shifts_after_cancel(self, client, librarian_token, admin_token):
        title, _, _ = _holder_setup(client, librarian_token, admin_token, "顺延书")
        tokens = []
        created_ids = []
        for index in range(3):
            reader_id = register_reader(client, f"shift{index}")
            issue_card(client, admin_token, reader_id)
            token = client.post(
                "/api/auth/login",
                json={"username": f"shift{index}", "password": "reader123", "role": "READER"},
            ).json()["access_token"]
            tokens.append(token)
            created_ids.append(
                client.post(
                    "/api/reservations", json={"title_id": title["title_id"]}, headers=auth(token)
                ).json()["reservation_id"]
            )

        client.delete(f"/api/reservations/{created_ids[0]}", headers=auth(tokens[0]))

        mine = client.get("/api/me/reservations", headers=auth(tokens[1])).json()
        assert mine[0]["queue_position"] == 1


class TestCancelReservation:
    """TC-030 取消预约成功。"""

    def test_cancel_active(self, client, librarian_token, admin_token):
        title, _, token = _holder_setup(client, librarian_token, admin_token, "取消书A")
        created = client.post(
            "/api/reservations", json={"title_id": title["title_id"]}, headers=auth(token)
        ).json()

        response = client.delete(f"/api/reservations/{created['reservation_id']}", headers=auth(token))
        assert response.status_code == 200
        assert response.json()["status"] == "CANCELLED"

    def test_cancel_others_reservation_rejected(self, client, librarian_token, admin_token):
        title, _, token = _holder_setup(client, librarian_token, admin_token, "取消书B")
        created = client.post(
            "/api/reservations", json={"title_id": title["title_id"]}, headers=auth(token)
        ).json()

        other_id = register_reader(client, "reader110")
        issue_card(client, admin_token, other_id)
        other_token = client.post(
            "/api/auth/login",
            json={"username": "reader110", "password": "reader123", "role": "READER"},
        ).json()["access_token"]

        response = client.delete(
            f"/api/reservations/{created['reservation_id']}", headers=auth(other_token)
        )
        assert response.status_code == 403

    def test_cancel_twice_rejected(self, client, librarian_token, admin_token):
        title, _, token = _holder_setup(client, librarian_token, admin_token, "取消书C")
        created = client.post(
            "/api/reservations", json={"title_id": title["title_id"]}, headers=auth(token)
        ).json()
        client.delete(f"/api/reservations/{created['reservation_id']}", headers=auth(token))

        second = client.delete(
            f"/api/reservations/{created['reservation_id']}", headers=auth(token)
        )
        assert second.status_code == 400  # FR-022 验收 4

    def test_ready_reservation_can_be_cancelled_and_hands_over(
        self, client, librarian_token, admin_token, session
    ):
        """BR-025a + BR-024a：`READY` 可取消；副本**转交下一位并保持 RESERVED**。"""
        title, _, _ = _holder_setup(client, librarian_token, admin_token, "交接书X")

        first_id = register_reader(client, "hand1")
        issue_card(client, admin_token, first_id)
        first_token = client.post(
            "/api/auth/login",
            json={"username": "hand1", "password": "reader123", "role": "READER"},
        ).json()["access_token"]
        first_res = client.post(
            "/api/reservations", json={"title_id": title["title_id"]}, headers=auth(first_token)
        ).json()

        second_id = register_reader(client, "hand2")
        issue_card(client, admin_token, second_id)
        second_token = client.post(
            "/api/auth/login",
            json={"username": "hand2", "password": "reader123", "role": "READER"},
        ).json()["access_token"]
        client.post(
            "/api/reservations", json={"title_id": title["title_id"]}, headers=auth(second_token)
        )

        # 归还 → 队首（hand1）置 READY、副本置 RESERVED
        returned = _return_borrowed_copy(client, librarian_token, session, title["title_id"])
        assert returned["item_status"] == "RESERVED"
        assert returned["reservation_advanced"]["status"] == "READY"

        # hand1 取消 → 副本转交 hand2，仍为 RESERVED
        cancelled = client.delete(
            f"/api/reservations/{first_res['reservation_id']}", headers=auth(first_token)
        )
        assert cancelled.status_code == 200

        second_after = client.get("/api/me/reservations", headers=auth(second_token)).json()
        assert second_after[0]["status"] == "READY"
        assert second_after[0]["queue_position"] == 1

        found = client.get("/api/books", params={"keyword": "交接书X"}).json()
        assert found["items"][0]["available_items"] == 0  # 副本仍 RESERVED，未释放

    def test_cancel_when_queue_empty_releases_item(
        self, client, librarian_token, admin_token, session
    ):
        """队列已空时才释放为 `AVAILABLE`（BR-024a）。"""
        title, _, _ = _holder_setup(client, librarian_token, admin_token, "释放书Y")
        single_id = register_reader(client, "solo1")
        issue_card(client, admin_token, single_id)
        token = client.post(
            "/api/auth/login",
            json={"username": "solo1", "password": "reader123", "role": "READER"},
        ).json()["access_token"]
        created = client.post(
            "/api/reservations", json={"title_id": title["title_id"]}, headers=auth(token)
        ).json()

        returned = _return_borrowed_copy(client, librarian_token, session, title["title_id"])
        assert returned["item_status"] == "RESERVED"

        client.delete(f"/api/reservations/{created['reservation_id']}", headers=auth(token))

        found = client.get("/api/books", params={"keyword": "释放书Y"}).json()
        assert found["items"][0]["available_items"] == 1


def _return_borrowed_copy(client, librarian_token, session, title_id: int) -> dict:
    """找出该题录下仍在借的副本并归还，返回还书响应。

    通过测试库直接定位条码——API 没有「按题录查副本」的端点，
    而测试需要拿到具体副本才能触发还书。
    """
    from sqlalchemy import select

    from app.infrastructure.models import LibraryItemModel, LoanModel

    row = session.scalar(
        select(LibraryItemModel)
        .join(LoanModel, LoanModel.item_id == LibraryItemModel.item_id)
        .where(
            LibraryItemModel.title_id == title_id,
            LoanModel.status == "BORROWED",
        )
    )
    assert row is not None, f"题录 {title_id} 下没有在借副本"

    response = client.post(
        "/api/circulation/return",
        json={"barcode": row.barcode},
        headers=auth(librarian_token),
    )
    assert response.status_code == 200, response.text
    return response.json()
