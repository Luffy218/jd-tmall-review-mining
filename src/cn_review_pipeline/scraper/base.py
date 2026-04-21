"""Base fetcher with header rotation, rate limiting, robots.txt enforcement,
retry/backoff, and an offline fixture mode.

All platform scrapers should compose ``AsyncFetcher`` rather than instantiating
an HTTP client themselves. This is the single choke-point where we enforce
politeness and legal constraints.

Legal/ToS note
--------------
JD.com and Tmall's Terms of Service prohibit automated scraping. The fixture
mode (``CRP_OFFLINE_FIXTURES=1``) is the default so the pipeline is fully
runnable without hitting their servers. If you disable it, you are responsible
for complying with their ToS and any applicable law in your jurisdiction.
"""

from __future__ import annotations

import asyncio
import json
import random
from pathlib import Path
from typing import Any
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

import httpx
from tenacity import (
    AsyncRetrying,
    RetryError,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential_jitter,
)

from ..config import get_settings
from ..logging_setup import logger

DEFAULT_USER_AGENTS: tuple[str, ...] = (
    # Hand-picked desktop UAs. We rotate for politeness (varied traffic), NOT to
    # evade fingerprinting — this is not a bypass mechanism.
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:124.0) Gecko/20100101 Firefox/124.0",
)


class RobotsDisallowedError(RuntimeError):
    """Raised when robots.txt forbids the URL and we are configured to respect it."""


class FixtureMissingError(FileNotFoundError):
    """Raised when offline mode is on but no fixture is available for a URL."""


class AsyncFetcher:
    """Async HTTP client with built-in politeness.

    Responsibilities (and only these — keep it boring):
      * Rotate User-Agent from a small built-in pool.
      * Enforce a per-host delay (``request_delay_seconds``).
      * Cap concurrency via a semaphore.
      * Respect robots.txt (cached per host).
      * Retry transient failures with exponential backoff.
      * When ``offline_fixtures`` is set, serve responses from ``data/fixtures/``
        instead of the network. Fixture path is derived from URL.
    """

    def __init__(
        self,
        *,
        extra_headers: dict[str, str] | None = None,
        fixtures_dir: str | Path | None = None,
    ) -> None:
        self._settings = get_settings()
        self._semaphore = asyncio.Semaphore(self._settings.max_concurrency)
        self._last_request_at: dict[str, float] = {}
        self._robots_cache: dict[str, RobotFileParser | None] = {}
        self._extra_headers = extra_headers or {}
        self._fixtures_dir = Path(fixtures_dir or self._settings.fixtures_dir)

        proxy = self._settings.http_proxy or None
        self._client = httpx.AsyncClient(
            timeout=self._settings.request_timeout_seconds,
            follow_redirects=True,
            proxy=proxy,
        )

    # ------------------------------------------------------------------ lifecycle

    async def __aenter__(self) -> AsyncFetcher:
        return self

    async def __aexit__(self, *_: object) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        await self._client.aclose()

    # ------------------------------------------------------------------ public API

    async def get_json(self, url: str, *, headers: dict[str, str] | None = None) -> Any:
        text = await self.get_text(url, headers=headers)
        # Some JD endpoints wrap JSON in ``fetchJSON_xxx(...)``; strip that.
        text = text.strip()
        if text.startswith("fetchJSON") and "(" in text and text.endswith(");"):
            text = text[text.index("(") + 1 : -2]
        return json.loads(text)

    async def get_text(self, url: str, *, headers: dict[str, str] | None = None) -> str:
        if self._settings.offline_fixtures:
            return self._load_fixture(url)

        await self._ensure_allowed(url)
        async with self._semaphore:
            await self._throttle(url)
            merged_headers = self._build_headers(headers)
            try:
                async for attempt in AsyncRetrying(
                    stop=stop_after_attempt(self._settings.max_retries),
                    wait=wait_exponential_jitter(initial=1.0, max=30.0),
                    retry=retry_if_exception_type(
                        (httpx.TransportError, httpx.HTTPStatusError)
                    ),
                    reraise=True,
                ):
                    with attempt:
                        logger.debug(
                            f"GET {url} (attempt {attempt.retry_state.attempt_number})"
                        )
                        resp = await self._client.get(url, headers=merged_headers)
                        resp.raise_for_status()
                        resp.encoding = resp.encoding or "utf-8"
                        return resp.text
            except RetryError as exc:  # pragma: no cover - defensive
                raise RuntimeError(f"Exhausted retries for {url}") from exc
        raise RuntimeError("unreachable")

    # ------------------------------------------------------------------ internals

    def _build_headers(self, extra: dict[str, str] | None) -> dict[str, str]:
        headers: dict[str, str] = {
            "Accept": "text/html,application/json;q=0.9,*/*;q=0.5",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        }
        if self._settings.user_agent_rotate:
            headers["User-Agent"] = random.choice(DEFAULT_USER_AGENTS)
        else:
            headers["User-Agent"] = DEFAULT_USER_AGENTS[0]
        headers.update(self._extra_headers)
        if extra:
            headers.update(extra)
        return headers

    async def _throttle(self, url: str) -> None:
        host = urlparse(url).netloc
        now = asyncio.get_event_loop().time()
        last = self._last_request_at.get(host)
        if last is not None:
            wait = self._settings.request_delay_seconds - (now - last)
            if wait > 0:
                await asyncio.sleep(wait)
        self._last_request_at[host] = asyncio.get_event_loop().time()

    async def _ensure_allowed(self, url: str) -> None:
        if not self._settings.respect_robots:
            return
        parsed = urlparse(url)
        host_key = f"{parsed.scheme}://{parsed.netloc}"
        parser = self._robots_cache.get(host_key)
        if parser is None and host_key not in self._robots_cache:
            parser = await self._load_robots(host_key)
            self._robots_cache[host_key] = parser
        if parser is None:
            return  # Could not fetch robots.txt — fail open (same as urllib default).
        ua = self._extra_headers.get("User-Agent", "*")
        if not parser.can_fetch(ua, url):
            raise RobotsDisallowedError(f"robots.txt disallows {url}")

    async def _load_robots(self, host_key: str) -> RobotFileParser | None:
        robots_url = f"{host_key}/robots.txt"
        try:
            resp = await self._client.get(robots_url, timeout=10.0)
            if resp.status_code >= 400:
                return None
            parser = RobotFileParser()
            parser.parse(resp.text.splitlines())
            return parser
        except httpx.HTTPError:
            logger.warning(f"Could not fetch {robots_url}; treating as permissive")
            return None

    # ------------------------------------------------------------------ fixtures

    def _load_fixture(self, url: str) -> str:
        path = self._fixture_path(url)
        if not path.exists():
            raise FixtureMissingError(
                f"Offline mode on but no fixture at {path} for URL {url}. "
                "Set CRP_OFFLINE_FIXTURES=0 to allow live requests."
            )
        return path.read_text(encoding="utf-8")

    def _fixture_path(self, url: str) -> Path:
        parsed = urlparse(url)
        safe_path = parsed.path.strip("/").replace("/", "_") or "index"
        query = parsed.query.replace("&", "_").replace("=", "-")
        name = f"{parsed.netloc}__{safe_path}"
        if query:
            name += f"__{query}"
        return self._fixtures_dir / f"{name}.txt"
