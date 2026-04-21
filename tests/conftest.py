"""Shared pytest fixtures.

All tests run against:
  * SQLite (via the Postgres adapter's dialect-agnostic fallback), so no running
    Postgres is required.
  * Offline fixture mode, so no network access is required.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(autouse=True)
def _env(tmp_path, monkeypatch):
    monkeypatch.setenv("CRP_OFFLINE_FIXTURES", "1")
    monkeypatch.setenv("CRP_RESPECT_ROBOTS", "0")
    monkeypatch.setenv("CRP_REQUEST_DELAY_SECONDS", "0")
    monkeypatch.setenv("CRP_STORAGE_BACKEND", "postgres")
    monkeypatch.setenv("CRP_POSTGRES_DSN", f"sqlite:///{tmp_path / 'test.db'}")
    monkeypatch.setenv("CRP_SENTIMENT_BACKEND", "baseline")
    monkeypatch.setenv(
        "CRP_FIXTURES_DIR", str(REPO_ROOT / "data" / "fixtures")
    )
    monkeypatch.setenv(
        "CRP_STOPWORDS_FILE",
        str(REPO_ROOT / "data" / "stopwords" / "zh_stopwords.txt"),
    )
    # Reset the cached settings + analyzer + stopwords between tests.
    # NB: grab the tokenize submodule via ``importlib`` — the processor
    # package __init__ rebinds the name ``tokenize`` to the function so
    # ``cn_review_pipeline.processor.tokenize`` attribute access gives us
    # the function, not the submodule.
    import importlib

    from cn_review_pipeline import config, storage
    from cn_review_pipeline.analyzer import sentiment

    tokenize_mod = importlib.import_module("cn_review_pipeline.processor.tokenize")

    config.get_settings.cache_clear()
    sentiment.get_analyzer.cache_clear()
    storage.get_store.cache_clear()
    tokenize_mod._load_stopwords.cache_clear()
    os.environ.pop("JIEBA_CACHE", None)
    yield
    config.get_settings.cache_clear()
    sentiment.get_analyzer.cache_clear()
    storage.get_store.cache_clear()
    tokenize_mod._load_stopwords.cache_clear()
