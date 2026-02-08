"""add composite index on chat_sessions(user_id, updated_at)

Revision ID: aa47109e820f
Revises: 207e161c145e
Create Date: 2026-02-08 10:05:42.527461

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'aa47109e820f'
down_revision: Union[str, Sequence[str], None] = '207e161c145e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


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
