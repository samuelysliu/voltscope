import inspect
from datetime import date

import pytest
from fastapi.params import Query
from sqlalchemy.dialects import postgresql

from app.api.v1.admin import (
    admin_articles,
    build_admin_articles_query,
    release_deleted_article_slug_conflicts,
    released_article_slug,
)
from app.core.errors import AppError
from app.schemas.admin import AdminArticlePayload


def compiled_query(**filters: object) -> str:
    statement = build_admin_articles_query(**filters)
    return str(statement.compile(dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True}))


def test_admin_article_list_defaults_to_twenty_per_page() -> None:
    page_size = inspect.signature(admin_articles).parameters["page_size"].default

    assert isinstance(page_size, Query)
    assert page_size.default == 20


def test_admin_article_query_searches_content_and_orders_by_creation_time() -> None:
    sql = compiled_query(q="battery", status="draft")

    assert "article_translations.content_text" in sql
    assert "article_translations.title" in sql
    assert "articles.status = 'draft'" in sql
    assert "articles.created_at DESC, articles.id DESC" in sql


def test_admin_article_query_filters_topic_and_inclusive_creation_dates() -> None:
    sql = compiled_query(
        topic="charging",
        created_from=date(2026, 7, 1),
        created_to=date(2026, 7, 15),
    )

    assert "topics.slug = 'charging'" in sql
    assert "articles.created_at >= '2026-06-30 16:00:00+00:00'" in sql
    assert "articles.created_at < '2026-07-15 16:00:00+00:00'" in sql


@pytest.mark.asyncio
async def test_admin_article_list_rejects_reversed_date_range() -> None:
    with pytest.raises(AppError) as error:
        await admin_articles(
            session=None,
            created_from=date(2026, 7, 15),
            created_to=date(2026, 7, 1),
        )

    assert error.value.code == "INVALID_ARTICLE_DATE_RANGE"


def article_payload(**overrides: object) -> AdminArticlePayload:
    values = {
        "author_id": None,
        "status": "draft",
        "topic_ids": [],
        "translations": [
            {
                "locale": "zh-TW",
                "title": "測試文章",
                "slug": "test-article",
                "excerpt": "測試摘要",
                "content_html": "<p>測試內容</p>",
                "content_text": "測試內容",
            }
        ],
    }
    values.update(overrides)
    return AdminArticlePayload.model_validate(values)


def test_admin_article_payload_rejects_duplicate_locales_and_topics() -> None:
    duplicate_translation = {
        "locale": "zh-TW",
        "title": "另一篇文章",
        "slug": "another-article",
        "excerpt": "另一段摘要",
        "content_html": "<p>另一段內容</p>",
        "content_text": "另一段內容",
    }

    with pytest.raises(ValueError):
        article_payload(translations=[article_payload().translations[0], duplicate_translation])
    with pytest.raises(ValueError):
        article_payload(topic_ids=["topic-1", "topic-1"])


def test_released_article_slug_is_unique_and_stays_within_database_limit() -> None:
    released = released_article_slug("a" * 220, "12345678-1234-1234-1234-123456789012")

    assert released.endswith("-deleted-12345678")
    assert len(released) == 220


@pytest.mark.asyncio
async def test_deleted_article_slug_conflict_is_released() -> None:
    conflicting_translation = type(
        "ConflictingTranslation",
        (),
        {"id": "12345678-1234-1234-1234-123456789012", "slug": "test-article"},
    )()

    class QueryResult:
        def first(self) -> tuple[object, date]:
            return conflicting_translation, date(2026, 7, 1)

    class ConflictSession:
        flushed = False

        async def execute(self, statement: object) -> QueryResult:
            return QueryResult()

        async def flush(self) -> None:
            self.flushed = True

    session = ConflictSession()
    payload = article_payload()

    await release_deleted_article_slug_conflicts("current-article", payload.translations, session)

    assert conflicting_translation.slug == "test-article-deleted-12345678"
    assert session.flushed is True
