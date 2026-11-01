from datetime import datetime

import pytest
from alembic import command
from sqlalchemy import inspect, text
from sqlalchemy.exc import IntegrityError

from backend import database


def migrate(engine, revision, action=command.upgrade):
    config = database.alembic_config()
    with engine.begin() as connection:
        config.attributes["connection"] = connection
        action(config, revision)


def insert_string_period(engine, rows):
    with engine.begin() as connection:
        for todo_id, start_at, end_at in rows:
            connection.execute(
                text(
                    "INSERT INTO todos (id, title, description, start_at, end_at, location, status, priority, assignee)"
                    " VALUES (:id, 'Test', '', :start_at, :end_at, '', 'planned', 'medium', '')"
                ),
                {"id": todo_id, "start_at": start_at, "end_at": end_at},
            )


def stored_period(engine):
    with database.SessionLocal() as db:
        return [(todo.id, todo.start_at, todo.end_at) for todo in db.query(database.Todo).order_by(database.Todo.id)]


def test_upgrade_converts_string_period_to_datetime(empty_db):
    migrate(empty_db, "0001")
    insert_string_period(empty_db, [
        (1, "2026-10-13T09:00", "2026-10-13T18:30:15"),
        (2, "2026-10-13", "2026-10-14"),              # 날짜만 있는 값
    ])

    migrate(empty_db, "head")

    assert stored_period(empty_db) == [
        (1, datetime(2026, 10, 13, 9, 0), datetime(2026, 10, 13, 18, 30, 15)),
        (2, datetime(2026, 10, 13, 0, 0), datetime(2026, 10, 14, 23, 59, 59)),
    ]
    columns = {column["name"]: column for column in inspect(empty_db).get_columns("todos")}
    assert not columns["start_at"]["nullable"] and not columns["end_at"]["nullable"]


def test_upgrade_keeps_check_constraints(empty_db):
    migrate(empty_db, "head")
    with pytest.raises(IntegrityError):
        with empty_db.begin() as connection:
            connection.execute(text(
                "INSERT INTO todos (title, description, start_at, end_at, location, status, priority, assignee)"
                " VALUES ('Test', '', '2026-10-13 09:00:00', '2026-10-13 18:00:00', '', 'archived', 'medium', '')"
            ))


def test_upgrade_with_invalid_stored_date_fails_without_changes(empty_db):
    migrate(empty_db, "0001")
    insert_string_period(empty_db, [(1, "2026-10-13T09:00", "2026-10-13T18:00"), (7, "2026-02-30", "2026-03-01")])

    with pytest.raises(RuntimeError, match=r"id=\[7\]"):
        migrate(empty_db, "head")

    with empty_db.connect() as connection:
        assert connection.execute(text("SELECT version_num FROM alembic_version")).scalar() == "0001"
        assert connection.execute(text("SELECT start_at FROM todos WHERE id = 7")).scalar() == "2026-02-30"


def test_downgrade_restores_string_period(empty_db):
    migrate(empty_db, "0001")
    insert_string_period(empty_db, [(1, "2026-10-13T09:00", "2026-10-14")])
    migrate(empty_db, "head")

    migrate(empty_db, "0001", command.downgrade)

    with empty_db.connect() as connection:
        row = connection.execute(text("SELECT start_at, end_at FROM todos")).one()
    assert tuple(row) == ("2026-10-13T09:00", "2026-10-14T23:59:59")


def test_init_db_upgrades_database_created_before_alembic(empty_db):
    # Alembic 도입 전에는 create_all 로 만들어 alembic_version 테이블이 없다
    migrate(empty_db, "0001")
    with empty_db.begin() as connection:
        connection.execute(text("DROP TABLE alembic_version"))
    insert_string_period(empty_db, [(1, "2026-10-13T09:00", "2026-10-13T18:00")])

    database.init_db()

    assert stored_period(empty_db) == [(1, datetime(2026, 10, 13, 9), datetime(2026, 10, 13, 18))]


def test_init_db_is_idempotent(empty_db):
    database.init_db()
    database.init_db()
    with empty_db.connect() as connection:
        assert connection.execute(text("SELECT version_num FROM alembic_version")).scalar() == "0002"
