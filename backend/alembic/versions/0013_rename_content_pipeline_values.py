"""rename internal content pipeline values

Revision ID: 0013_content_pipeline_values
Revises: 0012_user_soft_delete
"""

from alembic import op


revision = "0013_content_pipeline_values"
down_revision = "0012_user_soft_delete"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("UPDATE articles SET source_type = 'content_pipeline' WHERE source_type = 'phase7'")
    op.execute(
        """
        UPDATE article_translations
        SET content_json = jsonb_set(content_json, '{source}', '"content_pipeline_mistral"'::jsonb)
        WHERE content_json->>'source' = 'phase7_mistral'
        """
    )


def downgrade() -> None:
    op.execute("UPDATE articles SET source_type = 'phase7' WHERE source_type = 'content_pipeline'")
    op.execute(
        """
        UPDATE article_translations
        SET content_json = jsonb_set(content_json, '{source}', '"phase7_mistral"'::jsonb)
        WHERE content_json->>'source' = 'content_pipeline_mistral'
        """
    )
