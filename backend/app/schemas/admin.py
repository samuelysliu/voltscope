from datetime import date as Date
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, HttpUrl, model_validator

from app.schemas.content import ArticleTranslationIn


class AdminArticlePayload(BaseModel):
    author_id: str | None = None
    status: Literal["draft", "published", "archived"] = "draft"
    is_featured: bool = False
    show_ads: bool = True
    hero_image_url: str | None = Field(default=None, max_length=1000)
    thumbnail_url: str | None = Field(default=None, max_length=1000)
    og_image_url: str | None = Field(default=None, max_length=1000)
    topic_ids: list[str] = Field(default_factory=list)
    translations: list[ArticleTranslationIn] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_unique_relations(self) -> "AdminArticlePayload":
        locales = [translation.locale for translation in self.translations]
        if len(locales) != len(set(locales)):
            raise ValueError("Each article translation locale must be unique")
        if len(self.topic_ids) != len(set(self.topic_ids)):
            raise ValueError("Article topic IDs must be unique")
        return self


class AdminArticleListItem(BaseModel):
    id: str
    status: str
    is_featured: bool
    show_ads: bool
    created_at: datetime
    updated_at: datetime
    published_at: datetime | None = None
    title: str
    slug: str
    excerpt: str
    locale: str
    topics: list[dict]


class AdminUserUpdate(BaseModel):
    display_name: str | None = Field(default=None, min_length=1, max_length=160)
    role: Literal["member", "admin"] | None = None
    email_verified: bool | None = None
    is_active: bool | None = None


class AdminAdPayload(BaseModel):
    name: str = Field(min_length=1, max_length=180)
    image_url: str = Field(min_length=1, max_length=1000)
    target_url: HttpUrl
    alt_text: str = Field(min_length=1, max_length=255)
    placement: Literal["home", "article_top", "article_middle", "article_bottom", "sidebar"] = "home"
    status: Literal["active", "inactive"] = "active"
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    weight: int = 0


class AdminAdOut(BaseModel):
    id: str
    name: str | None
    image_url: str | None
    target_url: str
    alt_text: str
    placement: str
    status: str
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    weight: int


class AdminAiSourcePayload(BaseModel):
    name: str = Field(min_length=1, max_length=180)
    base_url: HttpUrl
    rss_url: HttpUrl | None = None
    source_type: Literal["website", "rss", "api"] = "website"
    is_active: bool = True


class AdminAiSourceOut(BaseModel):
    id: str
    name: str
    base_url: str
    rss_url: str | None = None
    source_type: str
    is_active: bool
    created_at: datetime
    updated_at: datetime


class AdminAiCandidateOut(BaseModel):
    id: str
    job_id: str
    source_url: str
    source_title: str
    source_name: str
    source_published_at: datetime | None = None
    raw_excerpt: str | None = None
    decision: str
    rejection_reason: str | None = None
    created_at: datetime


class AdminAiJobOut(BaseModel):
    id: str
    status: str
    started_at: datetime | None = None
    finished_at: datetime | None = None
    error_message: str | None = None
    created_at: datetime
    candidate_count: int = 0
    pending_count: int = 0
    accepted_count: int = 0
    rejected_count: int = 0


class AdminAiJobDetailOut(AdminAiJobOut):
    candidates: list[AdminAiCandidateOut] = Field(default_factory=list)


class AdminAiRejectPayload(BaseModel):
    reason: str = Field(default="", max_length=1000)


SourceGroup = Literal[
    "taiwan_media",
    "international_media",
    "government",
    "local_government",
    "charging_operator",
    "official_brand",
    "research_report",
    "community_signal",
]
SourceRegion = Literal["taiwan", "international"]
SourceLanguage = Literal["zh", "en", "mixed"]
TrustLevel = Literal["high", "medium", "low"]
CrawlMethod = Literal["rss", "api", "html", "playwright", "hybrid"]
QuotaRole = Literal["taiwan_daily", "international_daily", "event_driven", "reference_only"]
SourceHealth = Literal["healthy", "degraded", "failed", "disabled"]
ParserType = Literal["rss", "api", "html", "playwright", "ai_agent"]
ParserValidationStatus = Literal["draft", "validated", "approved", "rejected", "retired"]
ParserCreatedBy = Literal["admin", "system", "ai_agent"]
CrawlerJobType = Literal["daily_pipeline", "source_test", "selector_validation", "manual_run"]
CrawlerRunStatus = Literal["pending", "running", "success", "partial_success", "failed"]
CandidateDecision = Literal["pending", "accepted", "rejected", "generated", "published", "failed"]
SelectorRepairStatus = Literal["proposed", "validated", "approved", "rejected", "applied"]


