import pytest
from fastapi.testclient import TestClient

from qvelt_api.main import app


@pytest.mark.parametrize("authorization", [None, "Bearer forged", "Basic abc", "Bearer "])
def test_private_routes_reject_unverified_identity(authorization: str | None) -> None:
    headers = {} if authorization is None else {"Authorization": authorization}
    with TestClient(app) as client:
        response = client.get("/auth/me", headers=headers)
    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"
    assert "password" not in response.text


@pytest.mark.parametrize("method,path", [
    ("GET", "/runs/00000000-0000-0000-0000-000000000001/events"),
    ("POST", "/runs/00000000-0000-0000-0000-000000000001/cancel"),
    ("POST", "/chats/00000000-0000-0000-0000-000000000001/messages"),
])
def test_streaming_routes_require_authentication_before_storage(method, path):
    with TestClient(app) as client:
        response = client.request(method, path, json={"text": "hello"})
    assert response.status_code == 401
