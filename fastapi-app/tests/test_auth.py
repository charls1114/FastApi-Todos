from datetime import UTC, datetime, timedelta

import jwt
import pytest
from sqlalchemy import select

from backend import auth, database


USER = {"username": "alice", "display_name": "앨리스", "password": "password123"}


def register(client, **fields):
    return client.post("/auth/register", json={**USER, **fields})


def login(client, username="alice", password="password123"):
    return client.post("/auth/login", data={"username": username, "password": password})


def test_register_returns_user_without_password(api_client):
    response = register(api_client, username="Alice_01")
    assert response.status_code == 201
    assert response.json() == {"id": 1, "username": "alice_01", "display_name": "앨리스"}   # 아이디는 소문자로 저장


def test_password_is_stored_hashed(api_client):
    register(api_client)
    with database.SessionLocal() as db:
        stored = db.scalar(select(database.User.password_hash))
    assert stored != USER["password"] and stored.startswith("$argon2")


@pytest.mark.parametrize("username", ["alice", "ALICE"])
def test_register_duplicate_username_returns_409(api_client, username):
    register(api_client)
    response = register(api_client, username=username)
    assert response.status_code == 409


@pytest.mark.parametrize("fields", [
    {"username": "ab"},                  # 3자 미만
    {"username": "한글아이디"},
    {"username": "has space"},
    {"password": "short"},               # 8자 미만
    {"display_name": "   "},
])
def test_register_invalid_returns_422(api_client, fields):
    assert register(api_client, **fields).status_code == 422


def test_login_returns_token_and_user(api_client):
    register(api_client)
    response = login(api_client, username=" Alice ")
    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["user"]["username"] == "alice"
    me = api_client.get("/users/me", headers={"Authorization": f"Bearer {body['access_token']}"})
    assert me.json() == body["user"]


@pytest.mark.parametrize("username, password", [("alice", "wrong-password"), ("nobody", "password123")])
def test_login_failure_returns_401(api_client, username, password):
    register(api_client)
    response = login(api_client, username, password)
    assert response.status_code == 401
    assert response.json()["detail"] == "아이디 또는 비밀번호가 올바르지 않습니다."


def token_for(user_id, expires_in=timedelta(minutes=5), key=None):
    payload = {"sub": str(user_id), "exp": datetime.now(UTC) + expires_in}
    return jwt.encode(payload, key or auth.SECRET_KEY, algorithm=auth.ALGORITHM)


@pytest.mark.parametrize("headers", [
    {},
    {"Authorization": "Bearer not-a-jwt"},
    {"Authorization": f"Bearer {token_for(1, key='x' * 32 + 'other-secret')}"},   # 다른 키로 서명
])
@pytest.mark.parametrize("path", ["/users/me", "/friends", "/todos"])
def test_protected_routes_require_valid_token(api_client, headers, path):
    register(api_client)
    response = api_client.get(path, headers=headers)
    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"


def test_expired_token_returns_401(api_client):
    register(api_client)
    response = api_client.get("/users/me", headers={"Authorization": f"Bearer {token_for(1, timedelta(seconds=-1))}"})
    assert response.status_code == 401


def test_token_of_deleted_user_returns_401(api_client):
    register(api_client)
    with database.SessionLocal.begin() as db:
        db.delete(db.get(database.User, 1))
    response = api_client.get("/users/me", headers={"Authorization": f"Bearer {token_for(1)}"})
    assert response.status_code == 401


def test_health_does_not_require_login(api_client):
    assert api_client.get("/health").status_code == 200


def test_full_user_list_is_not_exposed(login):
    alice = login("alice")
    assert alice.get("/users").status_code in (404, 405)


# ── 회원 탈퇴 ────────────────────────────────────────────────

def delete_account(client, password="password123"):
    return client.request("DELETE", "/users/me", json={"password": password})


def test_delete_account_requires_password(login):
    alice = login("alice")
    response = delete_account(alice, "wrong-password")
    assert response.status_code == 403
    assert response.json()["detail"] == "비밀번호가 올바르지 않습니다."
    assert alice.get("/users/me").status_code == 200


def test_deleted_account_cannot_login_and_username_is_reusable(api_client, login):
    alice = login("alice")
    assert delete_account(alice).status_code == 204
    assert alice.get("/users/me").status_code == 401             # 남아 있는 토큰도 더는 쓸 수 없다
    assert api_client.post("/auth/login", data={"username": "alice", "password": "password123"}).status_code == 401
    assert register(api_client).status_code == 201


def test_delete_account_cleans_up_related_data(login, befriend):
    alice, bob = login("alice", "앨리스"), login("bob", "밥")
    befriend(alice, bob)
    period = {"start_at": "2026-10-13T09:00", "end_at": "2026-10-13T18:00"}
    alices = alice.post("/todos", json={"title": "앨리스의 일", **period, "assignee_id": bob.user["id"]}).json()
    bobs = bob.post("/todos", json={"title": "밥의 일", **period, "assignee_id": alice.user["id"]}).json()
    alice.post(f"/todos/{bobs['id']}/comments", json={"body": "앨리스의 댓글"})
    alice.patch(f"/todos/{bobs['id']}", json={"status": "done"})

    assert delete_account(alice).status_code == 204

    assert [todo["title"] for todo in bob.get("/todos").json()] == ["밥의 일"]   # 앨리스가 만든 할 일은 삭제
    assert bob.get(f"/todos/{alices['id']}/comments").status_code == 404
    assert bob.get("/todos").json()[0]["assignee"] is None                      # 담당자는 비워진다
    comment = bob.get(f"/todos/{bobs['id']}/comments").json()[0]
    assert (comment["author"], comment["body"]) == (None, "앨리스의 댓글")       # 댓글은 남는다
    assert [a["actor"] for a in bob.get(f"/todos/{bobs['id']}/activities").json()][-1] is None
    assert bob.get("/friends").json() == []
