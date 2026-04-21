"""Complaint / strength detection built on top of sentiment + keywords.

The simple but effective approach here: aggregate keywords separately across
negative vs positive reviews and return the terms that are characteristic of
each pole (i.e. appear disproportionately in one side).
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable

from ..models import AnalyzedReview


def _top_terms(reviews: Iterable[AnalyzedReview], *, top_n: int) -> list[tuple[str, int]]:
    counter: Counter[str] = Counter()
    for r in reviews:
        counter.update(r.keywords)
    return counter.most_common(top_n)


def complaints_and_strengths(
    reviews: list[AnalyzedReview], *, top_n: int = 10
) -> dict[str, list[tuple[str, int]]]:
    pos = [r for r in reviews if r.sentiment_label == "positive"]
    neg = [r for r in reviews if r.sentiment_label == "negative"]
    pos_counts = Counter(t for r in pos for t in r.keywords)
    neg_counts = Counter(t for r in neg for t in r.keywords)

    # Characteristic terms: raw count minus opposite-pole count. Avoids the
    # usual "common words dominate both lists" failure mode.
    strengths = sorted(
        ((t, c - neg_counts.get(t, 0)) for t, c in pos_counts.items()),
        key=lambda kv: kv[1],
        reverse=True,
    )
    complaints = sorted(
        ((t, c - pos_counts.get(t, 0)) for t, c in neg_counts.items()),
        key=lambda kv: kv[1],
        reverse=True,
    )
    return {
        "strengths": [(t, int(c)) for t, c in strengths[:top_n] if c > 0],
        "complaints": [(t, int(c)) for t, c in complaints[:top_n] if c > 0],
        "top_positive_terms": _top_terms(pos, top_n=top_n),
        "top_negative_terms": _top_terms(neg, top_n=top_n),
    }
