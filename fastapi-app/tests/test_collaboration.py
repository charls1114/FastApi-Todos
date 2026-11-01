import pytest

from backend import database


PERIOD = {"start_at": "2026-10-13T09:00", "end_at": "2026-10-13T18:00"}


@pytest.fixture
def alice(login):
    return login("alice", "앨리스")


@pytest.fixture
def bob(login):
    return login("bob", "밥")


@pytest.fixture
def carol(login):
    return login("carol", "캐럴")


def create(client, **fields):
    response = client.post("/todos", json={"title": "공동 작업", **PERIOD, **fields})
    assert response.status_code == 201
    return response.json()


def titles(client, **params):
    return [todo["title"] for todo in client.get("/todos", params=params).json()]


# ── 공개 범위: 작성자와 담당자만 ───────────────────────────────

def test_todo_has_owner_and_assignee(alice, bob):
    todo = create(alice, assignee_id=bob.user["id"])
    assert todo["owner"] == alice.user
    assert todo["assignee"] == bob.user
    assert todo["assignee_id"] == bob.user["id"]


def test_other_users_cannot_see_todo(alice, bob):
    todo = create(alice)
    assert titles(bob) == []
    for method, path, body in [
        ("put", f"/todos/{todo['id']}", {"title": "x", **PERIOD}),
        ("patch", f"/todos/{todo['id']}", {"status": "done"}),
        ("delete", f"/todos/{todo['id']}", None),
        ("get", f"/todos/{todo['id']}/comments", None),
        ("post", f"/todos/{todo['id']}/comments", {"body": "hi"}),
        ("get", f"/todos/{todo['id']}/activities", None),
    ]:
        kwargs = {"json": body} if body else {}
        assert bob.request(method, path, **kwargs).status_code == 404, (method, path)
    assert titles(alice) == ["공동 작업"]


def test_assignee_can_view_and_edit_but_not_delete(alice, bob):
    todo = create(alice, assignee_id=bob.user["id"])
    assert titles(bob) == ["공동 작업"]

    response = bob.patch(f"/todos/{todo['id']}", json={"status": "in_progress"})
    assert response.status_code == 200
    assert response.json()["owner"] == alice.user               # 수정해도 작성자는 그대로

    response = bob.delete(f"/todos/{todo['id']}")
    assert response.status_code == 403
    assert alice.delete(f"/todos/{todo['id']}").status_code == 204


def test_unassigned_user_loses_access(alice, bob):
    todo = create(alice, assignee_id=bob.user["id"])
    assert alice.patch(f"/todos/{todo['id']}", json={"assignee_id": None}).json()["assignee"] is None
    assert titles(bob) == []


def test_scope_filters(alice, bob, carol):
    create(alice, title="앨리스 혼자")
    create(alice, title="밥에게 맡김", assignee_id=bob.user["id"])
    create(bob, title="밥이 앨리스에게", assignee_id=alice.user["id"])
    create(carol, title="캐럴 혼자")

    assert titles(alice) == ["앨리스 혼자", "밥에게 맡김", "밥이 앨리스에게"]
    assert titles(alice, scope="assigned") == ["밥이 앨리스에게"]          # "내 할 일"
    assert titles(alice, scope="owned") == ["앨리스 혼자", "밥에게 맡김"]
    assert alice.get("/todos", params={"scope": "everyone"}).status_code == 422


@pytest.mark.parametrize("method", ["post", "put", "patch"])
def test_unknown_assignee_returns_422(alice, method):
    if method == "post":
        response = alice.post("/todos", json={"title": "x", **PERIOD, "assignee_id": 999})
    else:
        todo = create(alice)
        body = {"assignee_id": 999} if method == "patch" else {"title": "x", **PERIOD, "assignee_id": 999}
        response = alice.request(method, f"/todos/{todo['id']}", json=body)
    assert response.status_code == 422
    assert response.json()["detail"] == "존재하지 않는 담당자입니다."


def test_owner_id_cannot_be_set_by_client(alice, bob):
    todo = alice.post("/todos", json={"title": "x", **PERIOD, "owner_id": bob.user["id"]}).json()
    assert todo["owner"] == alice.user
    assert alice.patch(f"/todos/{todo['id']}", json={"owner_id": bob.user["id"]}).status_code == 422


