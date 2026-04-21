"""Domain models shared across layers.

Keeping these as plain Pydantic models (rather than ORM rows) decouples the
storage layer from everything else — the scraper emits ``RawReview``, the
processor consumes it and emits ``ProcessedReview``, the analyzer emits
``AnalyzedReview``, and any storage adapter can persist them.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

Platform = Literal["jd", "tmall", "other"]


class RawReview(BaseModel):
    """A review as pulled from a source, with minimal cleaning applied."""

    platform: Platform
    product_id: str
    review_id: str
    rating: int | None = None
    text: str
    created_at: datetime | None = None
    user_id: str | None = None
    user_level: str | None = None
    helpful_votes: int | None = None
    raw: dict[str, Any] = Field(default_factory=dict)
    fetched_at: datetime = Field(default_factory=datetime.utcnow)


class ProcessedReview(BaseModel):
    """A review after cleaning and tokenisation."""

    platform: Platform
    product_id: str
    review_id: str
    rating: int | None
    text: str
    clean_text: str
    tokens: list[str]
    language: str
    created_at: datetime | None = None
    fetched_at: datetime


class AnalyzedReview(BaseModel):
    """A review with sentiment + keyword signals attached."""

    platform: Platform
    product_id: str
    review_id: str
    rating: int | None
    text: str
    clean_text: str
    tokens: list[str]
    language: str
    created_at: datetime | None
    fetched_at: datetime
    sentiment_label: Literal["positive", "negative", "neutral"]
    sentiment_score: float
    keywords: list[str]
