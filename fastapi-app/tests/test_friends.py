import pytest


@pytest.fixture
def alice(login):
    return login("alice", "앨리스")


@pytest.fixture
def bob(login):
    return login("bob", "밥")


@pytest.fixture
def carol(login):
    return login("carol", "캐럴")


def send(client, username):
    return client.post("/friends/requests", json={"username": username})


def usernames(users):
    return [user["username"] for user in users]


def requests_of(client):
    body = client.get("/friends/requests").json()
    return usernames(r["user"] for r in body["received"]), usernames(r["user"] for r in body["sent"])


def test_request_then_accept_makes_both_friends(alice, bob):
    response = send(alice, " BOB ")                  # 아이디는 대소문자·공백 무시
    assert response.status_code == 201
    request = response.json()
    assert (request["user"], request["status"]) == (bob.user, "pending")

    assert requests_of(alice) == ([], ["bob"])
    assert requests_of(bob) == (["alice"], [])
    assert alice.get("/friends").json() == []        # 수락 전에는 친구가 아니다

    accepted = bob.post(f"/friends/requests/{request['id']}/accept")
    assert accepted.status_code == 200
    assert (accepted.json()["user"], accepted.json()["status"]) == (alice.user, "accepted")
    assert alice.get("/friends").json() == [bob.user]
    assert bob.get("/friends").json() == [alice.user]
    assert requests_of(alice) == ([], [])


def test_requester_cannot_accept_own_request(alice, bob):
    request = send(alice, "bob").json()
    response = alice.post(f"/friends/requests/{request['id']}/accept")
    assert response.status_code == 403
    assert alice.get("/friends").json() == []


def test_mutual_requests_become_friends(alice, bob):
    send(alice, "bob")
    response = send(bob, "alice")                    # 상대가 이미 보낸 요청이 있으면 바로 수락
    assert response.status_code == 201
    assert response.json()["status"] == "accepted"
    assert alice.get("/friends").json() == [bob.user]


@pytest.mark.parametrize("username, status, detail", [
    ("nobody", 404, "존재하지 않는 아이디입니다."),
    ("alice", 422, "자기 자신에게는 친구 요청을 보낼 수 없습니다."),
    ("ab", 422, None),                               # 아이디 형식 오류
])
def test_invalid_request(alice, username, status, detail):
    response = send(alice, username)
    assert response.status_code == status
    if detail:
        assert response.json()["detail"] == detail


def test_duplicate_request_and_existing_friend_return_409(alice, bob, befriend, carol):
    send(alice, "carol")
    assert send(alice, "carol").json()["detail"] == "이미 친구 요청을 보냈습니다."
    befriend(alice, bob)
    for client, username in [(alice, "bob"), (bob, "alice")]:
        response = send(client, username)
        assert response.status_code == 409
        assert response.json()["detail"] == "이미 친구입니다."


def test_reject_and_cancel_request(alice, bob, carol):
    to_bob = send(alice, "bob").json()
    to_carol = send(alice, "carol").json()

    assert bob.delete(f"/friends/requests/{to_bob['id']}").status_code == 204       # 받은 사람이 거절
    assert alice.delete(f"/friends/requests/{to_carol['id']}").status_code == 204   # 보낸 사람이 취소
    assert requests_of(alice) == ([], [])
    assert requests_of(carol) == ([], [])
    assert send(alice, "bob").status_code == 201                                     # 다시 보낼 수 있다


def test_other_users_cannot_touch_request(alice, bob, carol):
    request = send(alice, "bob").json()
    assert carol.post(f"/friends/requests/{request['id']}/accept").status_code == 404
    assert carol.delete(f"/friends/requests/{request['id']}").status_code == 404
    assert requests_of(bob) == (["alice"], [])


def test_accepted_friendship_is_not_a_pending_request(alice, bob, befriend):
    befriend(alice, bob)
    assert bob.delete("/friends/requests/1").status_code == 404     # 친구 끊기는 /friends/{user_id} 로 한다


def test_remove_friend_from_either_side(alice, bob, carol, befriend):
    befriend(alice, bob)
    befriend(carol, alice)
    assert usernames(alice.get("/friends").json()) == ["bob", "carol"]   # 표시 이름 순 (밥 < 캐럴)

    assert bob.delete(f"/friends/{alice.user['id']}").status_code == 204
    assert usernames(alice.get("/friends").json()) == ["carol"]
    assert bob.delete(f"/friends/{alice.user['id']}").status_code == 404
    assert send(bob, "alice").status_code == 201                         # 다시 요청할 수 있다


def test_friends_require_login(api_client):
    for method, path in [("get", "/friends"), ("get", "/friends/requests"), ("post", "/friends/requests")]:
        assert api_client.request(method, path).status_code == 401