class AdminSourceParserVersionOut(BaseModel):
    id: str
    source_id: str
    version: int
    parser_type: str
    selector_config: dict
    sample_url: str | None = None
    confidence_score: float | None = None
    validation_status: str
    is_active: bool
    created_by: str
    approved_by: str | None = None
    validation_result: dict | None = None
    created_at: datetime
    approved_at: datetime | None = None
    retired_at: datetime | None = None


class AdminSourceParserVersionPayload(BaseModel):
    parser_type: ParserType = "html"
    selector_config: dict = Field(default_factory=dict)
    sample_url: str | None = Field(default=None, max_length=1000)
    confidence_score: float | None = Field(default=None, ge=0, le=1)
    validation_status: ParserValidationStatus = "draft"
    is_active: bool = False


class AdminSelectorRepairCreatePayload(BaseModel):
    source_id: str


class AdminSelectorRepairRejectPayload(BaseModel):
    reason: str = Field(default="Rejected by admin", max_length=1000)


class AdminSelectorRepairProposalOut(BaseModel):
    id: str
    source_id: str
    source_name: str | None = None
    old_parser_version_id: str | None = None
    proposed_selector_config: dict
    agent_reasoning_summary: str | None = None
    validation_result: dict | None = None
    confidence_score: float | None = None
    status: str
    created_at: datetime
    validated_at: datetime | None = None
    approved_at: datetime | None = None
    applied_at: datetime | None = None


class AdminCrawlerRunOut(BaseModel):
    id: str
    source_id: str | None = None
    job_type: str
    status: str
    started_at: datetime
    finished_at: datetime | None = None
    candidates_found: int
    candidates_accepted: int
    error_message: str | None = None
    fallback_used: dict | None = None
    created_at: datetime


class AdminCrawlerCandidateOut(BaseModel):
    source_url: str
    title: str
    excerpt: str | None = None
    published_at: datetime | None = None
    author: str | None = None
    parser_type: str
    confidence_score: float | None = None


class AdminContentCandidateOut(BaseModel):
    id: str
    crawler_run_id: str
    source_id: str
    source_name: str | None = None
    source_url: str
    canonical_url: str | None = None
    source_title: str
    source_excerpt: str | None = None
    source_author: str | None = None
    source_published_at: datetime | None = None
    fetched_at: datetime
    normalized_hash: str
    raw_text_excerpt: str | None = None
    factual_notes: dict | None = None
    relevance_score: float | None = None
    novelty_score: float | None = None
    quota_category: str
    decision: str
    rejection_reason: str | None = None
    created_at: datetime
    updated_at: datetime


class AdminContentCandidateListOut(BaseModel):
    items: list[AdminContentCandidateOut] = Field(default_factory=list)
    total: int
    page: int
    page_size: int


class AdminMistralGenerationLogOut(BaseModel):
    id: str
    generation_job_id: str | None = None
    purpose: str
    model_name: str
    prompt_version: str
    input_token_count: int | None = None
    output_token_count: int | None = None
    latency_ms: int | None = None
    status: str
    error_message: str | None = None
    created_at: datetime


class AdminArticleGenerationJobOut(BaseModel):
    id: str
    candidate_id: str
    status: str
    provider: str
    model_name: str
    prompt_version: str
    started_at: datetime | None = None
    finished_at: datetime | None = None
    error_message: str | None = None
    retry_count: int
    quality_gate_result: dict | None = None
    generated_article_id: str | None = None
    created_at: datetime
    logs: list[AdminMistralGenerationLogOut] = Field(default_factory=list)


class AdminCandidateRejectPayload(BaseModel):
    reason: str = Field(default="Rejected by admin", max_length=500)


class AdminQuotaSelectionOut(BaseModel):
    candidates: list[AdminContentCandidateOut] = Field(default_factory=list)
    taiwan_count: int
    international_count: int
    total_count: int


