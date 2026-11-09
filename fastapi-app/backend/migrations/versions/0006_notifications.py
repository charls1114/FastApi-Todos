"""할일 할당 수락 상태와 사용자별 알림 추가

Revision ID: 0006
Revises: 0005
Create Date: 2026-11-09
"""
from alembic import op
import sqlalchemy as sa

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None

# SQLite 는 테이블을 새로 만들면서 이름 없는 CHECK 제약을 잃으므로 명시해서 넘긴다 (PostgreSQL 에서는 쓰이지 않음)
CHECKS = (
    sa.CheckConstraint("status IN ('planned', 'in_progress', 'done')"),
    sa.CheckConstraint("priority IN ('low', 'medium', 'high')"),
    sa.CheckConstraint("tag IS NULL OR tag IN ('hangout', 'work', 'important', 'trip')"),
)


def upgrade() -> None:
    # 기존에 지정된 담당자는 이미 수락한 것으로 본다
    with op.batch_alter_table("todos", table_args=CHECKS) as batch:
        batch.add_column(sa.Column("assignment_status", sa.String(10), nullable=False, server_default="accepted"))
        batch.create_check_constraint("ck_todos_assignment_status", "assignment_status IN ('pending', 'accepted')")

    op.create_table(
        "notifications",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("user_id", sa.Integer, nullable=False),
        sa.Column("type", sa.String(30), nullable=False),
        sa.Column("message", sa.Text, nullable=False),
        sa.Column("status", sa.String(10), nullable=False, server_default="unread"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("todo_id", sa.Integer, nullable=True),
        sa.Column("todo_title", sa.String(100), nullable=True),
        sa.Column("reason", sa.Text, nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="fk_notifications_user_id_users", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["todo_id"], ["todos.id"], name="fk_notifications_todo_id_todos", ondelete="SET NULL"),
        sa.CheckConstraint("status IN ('unread', 'read')"),
    )
    op.create_index("ix_notifications_user_id", "notifications", ["user_id"])


def downgrade() -> None:
    op.drop_table("notifications")
    with op.batch_alter_table("todos", table_args=CHECKS) as batch:
        batch.drop_constraint("ck_todos_assignment_status", type_="check")
        batch.drop_column("assignment_status")
