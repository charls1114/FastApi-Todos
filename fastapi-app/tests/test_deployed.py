import httpx
import pytest

@pytest.fixture
def client(base_url):
    with httpx.Client(base_url=base_url, timeout=10) as c:
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
