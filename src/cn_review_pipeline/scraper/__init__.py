"""Scraping layer.

Use ``AsyncFetcher`` as the single HTTP choke-point; it enforces politeness,
robots.txt, retries, and offline-fixture mode.
"""

from .base import AsyncFetcher, FixtureMissingError, RobotsDisallowedError
from .jd import JDReviewScraper
from .tmall import TmallReviewScraper

__all__ = [
    "AsyncFetcher",
    "FixtureMissingError",
    "JDReviewScraper",
    "RobotsDisallowedError",
    "TmallReviewScraper",
]
