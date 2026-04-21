"""Storage adapter contract.

Both Postgres and Mongo implementations must satisfy ``ReviewStore``. Upstream
code (tasks, API, dashboard) depends only on this interface.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Protocol

from ..models import AnalyzedReview, ProcessedReview, RawReview


class ReviewStore(Protocol):
    """The storage adapter interface.

    Implementations MUST:
      * be idempotent on (platform, review_id) — repeated upserts do not
        produce duplicates. This underpins incremental scraping.
      * accept iterables (not lists) — the pipeline streams batches.
    """

    def init_schema(self) -> None:
        """Create tables / collections / indexes. Safe to call repeatedly."""

    def upsert_raw(self, items: Iterable[RawReview]) -> int: ...

    def upsert_processed(self, items: Iterable[ProcessedReview]) -> int: ...

    def upsert_analyzed(self, items: Iterable[AnalyzedReview]) -> int: ...

    def existing_review_ids(self, platform: str, product_id: str) -> set[str]:
        """Return the set of already-stored ``review_id``s for a product — used
        by the scraper to skip already-seen reviews (incremental scrape)."""

    def list_analyzed(
        self, platform: str | None = None, product_id: str | None = None
    ) -> list[AnalyzedReview]: ...

    def close(self) -> None: ...
