"""Celery tasks wrapping the pipeline entry points.

Idempotent upserts in the storage layer mean these tasks are safe to retry.
"""

from __future__ import annotations

import asyncio

from ..logging_setup import configure_logging, logger
from ..pipeline import run_full_pipeline
from .celery_app import celery_app


@celery_app.task(
    name="crp.scrape_product",
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=300,
    retry_jitter=True,
    max_retries=5,
)
def scrape_product_task(
    self, platform: str, product_id: str, max_pages: int = 5, incremental: bool = True
) -> dict:
    configure_logging()
    logger.info(
        f"[task {self.request.id}] scraping platform={platform} product={product_id}"
    )
    analyzed = asyncio.run(
        run_full_pipeline(
            platform, product_id, max_pages=max_pages, incremental=incremental
        )
    )
    return {
        "platform": platform,
        "product_id": product_id,
        "new_reviews": len(analyzed),
    }
