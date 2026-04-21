"""JD.com review scraper.

JD exposes a public JSONP review endpoint of the form::

    https://club.jd.com/comment/productPageComments.action
        ?productId=<pid>&score=0&sortType=5&page=<n>&pageSize=10&isShadowSku=0

It returns data wrapped like ``fetchJSON_comment98(...)`` which we unwrap in
``AsyncFetcher.get_json``.

Under CRP_OFFLINE_FIXTURES=1 (default) the fetcher serves a canned JSON fixture
so the example is runnable without touching JD's servers. See
``data/fixtures/`` for the shape.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from ..logging_setup import logger
from ..models import RawReview
from .base import AsyncFetcher

JD_COMMENTS_URL = (
    "https://club.jd.com/comment/productPageComments.action"
    "?productId={product_id}&score=0&sortType=5&page={page}&pageSize=10&isShadowSku=0"
)


class JDReviewScraper:
    platform = "jd"

    def __init__(self, fetcher: AsyncFetcher) -> None:
        self._fetcher = fetcher

    async def fetch_page(self, product_id: str, page: int = 0) -> list[RawReview]:
        url = JD_COMMENTS_URL.format(product_id=product_id, page=page)
        logger.info(f"JD fetch product={product_id} page={page}")
        payload = await self._fetcher.get_json(url)
        return [self._parse(product_id, item) for item in payload.get("comments", [])]

    async def fetch_all(
        self, product_id: str, *, max_pages: int = 10
    ) -> list[RawReview]:
        out: list[RawReview] = []
        for page in range(max_pages):
            items = await self.fetch_page(product_id, page=page)
            if not items:
                break
            out.extend(items)
        return out

    # ------------------------------------------------------------------

    def _parse(self, product_id: str, item: dict[str, Any]) -> RawReview:
        created_at = _try_parse_jd_time(item.get("creationTime"))
        return RawReview(
            platform="jd",
            product_id=product_id,
            review_id=str(item.get("id") or item.get("guid") or ""),
            rating=_coerce_int(item.get("score")),
            text=str(item.get("content") or "").strip(),
            created_at=created_at,
            user_id=item.get("userClientShow") or item.get("nickname"),
            user_level=item.get("userLevelName"),
            helpful_votes=_coerce_int(item.get("usefulVoteCount")),
            raw=item,
        )


def _coerce_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (ValueError, TypeError):
        return None


def _try_parse_jd_time(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.strptime(str(value), "%Y-%m-%d %H:%M:%S")
    except ValueError:
        return None
