from datetime import datetime

import pytest
from alembic import command
import sqlalchemy as sa
from sqlalchemy import inspect, text
from sqlalchemy.exc import IntegrityError

from backend import database

HEAD = "0004"


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
    # 0002 시점의 todos (ORM 모델은 최신 스키마라 쓰지 않는다)
    todos = sa.table("todos", sa.column("id"), sa.column("start_at", sa.DateTime), sa.column("end_at", sa.DateTime))
    with engine.connect() as connection:
        return [tuple(row) for row in connection.execute(sa.select(todos).order_by(todos.c.id))]


def version(engine):
    with engine.connect() as connection:
        return connection.execute(text("SELECT version_num FROM alembic_version")).scalar()


def test_upgrade_converts_string_period_to_datetime(empty_db):
    migrate(empty_db, "0001")
    insert_string_period(empty_db, [
        (1, "2026-10-13T09:00", "2026-10-13T18:30:15"),
        (2, "2026-10-13", "2026-10-14"),              # 날짜만 있는 값
    ])

    migrate(empty_db, "0002")

    assert stored_period(empty_db) == [
        (1, datetime(2026, 10, 13, 9, 0), datetime(2026, 10, 13, 18, 30, 15)),
        (2, datetime(2026, 10, 13, 0, 0), datetime(2026, 10, 14, 23, 59, 59)),
    ]
    columns = {column["name"]: column for column in inspect(empty_db).get_columns("todos")}
    assert not columns["start_at"]["nullable"] and not columns["end_at"]["nullable"]


def test_upgrade_keeps_check_constraints(empty_db):
    migrate(empty_db, "0002")
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
    migrate(empty_db, "0002")

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

    assert version(empty_db) == HEAD
    assert stored_period(empty_db) == []          # 0003 에서 작성자 없는 기존 할 일은 삭제된다


def test_init_db_is_idempotent(empty_db):
    database.init_db()
    database.init_db()
    assert version(empty_db) == HEAD


def test_upgrade_0003_deletes_legacy_todos_and_adds_tables(empty_db):
    migrate(empty_db, "0001")
    insert_string_period(empty_db, [(1, "2026-10-13T09:00", "2026-10-13T18:00")])
    migrate(empty_db, "0002")

    migrate(empty_db, "0003")

    inspector = inspect(empty_db)
    assert {"users", "comments", "activities"} <= set(inspector.get_table_names())
    columns = {column["name"]: column for column in inspector.get_columns("todos")}
    assert "assignee" not in columns
    assert not columns["owner_id"]["nullable"] and columns["assignee_id"]["nullable"]
    assert stored_period(empty_db) == []


def test_upgrade_0003_keeps_check_constraints(empty_db):
    migrate(empty_db, "head")
    with empty_db.begin() as connection:
        connection.execute(text(
            "INSERT INTO users (id, username, display_name, password_hash, created_at)"
            " VALUES (1, 'alice', 'Alice', 'x', '2026-11-01 00:00:00')"
        ))
    with pytest.raises(IntegrityError):
        with empty_db.begin() as connection:
            connection.execute(text(
                "INSERT INTO todos (title, description, start_at, end_at, location, status, priority, owner_id)"
                " VALUES ('Test', '', '2026-10-13 09:00:00', '2026-10-13 18:00:00', '', 'planned', 'urgent', 1)"
            ))


def test_downgrade_0003_restores_free_text_assignee(empty_db):
    migrate(empty_db, "head")

    migrate(empty_db, "0002", command.downgrade)

    inspector = inspect(empty_db)
    assert not {"users", "comments", "activities"} & set(inspector.get_table_names())
    columns = {column["name"] for column in inspector.get_columns("todos")}
    assert "assignee" in columns and "owner_id" not in columns


def test_upgrade_0004_adds_friendships_with_constraints(empty_db):
    migrate(empty_db, "0004")
    with empty_db.begin() as connection:
        connection.execute(text(
            "INSERT INTO users (id, username, display_name, password_hash, created_at) VALUES"
            " (1, 'alice', 'Alice', 'x', '2026-11-01 00:00:00'), (2, 'bob', 'Bob', 'x', '2026-11-01 00:00:00')"
        ))
    insert = "INSERT INTO friendships (requester_id, addressee_id, status, created_at) VALUES ({}, {}, '{}', '2026-11-01')"
    with empty_db.begin() as connection:
        connection.execute(text(insert.format(1, 2, "pending")))
    for values in [(1, 2, "pending"), (1, 1, "pending"), (2, 1, "blocked")]:   # 중복, 자기 자신, 잘못된 상태
        with pytest.raises(IntegrityError):
            with empty_db.begin() as connection:
                connection.execute(text(insert.format(*values)))


def test_downgrade_0004_drops_friendships(empty_db):
    migrate(empty_db, "head")
    migrate(empty_db, "0003", command.downgrade)
    assert "friendships" not in inspect(empty_db).get_table_names()
