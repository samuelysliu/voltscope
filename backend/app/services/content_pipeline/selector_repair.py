from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import sha256
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.errors import AppError
from app.db.base import utcnow
from app.models import SelectorRepairProposal, SourceParserVersion, SourceWhitelist, User
from app.services.content_pipeline.crawlers.base import is_allowed_url
from app.services.content_pipeline.crawlers.http_crawler import fetch_text
from app.services.content_pipeline.parsers.ai_dom_parser import sanitize_dom_sample
from app.services.content_pipeline.parsers.html_parser import parse_html_candidates

REQUIRED_SELECTOR_KEYS = {"article_links", "title", "url"}


@dataclass
class ValidationOutput:
    result: dict[str, Any]
    confidence_score: float


async def get_latest_parser_version(session: AsyncSession, source_id: str) -> SourceParserVersion | None:
    return await session.scalar(
        select(SourceParserVersion)
        .where(SourceParserVersion.source_id == source_id)
        .order_by(SourceParserVersion.is_active.desc(), SourceParserVersion.version.desc())
        .limit(1)
    )


async def next_parser_version(session: AsyncSession, source_id: str) -> int:
    current = await session.scalar(select(func.max(SourceParserVersion.version)).where(SourceParserVersion.source_id == source_id))
    return int(current or 0) + 1


def selector_config_from_sample(source: SourceWhitelist, sample_url: str, final_url: str, sanitized_dom: str) -> dict[str, Any]:
    return {
        "parser_type": "html",
        "selectors": {
            "article_links": "a[href]",
            "title": "a::text",
            "url": "a::attr(href)",
        },
        "sample_url": sample_url,
        "final_url": final_url,
        "domain": source.domain,
        "dom_sample_hash": sha256(sanitized_dom.encode("utf-8")).hexdigest(),
    }


def required_fields_present(config: dict[str, Any]) -> bool:
    selectors = config.get("selectors")
    return isinstance(selectors, dict) and REQUIRED_SELECTOR_KEYS.issubset(set(selectors))


async def validate_selector_config_for_source(source: SourceWhitelist, config: dict[str, Any]) -> ValidationOutput:
    sample_url = str(config.get("sample_url") or source.list_url or source.homepage_url)
    required_ok = required_fields_present(config)
    try:
        raw_html, final_url = await fetch_text(sample_url)
        sanitized = sanitize_dom_sample(raw_html)
        candidates = parse_html_candidates(raw_html, final_url, source.domain, max(10, source.max_candidates_per_run or 10))
        sample_titles = [candidate.title for candidate in candidates[:5]]
        source_domain_valid = all(is_allowed_url(candidate.source_url, source.domain) for candidate in candidates)
        candidate_count = len(candidates)
        passed = required_ok and source_domain_valid and candidate_count >= 3
        confidence = 0.82 if passed else (0.55 if candidate_count else 0.25)
        return ValidationOutput(
            result={
                "passed": passed,
                "candidate_count": candidate_count,
                "required_candidate_count": 3,
                "sample_titles": sample_titles,
                "source_domain_valid": source_domain_valid,
                "required_fields_present": required_ok,
                "sample_url": sample_url,
                "final_url": final_url,
                "dom_sample_hash": sha256(sanitized.encode("utf-8")).hexdigest(),
                "validated_at": datetime.now(UTC).isoformat(),
            },
            confidence_score=confidence,
        )
    except Exception as exc:
        return ValidationOutput(
            result={
                "passed": False,
                "candidate_count": 0,
                "required_candidate_count": 3,
                "sample_titles": [],
                "source_domain_valid": False,
                "required_fields_present": required_ok,
                "sample_url": sample_url,
                "error": str(exc)[:1000],
                "validated_at": datetime.now(UTC).isoformat(),
            },
            confidence_score=0.2,
        )


async def create_selector_repair_proposal(session: AsyncSession, source_id: str) -> SelectorRepairProposal:
    source = await session.get(SourceWhitelist, source_id)
    if source is None:
        raise AppError("CONTENT_SOURCE_NOT_FOUND", "Content source not found", 404)
    old_version = await get_latest_parser_version(session, source.id)
    sample_url = source.list_url or source.homepage_url

    try:
        raw_html, final_url = await fetch_text(sample_url)
        sanitized = sanitize_dom_sample(raw_html)
        proposed_config = selector_config_from_sample(source, sample_url, final_url, sanitized)
        validation = await validate_selector_config_for_source(source, proposed_config)
        summary = (
            "Static DOM analysis found article-like anchors and proposed a conservative "
            "HTML selector set. The proposal is stored for validation and manual approval."
        )
    except Exception as exc:
        proposed_config = {
            "parser_type": "html",
            "selectors": {
                "article_links": "a[href]",
                "title": "a::text",
                "url": "a::attr(href)",
            },
            "sample_url": sample_url,
            "domain": source.domain,
        }
        validation = ValidationOutput(
            result={
                "passed": False,
                "candidate_count": 0,
                "required_candidate_count": 3,
                "sample_titles": [],
                "source_domain_valid": False,
                "required_fields_present": True,
                "sample_url": sample_url,
                "error": str(exc)[:1000],
                "validated_at": datetime.now(UTC).isoformat(),
            },
            confidence_score=0.2,
        )
        summary = "Static DOM analysis could not fetch the source. A baseline HTML selector proposal was created for review."

    now = utcnow()
    status = "validated" if validation.result.get("passed") else "proposed"
    proposal = SelectorRepairProposal(
        source_id=source.id,
        old_parser_version_id=old_version.id if old_version else None,
        proposed_selector_config=proposed_config,
        agent_reasoning_summary=summary,
        validation_result=validation.result,
        confidence_score=validation.confidence_score,
        status=status,
        validated_at=now if status == "validated" else None,
    )
    session.add(proposal)
    await session.flush()
    settings = get_settings()
    if settings.content_pipeline_auto_approve_selector and validation.confidence_score >= 0.9 and validation.result.get("passed"):
        await apply_selector_repair_proposal(session, proposal, None)
    return proposal


