"""create chat_sessions and chat_messages tables

Revision ID: 207e161c145e
Revises: 4292d1e26dc7
Create Date: 2026-02-07

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "207e161c145e"
down_revision: str | Sequence[str] | None = "4292d1e26dc7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create chat_sessions and chat_messages tables."""
    op.create_table(
        "chat_sessions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("conversation_id", sa.String(36), nullable=False),
        sa.Column("title", sa.String(255), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("conversation_id"),
    )
    op.create_index(
        op.f("ix_chat_sessions_conversation_id"),
        "chat_sessions",
        ["conversation_id"],
        unique=True,
    )
    op.create_index(
        op.f("ix_chat_sessions_user_id"),
        "chat_sessions",
        ["user_id"],
        unique=False,
    )

    op.create_table(
        "chat_messages",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("session_id", sa.Integer(), nullable=False),
        sa.Column("role", sa.String(20), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("tool_calls_json", sa.Text(), nullable=True),
        sa.Column("tool_call_id", sa.String(255), nullable=True),
        sa.Column("tool_name", sa.String(100), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["session_id"], ["chat_sessions.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_chat_messages_session_id"),
        "chat_messages",
        ["session_id"],
        unique=False,
    )


def downgrade() -> None:
    """Drop chat_messages and chat_sessions tables."""
    op.drop_index(op.f("ix_chat_messages_session_id"), table_name="chat_messages")
    op.drop_table("chat_messages")
    op.drop_index(op.f("ix_chat_sessions_user_id"), table_name="chat_sessions")
    op.drop_index(op.f("ix_chat_sessions_conversation_id"), table_name="chat_sessions")
    op.drop_table("chat_sessions")
