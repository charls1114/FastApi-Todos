from concurrent.futures import ThreadPoolExecutor

import pytest
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from backend.database import Todo, get_db
from backend.main import app


PERIOD = {"start_at": "2026-10-25T09:00", "end_at": "2026-10-25T18:00"}


@pytest.mark.parametrize("field", ["start_at", "end_at"])
def test_database_rejects_null_period(todo_db, field):
    with Session(todo_db) as db:
        db.add(Todo(title="Test", **{**PERIOD, field: None}))
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()
        assert db.query(Todo).count() == 0


def test_concurrent_creates_have_unique_ids_and_keep_all_items(api_client):
    def create(index):
        return api_client.post("/todos", json={"title": f"Todo {index}", **PERIOD})

    with ThreadPoolExecutor(max_workers=5) as pool:
        responses = list(pool.map(create, range(15)))
    assert all(response.status_code == 201 for response in responses)
    assert len({response.json()["id"] for response in responses}) == 15
    assert len(api_client.get("/todos").json()) == 15


def test_update_and_delete_preserve_other_items(api_client):
    first = api_client.post("/todos", json={"title": "First", **PERIOD}).json()
    second = api_client.post("/todos", json={"title": "Second", **PERIOD}).json()
    updated = api_client.put(f"/todos/{first['id']}", json={"title": "Updated", **PERIOD})
    assert updated.status_code == 200
    assert api_client.delete(f"/todos/{first['id']}").status_code == 204
    assert api_client.get("/todos").json() == [second]


def test_health_checks_database(api_client):
    assert api_client.get("/health").json() == {"status": "ok"}

    class UnavailableDatabase:
        def execute(self, statement):
            raise SQLAlchemyError("Database is offline")

    app.dependency_overrides[get_db] = lambda: UnavailableDatabase()
    try:
        response = api_client.get("/health")
        assert response.status_code == 503
        assert response.json() == {"detail": "Database unavailable"}
    finally:
        app.dependency_overrides.pop(get_db, None)
