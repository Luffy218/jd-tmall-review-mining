"""Sentiment analysis.

Two backends are supported, selected via ``CRP_SENTIMENT_BACKEND``:

* ``baseline`` — a small rule-based lexicon + rating heuristic. Pure Python,
  no heavy deps. Good enough to smoke-test the pipeline and as a fallback
  when the BERT model can't be loaded (e.g. no internet, no GPU).
* ``bert`` — a fine-tuned Chinese BERT/RoBERTa model via HuggingFace
  Transformers. Loaded lazily and optionally (``pip install .[ml]``). Falls
  back to the baseline if transformers/torch aren't installed.

Both backends implement the same ``analyze(text, rating=None)`` contract.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from typing import Literal, Protocol

from ..config import get_settings
from ..logging_setup import logger

SentimentLabel = Literal["positive", "negative", "neutral"]


@dataclass(frozen=True)
class SentimentResult:
    label: SentimentLabel
    score: float  # signed: positive in [0, 1], negative in [-1, 0]


class SentimentAnalyzer(Protocol):
    def analyze(self, text: str, *, rating: int | None = None) -> SentimentResult: ...


# --------------------------------------------------------------------------- baseline

# Tiny lexicon. In production you'd use something like BosonNLP or HowNet;
# this is intentionally minimal so the baseline is dependency-free.
_POSITIVE_TERMS: frozenset[str] = frozenset(
    {
        "好", "很好", "非常好", "不错", "棒", "赞", "满意", "喜欢", "推荐",
        "完美", "给力", "优秀", "物美价廉", "超值", "快", "便宜", "舒适",
        "精致", "漂亮", "惊喜", "值得", "划算", "耐用",
    }
)
_NEGATIVE_TERMS: frozenset[str] = frozenset(
    {
        "差", "很差", "太差", "不好", "烂", "坑", "骗", "假", "慢", "贵",
        "失望", "后悔", "垃圾", "退货", "投诉", "问题", "破损", "难用",
        "难吃", "味道怪", "色差", "掉色", "异味", "虚标", "卡顿", "漏液",
    }
)
_NEGATION_TERMS: frozenset[str] = frozenset({"不", "没", "无", "未", "别"})


class RuleBasedSentimentAnalyzer:
    def analyze(self, text: str, *, rating: int | None = None) -> SentimentResult:
        score = 0.0
        if text:
            # Very cheap: count lexicon hits, with a tiny negation handling.
            for term in _POSITIVE_TERMS:
                score += text.count(term)
            for term in _NEGATIVE_TERMS:
                score -= text.count(term)
            # Negation only dampens positive signals ("不好", "没问题" etc.). Negative
            # terms already capture their own negation, so applying it there would
            # double-count (e.g. "不好" hits _NEGATIVE_TERMS AND contains "不").
            if score > 0 and any(neg in text for neg in _NEGATION_TERMS):
                score *= 0.5
            # Normalise by length so long gushing reviews don't dominate.
            denom = max(len(text) / 20, 1.0)
            score = score / denom

        # Anchor on explicit rating when present (1-5 scale).
        if rating is not None:
            rating_score = (rating - 3) / 2  # -1..1
            score = 0.5 * score + 0.5 * rating_score

        # Clamp and label
        score = max(-1.0, min(1.0, score))
        if score > 0.15:
            label: SentimentLabel = "positive"
        elif score < -0.15:
            label = "negative"
        else:
            label = "neutral"
        return SentimentResult(label=label, score=score)


# --------------------------------------------------------------------------- BERT


class BertSentimentAnalyzer:
    def __init__(self, model_name: str) -> None:
        self._pipeline = _load_bert_pipeline(model_name)

    def analyze(self, text: str, *, rating: int | None = None) -> SentimentResult:
        if not text.strip():
            return SentimentResult(label="neutral", score=0.0)
        result = self._pipeline(text[:512])[0]
        raw_label = result["label"].lower()
        score = float(result["score"])
        if "pos" in raw_label or raw_label in {"1", "positive"}:
            return SentimentResult(label="positive", score=score)
        if "neg" in raw_label or raw_label in {"0", "negative"}:
            return SentimentResult(label="negative", score=-score)
        return SentimentResult(label="neutral", score=0.0)


@lru_cache(maxsize=1)
def _load_bert_pipeline(model_name: str):  # pragma: no cover - exercised via integration
    from transformers import pipeline  # local import: optional extra

    logger.info(f"Loading BERT sentiment pipeline: {model_name}")
    return pipeline("sentiment-analysis", model=model_name, truncation=True)


# --------------------------------------------------------------------------- factory


@lru_cache(maxsize=1)
def get_analyzer() -> SentimentAnalyzer:
    settings = get_settings()
    if settings.sentiment_backend == "bert":
        try:
            return BertSentimentAnalyzer(settings.bert_model)
        except Exception as exc:  # pragma: no cover - depends on env
            logger.warning(
                f"Falling back to rule-based sentiment (BERT load failed: {exc})"
            )
    return RuleBasedSentimentAnalyzer()
