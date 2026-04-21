"""FastAPI microservice.

Endpoints:

* ``POST /scrape`` — enqueue a scrape job on Celery.
* ``GET  /reviews`` — list analyzed reviews for a product.
* ``GET  /insights/{platform}/{product_id}`` — complaints + strengths.
* ``GET  /healthz`` — liveness probe.
"""

from __future__ import annotations

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel

from ..analyzer.insights import complaints_and_strengths
from ..logging_setup import configure_logging, logger
from ..models import AnalyzedReview
from ..storage import get_store


class ScrapeRequest(BaseModel):
    platform: str
    product_id: str
    max_pages: int = 5
    incremental: bool = True


class ScrapeResponse(BaseModel):
    task_id: str
    queued: bool = True


configure_logging()

app = FastAPI(title="CN Review Pipeline", version="0.1.0")


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/scrape", response_model=ScrapeResponse)
def trigger_scrape(req: ScrapeRequest) -> ScrapeResponse:
    # Lazy import so the API can boot without Redis (e.g. for local `/reviews`
    # inspection on a pre-populated store).
    try:
        from ..tasks.jobs import scrape_product_task
    except Exception as exc:  # pragma: no cover
        raise HTTPException(503, f"Celery not available: {exc}") from exc

    async_result = scrape_product_task.delay(
        req.platform, req.product_id, req.max_pages, req.incremental
    )
    logger.info(f"enqueued scrape task={async_result.id} platform={req.platform}")
    return ScrapeResponse(task_id=async_result.id)


@app.get("/reviews", response_model=list[AnalyzedReview])
def list_reviews(
    platform: str | None = Query(None),
    product_id: str | None = Query(None),
    limit: int = Query(50, ge=1, le=500),
) -> list[AnalyzedReview]:
    store = get_store()
    store.init_schema()
    return store.list_analyzed(platform=platform, product_id=product_id)[:limit]


@app.get("/insights/{platform}/{product_id}")
def insights(platform: str, product_id: str) -> dict:
    store = get_store()
    store.init_schema()
    rows = store.list_analyzed(platform=platform, product_id=product_id)
    if not rows:
        raise HTTPException(404, "No analyzed reviews for that product")
    return complaints_and_strengths(rows)
