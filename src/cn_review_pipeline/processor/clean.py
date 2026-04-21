"""HTML / whitespace cleaning and UTF-8 normalisation."""

from __future__ import annotations

import html
import re
import unicodedata

from bs4 import BeautifulSoup

_WHITESPACE_RE = re.compile(r"\s+")
_URL_RE = re.compile(r"https?://\S+")
_REPEAT_PUNCT_RE = re.compile(r"([!?。！？])\1{2,}")


def strip_html(text: str) -> str:
    """Remove HTML tags, decode entities, collapse whitespace."""
    if not text:
        return ""
    soup = BeautifulSoup(text, "lxml")
    stripped = soup.get_text(separator=" ")
    return html.unescape(stripped)


def normalize(text: str) -> str:
    """UTF-8 normalise, drop URLs, collapse whitespace and repeated punctuation."""
    if not text:
        return ""
    text = unicodedata.normalize("NFKC", text)
    text = _URL_RE.sub("", text)
    text = _REPEAT_PUNCT_RE.sub(r"\1\1", text)
    text = _WHITESPACE_RE.sub(" ", text)
    return text.strip()


def clean_review_text(text: str) -> str:
    return normalize(strip_html(text))
