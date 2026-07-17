from types import SimpleNamespace
from typing import cast

import pytest
from fastapi import BackgroundTasks

import app.api.v1.admin as admin_api
from app.core.config import Settings
from app.core.errors import AppError
from app.jobs.content_pipeline import is_retryable_pipeline_error, next_generation_candidate, report_counts
from app.models import ContentCandidate, SourceWhitelist
from app.schemas.admin import AdminContentPipelineRunPayload
from app.services.content_pipeline.ai.article_generator import normalize_article_payload, queue_article_generation
from app.services.content_pipeline.ai.mistral_client import MistralClient
from app.services.content_pipeline.ai.prompts import (
    article_length_requirement,
    article_review_messages,
    article_translation_messages,
    article_translation_revision_messages,
)
from app.services.content_pipeline.candidates import create_candidate_from_crawl
from app.services.content_pipeline.crawlers.base import CrawledCandidate
from app.services.content_pipeline.quality_gates import count_en_words, sentence_overlap_ratio


def candidate(candidate_id: str, category: str) -> ContentCandidate:
    return cast(ContentCandidate, SimpleNamespace(id=candidate_id, quota_category=category))


def test_daily_pipeline_defaults_target_five_successes() -> None:
    assert Settings.model_fields["content_pipeline_daily_min_articles"].default == 5


def test_english_article_minimum_is_two_hundred_words() -> None:
    assert Settings.model_fields["content_pipeline_min_en_words"].default == 200
    assert article_length_requirement("en") == (200, "at least 230 English words")


def test_failed_quota_candidate_is_replaced_by_same_category() -> None:
    taiwan_failed = candidate("tw-1", "taiwan_media")
    taiwan_replacement = candidate("tw-2", "taiwan_media")
    international = candidate("intl-1", "international_media")
    pool = [taiwan_failed, international, taiwan_replacement]

    selected = next_generation_candidate(pool, {taiwan_failed.id}, [], taiwan_min=1, international_min=1)

    assert selected is taiwan_replacement


def test_successful_quota_candidates_are_counted_instead_of_attempts() -> None:
    taiwan = candidate("tw-1", "taiwan_media")
    international = candidate("intl-1", "international_media")
    fallback = candidate("other-1", "reference_only")
    pool = [taiwan, international, fallback]

    selected = next_generation_candidate(pool, {taiwan.id}, [taiwan], taiwan_min=1, international_min=1)

    assert selected is international
    counts = report_counts([taiwan, international], [SimpleNamespace(id="article-1", status="draft")])
    assert counts["taiwan_media_count"] == 1
    assert counts["international_count"] == 1
    assert counts["total_ready_for_review"] == 1


def test_candidate_selection_stops_only_when_pool_is_exhausted() -> None:
    pool = [candidate("one", "reference_only"), candidate("two", "reference_only")]

    selected = next_generation_candidate(pool, {"one", "two"}, [], taiwan_min=0, international_min=0)

    assert selected is None


def test_overlap_gate_ignores_short_common_phrase_but_flags_long_copy() -> None:
    item = cast(
        ContentCandidate,
        SimpleNamespace(
            source_excerpt="alpha beta gamma delta epsilon zeta eta theta iota kappa lambda mu",
            raw_text_excerpt=None,
        ),
    )

    assert sentence_overlap_ratio(item, "alpha beta gamma delta epsilon zeta eta theta") == 0.0
    assert sentence_overlap_ratio(item, "alpha beta gamma delta epsilon zeta eta theta iota kappa") > 0.35


def test_editor_agent_receives_writer_draft_and_source_url() -> None:
    item = cast(
        ContentCandidate,
        SimpleNamespace(source_url="https://example.com/story"),
    )
    messages = article_review_messages(
        item,
        {"verified_facts": ["fact one", "fact two", "fact three"]},
        "zh-TW",
        {"title": "Writer draft", "html": "<p>Draft</p>"},
    )

    assert "independent senior news editor" in messages[0]["content"]
    assert "Writer draft" in messages[1]["content"]
    assert "https://example.com/story" in messages[1]["content"]


def test_reviewer_can_use_a_separate_model() -> None:
    assert MistralClient("review-model").model_name == "review-model"


def test_normalized_article_counts_the_sanitized_html_body() -> None:
    html_body = f"<p>{' '.join(f'word{index}' for index in range(410))}</p>"

    payload = normalize_article_payload(
        {
            "title": "A complete report",
            "slug": "a-complete-report",
            "excerpt": "A concrete summary.",
            "html": html_body,
            "text": "This incomplete field should not replace the complete HTML body.",
            "seo_title": "A complete report",
            "seo_description": "A concrete summary.",
        }
    )

    assert count_en_words(payload["text"]) == 410


