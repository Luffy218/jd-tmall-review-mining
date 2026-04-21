"""End-to-end analyzer: ProcessedReview -> AnalyzedReview."""

from __future__ import annotations

from collections.abc import Iterable

from ..models import AnalyzedReview, ProcessedReview
from .keywords import top_textrank_keywords
from .sentiment import get_analyzer


def analyze_review(p: ProcessedReview) -> AnalyzedReview:
    analyzer = get_analyzer()
    sent = analyzer.analyze(p.clean_text, rating=p.rating)
    keywords = top_textrank_keywords(p.clean_text, top_n=5) if p.clean_text else []
    return AnalyzedReview(
        platform=p.platform,
        product_id=p.product_id,
        review_id=p.review_id,
        rating=p.rating,
        text=p.text,
        clean_text=p.clean_text,
        tokens=p.tokens,
        language=p.language,
        created_at=p.created_at,
        fetched_at=p.fetched_at,
        sentiment_label=sent.label,
        sentiment_score=sent.score,
        keywords=keywords,
    )


def analyze_reviews(items: Iterable[ProcessedReview]) -> list[AnalyzedReview]:
    return [analyze_review(p) for p in items]
