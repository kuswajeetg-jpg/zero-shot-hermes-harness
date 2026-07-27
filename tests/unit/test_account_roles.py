"""Account and RBAC behavior tests."""
from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from src.api import create_app
from src.db.models import User
from src.db.session import create_db_session


def _client() -> TestClient:
    return TestClient(create_app())


def test_register_assigns_default_officer_role():
    client = _client()
    res = client.post("/auth/register", json={"email": "officer1@example.com", "password": "secret123"})
    assert res.status_code == 200
    body = res.json()["data"]
    assert body["email"] == "officer1@example.com"
    assert body["role"] == "officer"
    with create_db_session() as session:
        user = session.query(User).filter(User.email == "officer1@example.com").first()
        assert user is not None
        assert user.role == "officer"


def test_login_returns_role_in_payload():
    client = _client()
    client.post("/auth/register", json={"email": "analyst1@example.com", "password": "secret123"})
    res = client.post("/auth/login", json={"email": "analyst1@example.com", "password": "secret123"})
    assert res.status_code == 200
    body = res.json()["data"]
    assert "role" in body
    assert body["role"] in {"officer", "analyst", "administrator"}


def test_role_upgrade_and_login_reflects_new_role():
    client = _client()
    client.post("/auth/register", json={"email": "admin_upgrade@example.com", "password": "secret123"})
    with create_db_session() as session:
        user = session.query(User).filter(User.email == "admin_upgrade@example.com").first()
        user.role = "administrator"
        session.commit()
    res = client.post("/auth/login", json={"email": "admin_upgrade@example.com", "password": "secret123"})
    assert res.status_code == 200
    body = res.json()["data"]
    assert body["role"] == "administrator"


def test_missing_bearer_token_returns_401():
    client = _client()
    res = client.get("/api/uploads")
    assert res.status_code == 401


def test_invalid_token_returns_401():
    client = _client()
    res = client.get("/api/uploads", headers={"Authorization": "Bearer invalid"})
    assert res.status_code == 401
