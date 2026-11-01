"""친구 요청·친구 관계 추가

Revision ID: 0004
Revises: 0003
Create Date: 2026-11-01
"""
from alembic import op
import sqlalchemy as sa

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "friendships",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("requester_id", sa.Integer, nullable=False),
        sa.Column("addressee_id", sa.Integer, nullable=False),
        sa.Column("status", sa.String(10), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["requester_id"], ["users.id"], name="fk_friendships_requester_id_users", ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["addressee_id"], ["users.id"], name="fk_friendships_addressee_id_users", ondelete="CASCADE",
        ),
        sa.UniqueConstraint("requester_id", "addressee_id", name="uq_friendships_requester_id"),
        sa.CheckConstraint("status IN ('pending', 'accepted')"),
        sa.CheckConstraint("requester_id <> addressee_id"),
    )
    op.create_index("ix_friendships_requester_id", "friendships", ["requester_id"])
    op.create_index("ix_friendships_addressee_id", "friendships", ["addressee_id"])


def downgrade() -> None:
    op.drop_table("friendships")
