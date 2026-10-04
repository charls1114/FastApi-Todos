import httpx2
import pytest
import time

def wait_until_up(http, base_url, seconds=30):
    # 배포 직후에는 컨테이너가 아직 뜨는 중일 수 있으므로 응답이 올 때까지 기다림
    for _ in range(seconds):
        try:
            if http.get("/todos").status_code == 200:
                return
        except httpx2.TransportError:  # 연결 거부, 타임아웃 등
            pass
        time.sleep(1)
    pytest.fail(f"{base_url} 에 접속할 수 없음 (컨테이너 실행 여부, 포트, 방화벽 확인)")

@pytest.fixture(scope="session")
def client(base_url):
    with httpx2.Client(base_url=base_url, timeout=10) as c:
        wait_until_up(c, base_url)  # 컨테이너가 준비될 때까지 대기
        yield c


@pytest.fixture
def todo_factory(client):
    created_ids = []

    def create_todo(title):
        response = client.post("/todos", json={"title": title, "description": "배포 테스트 항목"})
        assert response.status_code == 201
        todo = response.json()
        created_ids.append(todo["id"])
        return todo

    yield create_todo

    for todo_id in created_ids:
        response = client.delete(f"/todos/{todo_id}")
        assert response.status_code in (204, 404)


def test_create_todo(client, todo_factory):
    todo = todo_factory("배포 생성 테스트")
    assert todo["title"] == "배포 생성 테스트"
    assert todo["id"]


def test_get_todos(client, todo_factory):
    todo = todo_factory("배포 조회 테스트")

    response = client.get("/todos")
    assert response.status_code == 200
    assert any(item["id"] == todo["id"] for item in response.json())


def test_update_todo(client, todo_factory):
    todo = todo_factory("배포 수정 전")
    updated_todo = {"title": "배포 수정 후", "description": "수정된 설명", "status": "done"}

    response = client.put(f"/todos/{todo['id']}", json=updated_todo)
    assert response.status_code == 200
    assert response.json()["title"] == "배포 수정 후"
    assert response.json()["status"] == "done"


def test_delete_todo(client, todo_factory):
    todo = todo_factory("배포 삭제 테스트")

    response = client.delete(f"/todos/{todo['id']}")
    assert response.status_code == 204

    get_response = client.get("/todos")
    assert all(item["id"] != todo["id"] for item in get_response.json())


def test_create_todo_without_title_returns_422(client):
    todo = {"description": "title 없는 항목"}  # 필수 필드 title 누락
    response = client.post("/todos", json=todo)
    assert response.status_code == 422


def test_delete_todo_not_found_returns_404(client):
    response = client.delete("/todos/999999")
    assert response.status_code == 404
