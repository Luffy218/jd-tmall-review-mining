"""End-to-end processor: RawReview -> ProcessedReview."""

from __future__ import annotations

from collections.abc import Iterable

from ..models import ProcessedReview, RawReview
from .clean import clean_review_text
from .tokenize import detect_language, tokenize


def process_review(raw: RawReview) -> ProcessedReview:
    clean = clean_review_text(raw.text)
    return ProcessedReview(
        platform=raw.platform,
        product_id=raw.product_id,
        review_id=raw.review_id,
        rating=raw.rating,
        text=raw.text,
        clean_text=clean,
        tokens=tokenize(clean),
        language=detect_language(clean) if clean else "unknown",
        created_at=raw.created_at,
        fetched_at=raw.fetched_at,
    )


def process_reviews(raws: Iterable[RawReview]) -> list[ProcessedReview]:
    return [process_review(r) for r in raws]