# ── 댓글 ───────────────────────────────────────────────────

def test_owner_and_assignee_can_comment(alice, bob):
    todo = create(alice, assignee_id=bob.user["id"])
    first = alice.post(f"/todos/{todo['id']}/comments", json={"body": "  시작합니다  "})
    assert first.status_code == 201
    assert first.json()["body"] == "시작합니다"
    assert first.json()["author"] == alice.user
    assert first.json()["created_at"].endswith("+00:00")        # UTC 로 내려준다
    bob.post(f"/todos/{todo['id']}/comments", json={"body": "확인했어요"})

    comments = bob.get(f"/todos/{todo['id']}/comments").json()
    assert [(c["author"]["username"], c["body"]) for c in comments] == [("alice", "시작합니다"), ("bob", "확인했어요")]


@pytest.mark.parametrize("body", ["", "   ", "x" * 1001])
def test_invalid_comment_returns_422(alice, body):
    todo = create(alice)
    assert alice.post(f"/todos/{todo['id']}/comments", json={"body": body}).status_code == 422


def test_only_author_can_delete_comment(alice, bob):
    todo = create(alice, assignee_id=bob.user["id"])
    comment = bob.post(f"/todos/{todo['id']}/comments", json={"body": "밥의 댓글"}).json()
    path = f"/todos/{todo['id']}/comments/{comment['id']}"

    assert alice.delete(path).status_code == 403
    assert bob.delete(path).status_code == 204
    assert bob.delete(path).status_code == 404
    assert alice.get(f"/todos/{todo['id']}/comments").json() == []


def test_comment_must_belong_to_todo(alice):
    first, second = create(alice), create(alice)
    comment = alice.post(f"/todos/{first['id']}/comments", json={"body": "첫 할 일"}).json()
    assert alice.delete(f"/todos/{second['id']}/comments/{comment['id']}").status_code == 404


# ── 활동 기록 ────────────────────────────────────────────────

def changes(client, todo_id):
    return [
        (a["actor"]["username"], a["action"], a["field"], a["old_value"], a["new_value"])
        for a in client.get(f"/todos/{todo_id}/activities").json()
    ]


def test_activity_records_creation_and_each_changed_field(alice, bob):
    todo = create(alice, assignee_id=bob.user["id"])
    bob.patch(f"/todos/{todo['id']}", json={"status": "done", "priority": "medium"})   # priority 는 그대로
    alice.put(f"/todos/{todo['id']}", json={
        "title": "제목 변경", **PERIOD, "end_at": "2026-10-14", "status": "done", "assignee_id": None,
    })

    assert changes(alice, todo["id"]) == [
        ("alice", "created", None, None, None),
        ("bob", "updated", "status", "planned", "done"),
        ("alice", "updated", "title", "공동 작업", "제목 변경"),
        ("alice", "updated", "end_at", "2026-10-13T18:00", "2026-10-14T23:59:59"),
        ("alice", "updated", "assignee_id", str(bob.user["id"]), None),
    ]


def test_unchanged_update_records_nothing(alice):
    todo = create(alice)
    alice.patch(f"/todos/{todo['id']}", json={"status": "planned"})
    alice.put(f"/todos/{todo['id']}", json={"title": "공동 작업", **PERIOD})
    assert len(changes(alice, todo["id"])) == 1


def test_failed_update_records_nothing(alice):
    todo = create(alice)
    alice.patch(f"/todos/{todo['id']}", json={"title": "새 제목", "assignee_id": 999})
    assert len(changes(alice, todo["id"])) == 1
    assert alice.get("/todos").json()[0]["title"] == "공동 작업"


def test_deleting_todo_removes_comments_and_activities(alice):
    todo = create(alice)
    alice.post(f"/todos/{todo['id']}/comments", json={"body": "삭제될 댓글"})
    alice.delete(f"/todos/{todo['id']}")
    with database.SessionLocal() as db:
        assert db.query(database.Comment).count() == 0
        assert db.query(database.Activity).count() == 0