async def validate_selector_repair_proposal(session: AsyncSession, proposal_id: str) -> SelectorRepairProposal:
    proposal = await session.get(SelectorRepairProposal, proposal_id)
    if proposal is None:
        raise AppError("SELECTOR_REPAIR_PROPOSAL_NOT_FOUND", "Selector repair proposal not found", 404)
    source = await session.get(SourceWhitelist, proposal.source_id)
    if source is None:
        raise AppError("CONTENT_SOURCE_NOT_FOUND", "Content source not found", 404)
    validation = await validate_selector_config_for_source(source, proposal.proposed_selector_config)
    proposal.validation_result = validation.result
    proposal.confidence_score = validation.confidence_score
    proposal.validated_at = utcnow()
    if proposal.status not in {"approved", "applied", "rejected"}:
        proposal.status = "validated" if validation.result.get("passed") else "proposed"
    await session.flush()
    return proposal


async def apply_selector_repair_proposal(
    session: AsyncSession,
    proposal: SelectorRepairProposal,
    admin: User | None,
) -> SourceParserVersion:
    if proposal.status == "rejected":
        raise AppError("SELECTOR_REPAIR_REJECTED", "Rejected proposals cannot be approved", 409)
    source = await session.get(SourceWhitelist, proposal.source_id)
    if source is None:
        raise AppError("CONTENT_SOURCE_NOT_FOUND", "Content source not found", 404)
    validation = await validate_selector_config_for_source(source, proposal.proposed_selector_config)
    proposal.validation_result = validation.result
    proposal.confidence_score = validation.confidence_score
    proposal.validated_at = utcnow()
    if not validation.result.get("passed"):
        proposal.status = "proposed"
        await session.flush()
        raise AppError("SELECTOR_REPAIR_VALIDATION_FAILED", "Selector repair proposal did not pass validation", 409)

    now = utcnow()
    active_versions = (
        await session.execute(
            select(SourceParserVersion).where(SourceParserVersion.source_id == source.id, SourceParserVersion.is_active.is_(True))
        )
    ).scalars().all()
    for version in active_versions:
        version.is_active = False
        version.validation_status = "retired"
        version.retired_at = now

    parser_version = SourceParserVersion(
        source_id=source.id,
        version=await next_parser_version(session, source.id),
        parser_type=str(proposal.proposed_selector_config.get("parser_type") or "html"),
        selector_config=proposal.proposed_selector_config,
        sample_url=str(proposal.proposed_selector_config.get("sample_url") or source.list_url or source.homepage_url),
        confidence_score=validation.confidence_score,
        validation_status="approved",
        is_active=True,
        created_by="ai_agent",
        approved_by=admin.id if admin else None,
        validation_result=validation.result,
        approved_at=now,
    )
    session.add(parser_version)
    proposal.status = "applied"
    proposal.approved_at = now
    proposal.applied_at = now
    await session.flush()
    return parser_version


async def reject_selector_repair_proposal(session: AsyncSession, proposal_id: str, reason: str = "") -> SelectorRepairProposal:
    proposal = await session.get(SelectorRepairProposal, proposal_id)
    if proposal is None:
        raise AppError("SELECTOR_REPAIR_PROPOSAL_NOT_FOUND", "Selector repair proposal not found", 404)
    if proposal.status == "applied":
        raise AppError("SELECTOR_REPAIR_ALREADY_APPLIED", "Applied proposals cannot be rejected", 409)
    result = proposal.validation_result or {}
    proposal.validation_result = {**result, "rejection_reason": reason or "Rejected by admin"}
    proposal.status = "rejected"
    await session.flush()
    return proposal


async def approve_parser_version(session: AsyncSession, parser_version: SourceParserVersion, admin: User, validate_first: bool = True) -> SourceParserVersion:
    source = await session.get(SourceWhitelist, parser_version.source_id)
    if source is None:
        raise AppError("CONTENT_SOURCE_NOT_FOUND", "Content source not found", 404)
    if parser_version.validation_status == "rejected":
        raise AppError("PARSER_VERSION_REJECTED", "Rejected parser versions cannot be approved", 409)
    if validate_first and parser_version.parser_type == "html":
        validation = await validate_selector_config_for_source(source, parser_version.selector_config)
        parser_version.validation_result = validation.result
        parser_version.confidence_score = validation.confidence_score
        if not validation.result.get("passed"):
            parser_version.validation_status = "draft"
            raise AppError("PARSER_VERSION_VALIDATION_FAILED", "Parser version did not pass validation", 409)

    now = utcnow()
    active_versions = (
        await session.execute(
            select(SourceParserVersion).where(
                SourceParserVersion.source_id == parser_version.source_id,
                SourceParserVersion.is_active.is_(True),
                SourceParserVersion.id != parser_version.id,
            )
        )
    ).scalars().all()
    for version in active_versions:
        version.is_active = False
        version.validation_status = "retired"
        version.retired_at = now
    parser_version.is_active = True
    parser_version.validation_status = "approved"
    parser_version.approved_by = admin.id
    parser_version.approved_at = now
    parser_version.retired_at = None
    await session.flush()
    return parser_version
