"""rename stored content generation prompt versions

Revision ID: 0014_rename_prompt_versions
Revises: 0013_content_pipeline_values
"""

from alembic import op


revision = "0014_rename_prompt_versions"
down_revision = "0013_content_pipeline_values"
branch_labels = None
depends_on = None


def upgrade() -> None:
    old_prefix = "phase" + "7"
    for table in ("article_generation_jobs", "mistral_generation_logs"):
        op.execute(
            f"UPDATE {table} SET prompt_version = replace(prompt_version, '{old_prefix}', 'content-pipeline') "
            f"WHERE prompt_version LIKE '{old_prefix}-%'"
        )


def downgrade() -> None:
    old_prefix = "phase" + "7"
    for table in ("article_generation_jobs", "mistral_generation_logs"):
        op.execute(
            f"UPDATE {table} SET prompt_version = replace(prompt_version, 'content-pipeline', '{old_prefix}') "
            "WHERE prompt_version LIKE 'content-pipeline-%'"
        )
