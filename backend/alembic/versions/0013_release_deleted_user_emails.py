"""release email addresses held by soft-deleted users

Revision ID: 0013_release_deleted_user_emails
Revises: 0012_user_soft_delete
"""

from alembic import op

revision = "0013_release_deleted_user_emails"
down_revision = "0012_user_soft_delete"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        UPDATE users
        SET email = 'deleted-' || id::text || '@users.invalid'
        WHERE deleted_at IS NOT NULL
          AND email NOT LIKE 'deleted-%@users.invalid'
        """
    )


def downgrade() -> None:
    # Deleted users' original email addresses are intentionally not recoverable.
    pass
