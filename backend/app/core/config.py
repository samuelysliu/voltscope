from functools import lru_cache
from typing import Literal

from pydantic import AnyHttpUrl, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: Literal["local", "test", "production"] = "local"
    frontend_url: AnyHttpUrl = "http://localhost:3000"
    api_base_url: AnyHttpUrl = "http://localhost:8000/api/v1"

    database_url: str = "postgresql+asyncpg://voltscope:change-me@localhost:5432/voltscope"
    redis_url: str = "redis://localhost:6379/0"

    jwt_secret: str = Field(default="dev-only-secret-change-me", min_length=16)
    jwt_access_token_expire_minutes: int = 30
    jwt_refresh_token_expire_days: int = 14
    default_admin_email: str = "admin@example.com"
    default_admin_password: str = "change-me-now"

    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    email_from: str = ""
    email_provider: Literal["console", "smtp"] = "console"
    email_subject_prefix: str = "VoltScope"
    smtp_starttls: bool = True
    smtp_use_tls: bool = False
    smtp_timeout_seconds: int = 15

    ai_auto_publish: bool = False
    upload_dir: str = "/app/uploads"

    content_pipeline_daily_enabled: bool = True
    content_pipeline_auto_publish: bool = False
    content_pipeline_daily_min_articles: int = 3
    content_pipeline_daily_taiwan_media_min: int = 1
    content_pipeline_daily_international_min: int = 2
    content_pipeline_timezone: str = "Asia/Taipei"
    content_pipeline_daily_hour: int = 5
    content_pipeline_auto_approve_selector: bool = False
    content_pipeline_crawler_timeout_seconds: int = 30
    content_pipeline_playwright_enabled: bool = False

    mistral_api_key: str = ""
    mistral_model: str = "mistral-large-latest"
    mistral_request_timeout_seconds: int = 60
    mistral_max_retries: int = 3
    mistral_prompt_version: str = "content-pipeline-v3"

    content_pipeline_min_zh_chars: int = 600
    content_pipeline_min_en_words: int = 500
    content_pipeline_max_source_sentence_overlap: float = 0.15

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()
