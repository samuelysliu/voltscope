"""add user soft delete state

Revision ID: 0012_user_soft_delete
Revises: 0011_sync_published_translations
"""

import sqlalchemy as sa
from alembic import op


revision = "0012_user_soft_delete"
down_revision = "0011_sync_published_translations"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index("ix_users_deleted_at", "users", ["deleted_at"])


def downgrade() -> None:
    op.drop_index("ix_users_deleted_at", table_name="users")
    op.drop_column("users", "deleted_at")
