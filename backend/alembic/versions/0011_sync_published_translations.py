"""sync published article translation states

Revision ID: 0011_sync_published_translations
Revises: 0010_phase7_selector_repairs
"""

from alembic import op


revision = "0011_sync_published_translations"
down_revision = "0010_phase7_selector_repairs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        UPDATE article_translations
        SET translation_status = 'published'
        WHERE article_id IN (
            SELECT id FROM articles
            WHERE status = 'published' AND deleted_at IS NULL
        )
        """
    )
    op.execute(
        """
        WITH article_text AS (
            SELECT
                a.id AS article_id,
                lower(string_agg(t.title || ' ' || t.content_text, ' ')) AS body
            FROM articles a
            JOIN article_translations t ON t.article_id = a.id
            WHERE a.source_type = 'phase7' AND a.deleted_at IS NULL
            GROUP BY a.id
        ), classified AS (
            SELECT
                article_id,
                CASE
                    WHEN body ~ 'robotaxi|autonomous|self-driving|driverless|mobility|lidar|fleet' THEN 'smart-mobility'
                    WHEN body ~ 'charging station|fast charger|supercharger|charging network' THEN 'charging-station'
                    WHEN body ~ 'discount|rebate|incentive|coupon|financing|0% interest' THEN 'charging-deals'
                    WHEN body ~ 'charging|charger|battery|kwh' THEN 'charging'
                    ELSE 'ev'
                END AS slug
            FROM article_text
        )
        INSERT INTO article_topics (article_id, topic_id, is_primary, created_at)
        SELECT classified.article_id, topics.id, true, now()
        FROM classified
        JOIN topics ON topics.slug = classified.slug
        WHERE NOT EXISTS (
            SELECT 1 FROM article_topics existing
            WHERE existing.article_id = classified.article_id
        )
        ON CONFLICT DO NOTHING
        """
    )
    op.execute(
        """
        INSERT INTO article_tags (article_id, tag_id, created_at)
        SELECT article_topics.article_id, tags.id, now()
        FROM article_topics
        JOIN topics ON topics.id = article_topics.topic_id
        JOIN tags ON tags.slug = topics.slug AND tags.is_active = true
        JOIN articles ON articles.id = article_topics.article_id
        WHERE articles.source_type = 'phase7'
          AND articles.deleted_at IS NULL
          AND article_topics.is_primary = true
          AND NOT EXISTS (
              SELECT 1 FROM article_tags existing
              WHERE existing.article_id = article_topics.article_id
                AND existing.tag_id = tags.id
          )
        ON CONFLICT DO NOTHING
        """
    )


def downgrade() -> None:
    pass
