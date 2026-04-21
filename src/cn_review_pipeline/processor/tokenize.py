"""Chinese tokenisation with jieba + stopword filtering + language detection."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import jieba
from langdetect import DetectorFactory, LangDetectException, detect

from ..config import get_settings

# Deterministic langdetect results (per its docs).
DetectorFactory.seed = 0

# Suppress jieba's noisy logger.
jieba.setLogLevel(60)


@lru_cache(maxsize=1)
def _load_stopwords() -> frozenset[str]:
    settings = get_settings()
    path = Path(settings.stopwords_file)
    if not path.exists():
        return frozenset()
    words = {
        line.strip()
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.startswith("#")
    }
    return frozenset(words)


def detect_language(text: str) -> str:
    if not text:
        return "unknown"
    try:
        return detect(text)
    except LangDetectException:
        return "unknown"


def tokenize(text: str, *, remove_stopwords: bool = True) -> list[str]:
    """Tokenise Chinese text (falls back gracefully for non-Chinese)."""
    if not text:
        return []
    tokens = [t for t in jieba.lcut(text) if t.strip()]
    if not remove_stopwords:
        return tokens
    stop = _load_stopwords()
    return [t for t in tokens if t not in stop and len(t.strip()) > 0]
