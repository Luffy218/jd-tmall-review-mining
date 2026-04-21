"""Run the full pipeline against the bundled offline fixtures.

Useful for dashboard / API demo without any network or DB setup:

    CRP_STORAGE_BACKEND=postgres \\
    CRP_POSTGRES_DSN=sqlite:///data/demo.db \\
    python scripts/load_fixtures.py
"""

from __future__ import annotations

import asyncio

from cn_review_pipeline.logging_setup import configure_logging, logger
from cn_review_pipeline.pipeline import run_full_pipeline


async def main() -> None:
    configure_logging()
    for platform, product_id in (("jd", "100012043978"), ("tmall", "620010218888")):
        results = await run_full_pipeline(platform, product_id, max_pages=2)
        logger.info(f"{platform} {product_id}: {len(results)} analyzed reviews")


if __name__ == "__main__":
    asyncio.run(main())
