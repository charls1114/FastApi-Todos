"""태그 important(중요)를 event(행사)로 이름 변경

Revision ID: 0007
Revises: 0006
Create Date: 2026-11-16
"""
from alembic import op
import sqlalchemy as sa

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None

TAG_CHECK_NAME = "todos_tag_check"     # PostgreSQL 이 이름 없는 tag CHECK 제약에 붙이는 이름
OTHER_CHECKS = (
    sa.CheckConstraint("status IN ('planned', 'in_progress', 'done')"),
    sa.CheckConstraint("priority IN ('low', 'medium', 'high')"),
)


def tag_check(tag: str) -> str:
    return f"tag IS NULL OR tag IN ('hangout', 'work', '{tag}', 'trip')"


def rename_tag(old: str, new: str) -> None:
    connection = op.get_bind()
    values = {"old": old, "new": new}
    statements = (
        "UPDATE todos SET tag = :new WHERE tag = :old",
        # 활동 기록에 남은 태그 변경 이력도 함께 바꾼다
        "UPDATE activities SET old_value = :new WHERE field = 'tag' AND old_value = :old",
        "UPDATE activities SET new_value = :new WHERE field = 'tag' AND new_value = :old",
    )

    if connection.dialect.name == "sqlite":
        # SQLite 는 제약을 바꾸려면 테이블을 새로 만들어야 한다. 이름 없는 CHECK 제약은 table_args 로 넘긴 것만 남는다.
        with op.batch_alter_table("todos", table_args=OTHER_CHECKS, recreate="always"):
            pass                                   # tag 제약 없이 다시 만든다
        for statement in statements:
            connection.execute(sa.text(statement), values)
        with op.batch_alter_table(
            "todos", table_args=(*OTHER_CHECKS, sa.CheckConstraint(tag_check(new))), recreate="always",
        ):
            pass
        return

    for check in sa.inspect(connection).get_check_constraints("todos"):
        if "hangout" in check["sqltext"]:
            op.drop_constraint(check["name"], "todos", type_="check")
    for statement in statements:
        connection.execute(sa.text(statement), values)
    op.create_check_constraint(TAG_CHECK_NAME, "todos", tag_check(new))


def upgrade() -> None:
    rename_tag("important", "event")


def downgrade() -> None:
    rename_tag("event", "important")
