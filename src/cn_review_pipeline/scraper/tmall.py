"""Tmall review scraper.

Tmall's review endpoints require session cookies + anti-bot tokens that the
site rotates aggressively. We do NOT attempt to bypass those — instead this
scraper targets the public AJAX response shape and relies on the caller to
either supply a cookie jar or run under ``CRP_OFFLINE_FIXTURES=1`` (default).

Under offline mode we serve a canned fixture so the pipeline is runnable.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from ..logging_setup import logger
from ..models import RawReview
from .base import AsyncFetcher

TMALL_REVIEWS_URL = (
    "https://rate.tmall.com/list_detail_rate.htm"
    "?itemId={product_id}&currentPage={page}&order=3"
)


class TmallReviewScraper:
    platform = "tmall"

    def __init__(self, fetcher: AsyncFetcher) -> None:
        self._fetcher = fetcher

    async def fetch_page(self, product_id: str, page: int = 1) -> list[RawReview]:
        url = TMALL_REVIEWS_URL.format(product_id=product_id, page=page)
        logger.info(f"Tmall fetch product={product_id} page={page}")
        payload = await self._fetcher.get_json(url)
        data = payload.get("rateDetail", {}).get("rateList", []) or []
        return [self._parse(product_id, item) for item in data]

    async def fetch_all(
        self, product_id: str, *, max_pages: int = 10
    ) -> list[RawReview]:
        out: list[RawReview] = []
        for page in range(1, max_pages + 1):
            items = await self.fetch_page(product_id, page=page)
            if not items:
                break
            out.extend(items)
        return out

    # ------------------------------------------------------------------

    def _parse(self, product_id: str, item: dict[str, Any]) -> RawReview:
        created_at = _try_parse_tmall_time(item.get("rateDate"))
        return RawReview(
            platform="tmall",
            product_id=product_id,
            review_id=str(item.get("id") or item.get("tradeId") or ""),
            rating=None,  # Tmall generally doesn't expose numeric rating on reviews.
            text=str(item.get("rateContent") or "").strip(),
            created_at=created_at,
            user_id=item.get("displayUserNick") or item.get("userVipLevel"),
            user_level=item.get("userVipLevel"),
            helpful_votes=None,
            raw=item,
        )


def _try_parse_tmall_time(value: Any) -> datetime | None:
    if not value:
        return None
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
        try:
            return datetime.strptime(str(value), fmt)
        except ValueError:
            continue
    return None
