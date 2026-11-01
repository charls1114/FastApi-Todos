"""todos 테이블 생성 (Alembic 도입 전 스키마)

Revision ID: 0001
Revises:
Create Date: 2026-11-01
"""
from alembic import op
import sqlalchemy as sa

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "todos",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("title", sa.String(100), nullable=False),
        sa.Column("description", sa.Text, nullable=False),
        sa.Column("start_at", sa.String(19), nullable=False),
        sa.Column("end_at", sa.String(19), nullable=False),
        sa.Column("location", sa.Text, nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("tag", sa.String(20), nullable=True),
        sa.Column("priority", sa.String(10), nullable=False),
        sa.Column("assignee", sa.Text, nullable=False),
        sa.CheckConstraint("status IN ('planned', 'in_progress', 'done')"),
        sa.CheckConstraint("priority IN ('low', 'medium', 'high')"),
        sa.CheckConstraint("tag IS NULL OR tag IN ('hangout', 'work', 'important', 'trip')"),
    )


def downgrade() -> None:
    op.drop_table("todos")
