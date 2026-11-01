"""start_at, end_at 을 문자열에서 DateTime 으로 변경

Revision ID: 0002
Revises: 0001
Create Date: 2026-11-01

날짜만 있는 값은 기존 API 규칙대로 시작은 그날 0시, 종료는 그날 23:59:59로 바꾼다.
날짜로 읽을 수 없는 값이 있으면 데이터를 바꾸지 않고 해당 id 를 알려주며 실패한다.
"""
from datetime import datetime

from alembic import op
import sqlalchemy as sa

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None

FIELDS = ("start_at", "end_at")
# SQLite 는 테이블을 새로 만들면서 이름 없는 CHECK 제약을 잃으므로 명시해서 넘긴다 (PostgreSQL 에서는 쓰이지 않음)
CHECKS = (
    sa.CheckConstraint("status IN ('planned', 'in_progress', 'done')"),
    sa.CheckConstraint("priority IN ('low', 'medium', 'high')"),
    sa.CheckConstraint("tag IS NULL OR tag IN ('hangout', 'work', 'important', 'trip')"),
)


def to_datetime(value: str, field: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    if "T" not in value and field == "end_at":
        parsed = parsed.replace(hour=23, minute=59, second=59)
    return parsed


def to_string(value: datetime) -> str:
    return value.isoformat(timespec="seconds" if value.second else "minutes")


def convert(old_type, new_type, transform) -> None:
    connection = op.get_bind()
    old = sa.table("todos", sa.column("id", sa.Integer), *(sa.column(f, old_type) for f in FIELDS))
    rows = connection.execute(sa.select(old)).all()

    converted, invalid = [], []
    for row in rows:
        try:
            converted.append({"row_id": row.id, **{f"new_{f}": transform(getattr(row, f), f) for f in FIELDS}})
        except (TypeError, ValueError):
            invalid.append(row.id)
    if invalid:
        raise RuntimeError(f"todos 의 날짜 값을 변환할 수 없습니다. 먼저 수정하세요: id={invalid}")

    with op.batch_alter_table("todos") as batch:
        for f in FIELDS:
            batch.add_column(sa.Column(f"new_{f}", new_type, nullable=True))

    new = sa.table("todos", sa.column("id", sa.Integer), *(sa.column(f"new_{f}", new_type) for f in FIELDS))
    if converted:
        connection.execute(
            new.update().where(new.c.id == sa.bindparam("row_id")),
            converted,
        )

    with op.batch_alter_table("todos", table_args=CHECKS) as batch:
        for f in FIELDS:
            batch.drop_column(f)
            batch.alter_column(f"new_{f}", new_column_name=f, existing_type=new_type, nullable=False)


def upgrade() -> None:
    convert(sa.String(19), sa.DateTime(), to_datetime)


def downgrade() -> None:
    convert(sa.DateTime(), sa.String(19), lambda value, _field: to_string(value))
