"""High-level pipeline orchestration.

These functions compose scraper -> processor -> analyzer -> storage and are
the entry points for the CLI, Celery tasks, and FastAPI. They're deliberately
small: each sub-layer is already self-contained.
"""

from __future__ import annotations

from .analyzer.pipeline import analyze_reviews
from .logging_setup import logger
from .models import AnalyzedReview, RawReview
from .processor.pipeline import process_reviews
from .scraper import AsyncFetcher, JDReviewScraper, TmallReviewScraper
from .storage import get_store


async def scrape_product(
    platform: str, product_id: str, *, max_pages: int = 5, incremental: bool = True
) -> list[RawReview]:
    """Fetch reviews for a product, skipping any review_id already stored.

    Setting ``incremental=False`` re-fetches and lets the store upsert overwrite.
    """
    store = get_store()
    store.init_schema()
    seen = store.existing_review_ids(platform, product_id) if incremental else set()

    async with AsyncFetcher() as fetcher:
        if platform == "jd":
            scraper: JDReviewScraper | TmallReviewScraper = JDReviewScraper(fetcher)
        elif platform == "tmall":
            scraper = TmallReviewScraper(fetcher)
        else:
            raise ValueError(f"Unsupported platform: {platform}")
        fetched = await scraper.fetch_all(product_id, max_pages=max_pages)

    fresh = [r for r in fetched if r.review_id not in seen]
    logger.info(
        f"scrape_product platform={platform} product={product_id} "
        f"fetched={len(fetched)} fresh={len(fresh)}"
    )
    if fresh:
        store.upsert_raw(fresh)
    return fresh


def process_and_store(raws: list[RawReview]) -> list[AnalyzedReview]:
    store = get_store()
    store.init_schema()
    processed = process_reviews(raws)
    store.upsert_processed(processed)
    analyzed = analyze_reviews(processed)
    store.upsert_analyzed(analyzed)
    return analyzed


async def run_full_pipeline(
    platform: str, product_id: str, *, max_pages: int = 5, incremental: bool = True
) -> list[AnalyzedReview]:
    raws = await scrape_product(
        platform, product_id, max_pages=max_pages, incremental=incremental
    )
    return process_and_store(raws)