def test_english_translation_uses_finalized_chinese_master() -> None:
    item = cast(
        ContentCandidate,
        SimpleNamespace(source_url="https://example.com/story"),
    )
    zh_article = {"title": "中文定稿", "html": "<p>完整中文內容</p>", "text": "完整中文內容"}

    messages = article_translation_messages(
        item,
        {"verified_facts": ["fact one", "fact two", "fact three"]},
        zh_article,
    )

    instruction = messages[0]["content"] + messages[1]["content"]
    assert "Chinese article is the master copy" in instruction
    assert "Do not independently regenerate" in instruction
    assert "中文定稿" in instruction
    assert "publication gate is 200 English words" in instruction
    assert "at least 230 English words" in instruction


def test_short_english_translation_revision_restores_chinese_details() -> None:
    item = cast(ContentCandidate, SimpleNamespace(source_url="https://example.com/story"))

    messages = article_translation_revision_messages(
        item,
        {"verified_facts": ["fact one", "fact two", "fact three"]},
        {"title": "中文定稿", "html": "<p>完整中文內容</p>"},
        {"title": "Draft", "html": "<p>Draft</p>", "text": "Draft"},
        ["en_article_short"],
        {"en_words": 187},
    )

    instruction = messages[1]["content"]
    assert "has 187 English words" in instruction
    assert "publication gate is 200" in instruction
    assert "at least 230 English words" in instruction
    assert "中文定稿" in instruction


def test_dns_failure_is_retryable_but_quality_failure_is_not() -> None:
    dns_error = AppError(
        "SOURCE_ARTICLE_FETCH_FAILED",
        "Unable to read the original article",
        422,
        {"reason": "[Errno -2] Name or service not known"},
    )
    quality_error = AppError("ARTICLE_GENERATION_QUALITY_GATE_FAILED", "Generated article failed quality gate", 422)

    assert is_retryable_pipeline_error(dns_error) is True
    assert is_retryable_pipeline_error(quality_error) is False


@pytest.mark.asyncio
async def test_recrawled_transient_failure_returns_to_pending() -> None:
    existing = cast(
        ContentCandidate,
        SimpleNamespace(
            decision="failed",
            rejection_reason="generation_failed",
            fetched_at=None,
        ),
    )

    class ExistingCandidateSession:
        async def scalar(self, statement: object) -> ContentCandidate:
            return existing

    source = cast(SourceWhitelist, SimpleNamespace(id="source-1"))
    crawled = CrawledCandidate(source_url="https://example.com/news/1", title="EV charging update")

    result = await create_candidate_from_crawl(
        cast(object, ExistingCandidateSession()),
        source,
        "crawler-run-1",
        crawled,
    )

    assert result is None
    assert existing.decision == "pending"
    assert existing.rejection_reason is None
    assert existing.fetched_at is not None


@pytest.mark.asyncio
async def test_retrying_interrupted_candidate_clears_stale_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    interrupted_candidate = cast(
        ContentCandidate,
        SimpleNamespace(
            id="candidate-1",
            decision="failed",
            rejection_reason="generation_interrupted",
        ),
    )

    class QueueSession:
        def __init__(self) -> None:
            self.scalar_results = [interrupted_candidate, None]
            self.added: list[object] = []
            self.committed = False

        async def scalar(self, statement: object) -> object:
            return self.scalar_results.pop(0)

        def add(self, value: object) -> None:
            self.added.append(value)

        async def commit(self) -> None:
            self.committed = True

        async def refresh(self, value: object) -> None:
            return None

    monkeypatch.setattr(MistralClient, "is_configured", property(lambda self: True))
    session = QueueSession()

    job, queued_candidate, created = await queue_article_generation(cast(object, session), interrupted_candidate.id)

    assert created is True
    assert job.status == "pending"
    assert queued_candidate.decision == "pending"
    assert queued_candidate.rejection_reason is None
    assert session.committed is True


@pytest.mark.asyncio
async def test_manual_pipeline_endpoint_queues_background_work(monkeypatch: pytest.MonkeyPatch) -> None:
    class EmptySession:
        committed = False

        async def scalar(self, statement: object) -> None:
            return None

        async def commit(self) -> None:
            self.committed = True

    async def fake_upsert_report(session: object, report_date: object, values: dict) -> SimpleNamespace:
        assert values["status"] == "running"
        return SimpleNamespace(id="report-1")

    monkeypatch.setattr(admin_api, "upsert_report", fake_upsert_report)
    session = EmptySession()
    tasks = BackgroundTasks()

    result = await admin_api.run_admin_content_pipeline(
        AdminContentPipelineRunPayload(date="2026-07-13", dry_run=True),
        tasks,
        cast(object, session),
    )

    assert result.status == "queued"
    assert result.report_date.isoformat() == "2026-07-13"
    assert result.already_running is False
    assert session.committed is True
    assert len(tasks.tasks) == 1
