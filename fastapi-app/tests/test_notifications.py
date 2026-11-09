import asyncio
import threading
from datetime import UTC, datetime, timedelta

import pytest

from backend import auth, database, notifications as notifications_module
from backend.notifications import MAX_NOTIFICATIONS

PERIOD = {"start_at": "2026-10-13T09:00", "end_at": "2026-10-13T18:00"}


@pytest.fixture
def alice(login):
    return login("alice", "앨리스")


@pytest.fixture
def bob(login, alice, befriend):
    bob = login("bob", "밥")
    befriend(alice, bob)
    return bob


@pytest.fixture
def carol(login, alice, befriend):
    carol = login("carol", "캐럴")
    befriend(alice, carol)
    return carol


def create(client, **fields):
    response = client.post("/todos", json={"title": "공동 작업", **PERIOD, **fields})
    assert response.status_code == 201, response.text
    return response.json()


def notifications(client):
    response = client.get("/notifications")
    assert response.status_code == 200
    return response.json()


# ── 할당 → 수락 대기 + 알림 ──────────────────────────────────

def test_assigning_friend_creates_pending_todo_and_notification(alice, bob):
    todo = create(alice, assignee_id=bob.user["id"])
    assert todo["assignment_status"] == "pending"

    [notification] = notifications(bob)
    assert notification["type"] == "todo_assigned"
    assert notification["message"] == "앨리스님이 일정을 배정했습니다."
    assert notification["status"] == "unread"
    assert notification["todo_id"] == todo["id"] and notification["todo_title"] == "공동 작업"
    assert notification["created_at"].endswith("+00:00")
    assert notifications(alice) == []


@pytest.mark.parametrize("assignee", ["self", "none"])
def test_self_or_no_assignee_is_accepted_without_notification(alice, assignee):
    assignee_id = alice.user["id"] if assignee == "self" else None
    assert create(alice, assignee_id=assignee_id)["assignment_status"] == "accepted"
    assert notifications(alice) == []


@pytest.mark.parametrize("method", ["patch", "put"])
def test_changing_assignee_creates_pending_and_notifies_new_assignee(alice, bob, carol, method):
    todo = create(alice, assignee_id=bob.user["id"])
    bob.post(f"/todos/{todo['id']}/accept")
    body = {"assignee_id": carol.user["id"]}
    if method == "put":
        body = {"title": "공동 작업", **PERIOD, **body}

    updated = alice.request(method, f"/todos/{todo['id']}", json=body).json()

    assert updated["assignment_status"] == "pending"
    assert [n["type"] for n in notifications(carol)] == ["todo_assigned"]
    assert alice.patch(f"/todos/{todo['id']}", json={"assignee_id": None}).json()["assignment_status"] == "accepted"


def test_editing_other_fields_does_not_notify_again(alice, bob):
    todo = create(alice, assignee_id=bob.user["id"])
    alice.patch(f"/todos/{todo['id']}", json={"title": "새 제목"})
    assert len(notifications(bob)) == 1


# ── 수락·거부 ────────────────────────────────────────────────

def test_accept_marks_accepted_and_notifies_owner(alice, bob):
    todo = create(alice, assignee_id=bob.user["id"])

    response = bob.post(f"/todos/{todo['id']}/accept")

    assert response.status_code == 200
    assert response.json()["assignment_status"] == "accepted"
    [notification] = notifications(alice)
    assert notification["type"] == "todo_accepted"
    assert notification["message"] == "밥님이 일정 배정을 수락했습니다."
    assert bob.post(f"/todos/{todo['id']}/accept").status_code == 409


def test_reject_deletes_todo_and_notifies_owner_with_reason(alice, bob):
    todo = create(alice, assignee_id=bob.user["id"])

    response = bob.post(f"/todos/{todo['id']}/reject", json={"reason": "  같은 시간에 회의가 있어요  "})

    assert response.status_code == 204
    assert alice.get("/todos").json() == []
    [notification] = notifications(alice)
    assert notification["type"] == "todo_rejected"
    assert notification["message"] == "밥님이 일정 배정을 거부했습니다. 거부 사유를 확인해주세요."
    assert notification["reason"] == "같은 시간에 회의가 있어요"
    assert notification["todo_title"] == "공동 작업" and notification["todo_id"] is None
    assert notifications(bob)[0]["todo_id"] is None             # 받은 할당 알림도 삭제된 할 일과 연결이 끊긴다


