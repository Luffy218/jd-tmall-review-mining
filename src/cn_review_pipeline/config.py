"""Centralised configuration loaded from environment variables / .env.

All modules should import settings from here rather than reading os.environ
directly — this keeps the pipeline configurable and testable.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="CRP_",
        extra="ignore",
        case_sensitive=False,
    )

    # Storage
    storage_backend: Literal["postgres", "mongo"] = "postgres"
    postgres_dsn: str = "postgresql+psycopg://crp:crp@localhost:5432/crp"
    mongo_uri: str = "mongodb://localhost:27017"
    mongo_db: str = "crp"

    # Scraping
    respect_robots: bool = True
    request_delay_seconds: float = 2.0
    max_concurrency: int = 2
    user_agent_rotate: bool = True
    offline_fixtures: bool = True
    http_proxy: str | None = None
    request_timeout_seconds: float = 20.0
    max_retries: int = 4

    # Celery
    celery_broker_url: str = "redis://localhost:6379/0"
    celery_result_backend: str = "redis://localhost:6379/1"

    # Analysis
    sentiment_backend: Literal["baseline", "bert"] = "baseline"
    bert_model: str = "uer/roberta-base-finetuned-jd-binary-chinese"

    # Logging
    log_level: str = "INFO"

    # Paths
    fixtures_dir: str = Field(default="data/fixtures")
    stopwords_file: str = Field(default="data/stopwords/zh_stopwords.txt")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
