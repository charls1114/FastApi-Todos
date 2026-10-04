import httpx2
import pytest
import time

def wait_until_up(http, seconds=30):
    # 배포 직후에는 컨테이너가 아직 뜨는 중일 수 있으므로 응답이 올 때까지 기다림
    for _ in range(seconds):
        try:
            if http.get("/todos").status_code == 200:
                return
        except httpx2.TransportError:  # 연결 거부, 타임아웃 등
            pass
        time.sleep(1)
    pytest.fail(f"{BASE_URL} 에 접속할 수 없음 (컨테이너 실행 여부, 포트, 방화벽 확인)")

@pytest.fixture(scope="session")
def client(BASE_URL):
    with httpx2.Client(base_url=BASE_URL, timeout=10) as c:
        wait_until_up(c)  # 컨테이너가 준비될 때까지 대기
        yield c


def test_create_get_update_delete_flow(client):
    # 1) 추가 (201)
    todo = {"title": "배포 테스트", "description": "통합 테스트용 항목"}
    create_res = client.post("/todos", json=todo)
    assert create_res.status_code == 201
    created = create_res.json()
    assert created["title"] == "배포 테스트"
    todo_id = created["id"]

    # 2) 조회 (200)
    get_res = client.get("/todos")
    assert get_res.status_code == 200
    assert any(t["id"] == todo_id for t in get_res.json())

    # 3) 수정 (200)
    updated_todo = {"title": "수정됨", "description": "수정된 설명", "status": "done"}
    update_res = client.put(f"/todos/{todo_id}", json=updated_todo)
    assert update_res.status_code == 200
    assert update_res.json()["title"] == "수정됨"

    # 4) 삭제 (204)
    delete_res = client.delete(f"/todos/{todo_id}")
    assert delete_res.status_code == 204


def test_create_todo_without_title_returns_422(client):
    todo = {"description": "title 없는 항목"}  # 필수 필드 title 누락
    response = client.post("/todos", json=todo)
    assert response.status_code == 422


def test_delete_todo_not_found_returns_404(client):
    response = client.delete("/todos/999999")
    assert response.status_code == 404