@pytest.mark.parametrize("reason", ["", "   ", "x" * 501])
def test_reject_requires_reason(alice, bob, reason):
    todo = create(alice, assignee_id=bob.user["id"])
    assert bob.post(f"/todos/{todo['id']}/reject", json={"reason": reason}).status_code == 422


@pytest.mark.parametrize("action", ["accept", "reject"])
def test_only_assignee_can_respond(alice, bob, carol, action):
    todo = create(alice, assignee_id=bob.user["id"])
    body = {"json": {"reason": "안 돼요"}} if action == "reject" else {}
    assert alice.post(f"/todos/{todo['id']}/{action}", **body).status_code == 403   # 작성자
    assert carol.post(f"/todos/{todo['id']}/{action}", **body).status_code == 404   # 볼 수 없는 사용자
    own = create(alice, assignee_id=alice.user["id"])
    assert alice.post(f"/todos/{own['id']}/{action}", **body).status_code == 403    # 본인 할당


def test_cannot_reject_after_accepting(alice, bob):
    todo = create(alice, assignee_id=bob.user["id"])
    bob.post(f"/todos/{todo['id']}/accept")
    assert bob.post(f"/todos/{todo['id']}/reject", json={"reason": "변심"}).status_code == 409


# ── 알림 확인·개수 제한 ──────────────────────────────────────

def test_read_single_notification(alice, bob):
    create(alice, assignee_id=bob.user["id"])
    create(alice, assignee_id=bob.user["id"])
    newest, oldest = notifications(bob)

    response = bob.post(f"/notifications/{oldest['id']}/read")

    assert response.status_code == 200 and response.json()["status"] == "read"
    assert [n["status"] for n in notifications(bob)] == ["unread", "read"]
    assert alice.post(f"/notifications/{newest['id']}/read").status_code == 404   # 남의 알림
    assert bob.post("/notifications/999/read").status_code == 404


def test_read_all_only_affects_own_notifications(alice, bob):
    todo = create(alice, assignee_id=bob.user["id"])
    bob.post(f"/todos/{todo['id']}/accept")

    assert bob.post("/notifications/read-all").status_code == 204

    assert [n["status"] for n in notifications(bob)] == ["read"]
    assert [n["status"] for n in notifications(alice)] == ["unread"]


def test_keeps_only_latest_notifications_per_user(alice, bob):
    for index in range(MAX_NOTIFICATIONS + 2):
        create(alice, title=f"할 일 {index}", assignee_id=bob.user["id"])

    titles = [n["todo_title"] for n in notifications(bob)]

    assert len(titles) == MAX_NOTIFICATIONS
    assert titles[0] == f"할 일 {MAX_NOTIFICATIONS + 1}" and titles[-1] == "할 일 2"   # 최신순, 오래된 2개 삭제


def test_notifications_require_login(api_client):
    assert api_client.get("/notifications").status_code == 401


# ── 삭제·탈퇴 정리 ───────────────────────────────────────────

def test_deleting_todo_keeps_notification_without_link(alice, bob):
    todo = create(alice, assignee_id=bob.user["id"])
    assert alice.delete(f"/todos/{todo['id']}").status_code == 204
    [notification] = notifications(bob)
    assert notification["todo_id"] is None and notification["todo_title"] == "공동 작업"


def test_deleting_account_cleans_up_notifications(alice, bob):
    todo = create(alice, assignee_id=bob.user["id"])
    bob.post(f"/todos/{todo['id']}/accept")

    assert alice.request("DELETE", "/users/me", json={"password": "password123"}).status_code == 204

    assert notifications(bob)[0]["todo_id"] is None


def test_deleted_assignee_leaves_todo_accepted_and_unassigned(alice, bob):
    todo = create(alice, assignee_id=bob.user["id"])
    assert bob.request("DELETE", "/users/me", json={"password": "password123"}).status_code == 204
    [saved] = alice.get("/todos").json()
    assert saved["id"] == todo["id"] and saved["assignee"] is None and saved["assignment_status"] == "accepted"


