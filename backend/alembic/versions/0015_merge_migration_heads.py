"""merge user cleanup and content pipeline migration heads

Revision ID: 0015_merge_migration_heads
Revises: 0013_release_deleted_user_emails, 0014_rename_prompt_versions
"""

revision = "0015_merge_migration_heads"
down_revision = ("0013_release_deleted_user_emails", "0014_rename_prompt_versions")
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
