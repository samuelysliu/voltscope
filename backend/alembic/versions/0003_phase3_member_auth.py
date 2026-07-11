"""phase 3 member auth constraints

Revision ID: 0003_phase3_member_auth
Revises: 0002_prd_step1_foundation
Create Date: 2026-07-09
"""

from collections.abc import Sequence

from alembic import op

revision = "0003_phase3_member_auth"
down_revision = "0002_prd_step1_foundation"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_unique_constraint("uq_article_likes_article_id_user_id", "article_likes", ["article_id", "user_id"])


def downgrade() -> None:
    op.drop_constraint("uq_article_likes_article_id_user_id", "article_likes", type_="unique")