# ── 실시간 알림 (SSE) ────────────────────────────────────────

def events_of(body):
    return [line.removeprefix("event: ") for line in body.splitlines() if line.startswith("event: ")]


@pytest.mark.parametrize("headers", [{}, {"Authorization": "Bearer invalid"}])
def test_stream_requires_valid_token(api_client, headers):
    assert api_client.get("/notifications/stream", headers=headers).status_code == 401


def test_stream_pushes_new_notification_and_closes_at_token_expiry(login, befriend, monkeypatch):
    monkeypatch.setattr(auth, "TOKEN_MINUTES", 2 / 60)   # 2초 뒤 만료되는 토큰 → 스트림이 스스로 끝난다
    monkeypatch.setattr(notifications_module, "KEEPALIVE_SECONDS", 0.5)
    alice, bob = login("alice", "앨리스"), login("bob", "밥")
    befriend(alice, bob)
    # 스트림이 열린 동안 다른 스레드에서 앨리스가 밥에게 할당한다
    assign = threading.Timer(0.5, lambda: create(alice, assignee_id=bob.user["id"]))
    assign.start()

    response = bob.get("/notifications/stream")
    assign.join()

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert events_of(response.text) == ["ready", "notification"]
    assert 'data: {"type": "todo_assigned"}' in response.text
    assert ": keep-alive" in response.text


def subscriber_queue(user_id):
    """이벤트 루프 없이 테스트하기 위해 별도 루프에서 구독한다."""
    loop = asyncio.new_event_loop()
    entry = loop.run_until_complete(_subscribe(user_id))
    return loop, entry


async def _subscribe(user_id):
    return notifications_module.hub.subscribe(user_id)


def drain(loop, entry):
    loop.run_until_complete(asyncio.sleep(0))      # call_soon_threadsafe 로 예약된 put 을 실행
    queue = entry[1]
    return [queue.get_nowait() for _ in range(queue.qsize())]


def test_push_goes_only_to_recipient_after_commit(alice, bob):
    hub = notifications_module.hub
    bob_loop, bob_entry = subscriber_queue(bob.user["id"])
    alice_loop, alice_entry = subscriber_queue(alice.user["id"])
    try:
        todo = create(alice, assignee_id=bob.user["id"])
        assert drain(bob_loop, bob_entry) == [{"type": "todo_assigned"}]
        assert drain(alice_loop, alice_entry) == []

        bob.post(f"/todos/{todo['id']}/accept")
        assert drain(alice_loop, alice_entry) == [{"type": "todo_accepted"}]
    finally:
        hub.unsubscribe(bob.user["id"], bob_entry)
        hub.unsubscribe(alice.user["id"], alice_entry)
        bob_loop.close()
        alice_loop.close()


def test_rolled_back_notification_is_not_pushed(alice, bob):
    loop, entry = subscriber_queue(bob.user["id"])
    try:
        with database.SessionLocal() as db:
            actor = db.get(database.User, alice.user["id"])
            todo = database.Todo(title="x", start_at=datetime(2026, 1, 1), end_at=datetime(2026, 1, 2), owner_id=actor.id)
            db.add(todo)
            db.flush()
            notifications_module.notify(db, bob.user["id"], "todo_assigned", actor, todo)
            db.rollback()
            db.commit()                            # 롤백된 알림이 다음 커밋에 섞여 나가지 않아야 한다
        assert drain(loop, entry) == []
        assert notifications(bob) == []
    finally:
        notifications_module.hub.unsubscribe(bob.user["id"], entry)
        loop.close()


def test_unsubscribed_connection_is_removed():
    loop, entry = subscriber_queue(42)
    notifications_module.hub.unsubscribe(42, entry)
    notifications_module.hub.publish(42, {"type": "todo_assigned"})
    assert drain(loop, entry) == []
    assert 42 not in notifications_module.hub._subscribers
    loop.close()


def test_event_stream_ends_when_token_already_expired():
    async def collect():
        return [chunk async for chunk in notifications_module.event_stream(7, datetime.now(UTC) - timedelta(seconds=1))]

    chunks = asyncio.run(collect())
    assert len(chunks) == 1 and "event: ready" in chunks[0]
    assert 7 not in notifications_module.hub._subscribers
