"""사용자, 작성자·담당자 연결, 댓글, 활동 기록 추가

Revision ID: 0003
Revises: 0002
Create Date: 2026-11-01

기존 할 일은 작성자를 알 수 없으므로 삭제한다 (작성자 정보 없이 남겨 둘 수 없음).
자유 텍스트 담당자(assignee)는 users 를 가리키는 assignee_id 로 바뀐다.
"""
from alembic import op
import sqlalchemy as sa

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None

# SQLite 는 테이블을 새로 만들면서 이름 없는 CHECK 제약을 잃으므로 명시해서 넘긴다 (PostgreSQL 에서는 쓰이지 않음)
CHECKS = (
    sa.CheckConstraint("status IN ('planned', 'in_progress', 'done')"),
    sa.CheckConstraint("priority IN ('low', 'medium', 'high')"),
    sa.CheckConstraint("tag IS NULL OR tag IN ('hangout', 'work', 'important', 'trip')"),
)


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("username", sa.String(30), nullable=False),
        sa.Column("display_name", sa.String(50), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("username", name="uq_users_username"),
    )

    op.execute("DELETE FROM todos")
    with op.batch_alter_table("todos", table_args=CHECKS) as batch:
        batch.drop_column("assignee")
        batch.add_column(sa.Column("owner_id", sa.Integer, nullable=False))
        batch.add_column(sa.Column("assignee_id", sa.Integer, nullable=True))
        batch.create_foreign_key("fk_todos_owner_id_users", "users", ["owner_id"], ["id"], ondelete="CASCADE")
        batch.create_foreign_key("fk_todos_assignee_id_users", "users", ["assignee_id"], ["id"], ondelete="SET NULL")
        batch.create_index("ix_todos_owner_id", ["owner_id"])
        batch.create_index("ix_todos_assignee_id", ["assignee_id"])

    op.create_table(
        "comments",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("todo_id", sa.Integer, nullable=False),
        sa.Column("author_id", sa.Integer, nullable=True),
        sa.Column("body", sa.Text, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["todo_id"], ["todos.id"], name="fk_comments_todo_id_todos", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["author_id"], ["users.id"], name="fk_comments_author_id_users", ondelete="SET NULL"),
    )
    op.create_index("ix_comments_todo_id", "comments", ["todo_id"])

    op.create_table(
        "activities",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("todo_id", sa.Integer, nullable=False),
        sa.Column("actor_id", sa.Integer, nullable=True),
        sa.Column("action", sa.String(20), nullable=False),
        sa.Column("field", sa.String(30), nullable=True),
        sa.Column("old_value", sa.Text, nullable=True),
        sa.Column("new_value", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["todo_id"], ["todos.id"], name="fk_activities_todo_id_todos", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["actor_id"], ["users.id"], name="fk_activities_actor_id_users", ondelete="SET NULL"),
    )
    op.create_index("ix_activities_todo_id", "activities", ["todo_id"])


def downgrade() -> None:
    op.drop_table("activities")
    op.drop_table("comments")
    with op.batch_alter_table("todos", table_args=CHECKS) as batch:
        batch.drop_index("ix_todos_assignee_id")
        batch.drop_index("ix_todos_owner_id")
        batch.drop_constraint("fk_todos_assignee_id_users", type_="foreignkey")
        batch.drop_constraint("fk_todos_owner_id_users", type_="foreignkey")
        batch.drop_column("assignee_id")
        batch.drop_column("owner_id")
        batch.add_column(sa.Column("assignee", sa.Text, nullable=False, server_default=""))
    op.drop_table("users")