class AdminCandidateGenerateOut(BaseModel):
    job: AdminArticleGenerationJobOut
    candidate: AdminContentCandidateOut
    article_id: str | None = None
    article_status: str


class AdminContentPipelineRunPayload(BaseModel):
    date: Date | None = None
    force: bool = False
    dry_run: bool = False


class AdminDailyContentReportOut(BaseModel):
    id: str
    report_date: Date
    status: str
    total_published: int
    total_ready_for_review: int
    taiwan_media_count: int
    international_count: int
    event_driven_count: int
    quota_met: bool
    quota_detail: dict
    failed_sources: list | None = None
    degraded_sources: list | None = None
    message: str | None = None
    created_at: datetime
    updated_at: datetime


class AdminDailyContentReportListOut(BaseModel):
    items: list[AdminDailyContentReportOut] = Field(default_factory=list)
    total: int
    page: int
    page_size: int


class AdminContentPipelineRunAcceptedOut(BaseModel):
    run_id: str
    report_date: Date
    status: Literal["queued", "running"]
    already_running: bool = False


class AdminSourceHealthOut(BaseModel):
    id: str
    name: str
    domain: str
    enabled: bool
    quota_role: str
    health_status: str
    consecutive_failures: int
    last_success_at: datetime | None = None
    last_failure_at: datetime | None = None


class AdminFailedQualityGateOut(BaseModel):
    job_id: str
    candidate_id: str
    source_id: str
    source_name: str | None = None
    source_title: str
    status: str
    error_message: str | None = None
    quality_gate_result: dict
    created_at: datetime


class AdminContentPipelineMonitoringOut(BaseModel):
    latest_report: AdminDailyContentReportOut | None = None
    quota_preview: AdminQuotaSelectionOut
    source_health: list[AdminSourceHealthOut] = Field(default_factory=list)
    failed_quality_gates: list[AdminFailedQualityGateOut] = Field(default_factory=list)
    report_status_counts: dict[str, int] = Field(default_factory=dict)
    candidate_decision_counts: dict[str, int] = Field(default_factory=dict)


class AdminContentSourcePayload(BaseModel):
    name: str = Field(min_length=1, max_length=180)
    homepage_url: HttpUrl
    list_url: HttpUrl | None = None
    rss_url: HttpUrl | None = None
    source_group: SourceGroup
    region: SourceRegion
    default_language: SourceLanguage = "mixed"
    trust_level: TrustLevel = "medium"
    enabled: bool = True
    allowed_topics: list[str] = Field(default_factory=list)
    crawl_method: CrawlMethod = "rss"
    quota_role: QuotaRole = "reference_only"
    allow_auto_publish: bool = False
    requires_review: bool = True
    crawl_frequency_minutes: int = Field(default=360, ge=15, le=43200)
    max_candidates_per_run: int = Field(default=10, ge=1, le=100)


class AdminContentSourceOut(BaseModel):
    id: str
    name: str
    homepage_url: str
    list_url: str | None = None
    rss_url: str | None = None
    domain: str
    source_group: str
    region: str
    default_language: str
    trust_level: str
    enabled: bool
    allowed_topics: list[str]
    crawl_method: str
    quota_role: str
    allow_auto_publish: bool
    requires_review: bool
    crawl_frequency_minutes: int
    max_candidates_per_run: int
    robots_checked_at: datetime | None = None
    last_success_at: datetime | None = None
    last_failure_at: datetime | None = None
    consecutive_failures: int
    health_status: str
    created_at: datetime
    updated_at: datetime


class AdminContentSourceDetailOut(AdminContentSourceOut):
    parser_versions: list[AdminSourceParserVersionOut] = Field(default_factory=list)
    recent_crawler_runs: list[AdminCrawlerRunOut] = Field(default_factory=list)


class AdminCandidateIngestOut(BaseModel):
    source: AdminContentSourceOut
    crawler_run_id: str
    created_count: int
    duplicate_count: int
    rejected_count: int
    candidates: list[AdminContentCandidateOut] = Field(default_factory=list)


class AdminTestCrawlOut(BaseModel):
    source: AdminContentSourceOut
    run: AdminCrawlerRunOut
    candidates: list[AdminCrawlerCandidateOut] = Field(default_factory=list)
    fallback_used: dict | None = None
