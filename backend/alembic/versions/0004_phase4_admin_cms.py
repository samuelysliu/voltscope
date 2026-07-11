"""phase 4 admin cms

Revision ID: 0004_phase4_admin_cms
Revises: 0003_phase3_member_auth
Create Date: 2026-07-09
"""

from collections.abc import Sequence

from alembic import op

revision = "0004_phase4_admin_cms"
down_revision = "0003_phase3_member_auth"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column("ads", "campaign_id", nullable=True)
    op.alter_column("ads", "image_media_id", nullable=True)


def downgrade() -> None:
    op.alter_column("ads", "image_media_id", nullable=False)
    op.alter_column("ads", "campaign_id", nullable=False)
