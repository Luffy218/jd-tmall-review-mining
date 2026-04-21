"""Pluggable storage layer.

``get_store()`` returns the configured adapter based on ``CRP_STORAGE_BACKEND``.
Both adapters satisfy the ``ReviewStore`` protocol so upstream code stays
backend-agnostic.
"""

from __future__ import annotations

from functools import lru_cache

from ..config import get_settings
from .base import ReviewStore
from .mongo import MongoReviewStore
from .postgres import PostgresReviewStore


@lru_cache(maxsize=1)
def get_store() -> ReviewStore:
    """Return the process-wide storage adapter.

    Cached so SQLAlchemy engine / MongoClient pools are reused across API
    requests and pipeline runs instead of being rebuilt (and leaked) each call.
    """
    settings = get_settings()
    if settings.storage_backend == "mongo":
        return MongoReviewStore(settings.mongo_uri, settings.mongo_db)
    return PostgresReviewStore(settings.postgres_dsn)


__all__ = ["MongoReviewStore", "PostgresReviewStore", "ReviewStore", "get_store"]
