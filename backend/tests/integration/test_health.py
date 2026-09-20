"""TASK-001 验收：应用可启动、健康检查可用。"""

from __future__ import annotations


def test_health(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["service"] == "library-management-system"


def test_openapi_contains_core_endpoints(client):
    """核心接口必须出现在契约中（实验二验收标准 3~6）。"""
    paths = client.get("/openapi.json").json()["paths"]
    expected = [
        "/api/auth/register",
        "/api/admin/borrow-cards",
        "/api/books",
        "/api/circulation/borrow",
        "/api/circulation/return",
        "/api/reservations",
        "/api/admin/book-titles",
        "/api/admin/library-items",
        "/api/admin/policies/borrow",
        "/api/admin/policies/fine",
    ]
    missing = [path for path in expected if path not in paths]
    assert missing == [], f"缺少接口: {missing}"
