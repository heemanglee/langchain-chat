"""add composite index on chat_sessions(user_id, updated_at)

Revision ID: ab24cb2d24e5
Revises: 207e161c145e
Create Date: 2026-02-08 10:06:51.178727

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "ab24cb2d24e5"
down_revision: str | Sequence[str] | None = "207e161c145e"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_index(
        "ix_chat_sessions_user_id_updated_at",
        "chat_sessions",
        ["user_id", "updated_at"],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_chat_sessions_user_id_updated_at", table_name="chat_sessions")
