"""PostgreSQL adapter backed by SQLAlchemy 2.0.

Tables:
  * ``raw_reviews`` — verbatim payloads, one row per (platform, review_id).
  * ``processed_reviews`` — cleaned text + tokens.
  * ``analyzed_reviews`` — sentiment + keywords.

Upserts use ``INSERT ... ON CONFLICT DO UPDATE`` (Postgres) and fall back to
a SELECT+UPDATE dance on SQLite (so the test suite can run without Postgres).
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    DateTime,
    Float,
    Integer,
    String,
    Text,
    create_engine,
    select,
)
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column

from ..models import AnalyzedReview, ProcessedReview, RawReview


class Base(DeclarativeBase):
    pass


class RawReviewRow(Base):
    __tablename__ = "raw_reviews"
    platform: Mapped[str] = mapped_column(String(16), primary_key=True)
    review_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    product_id: Mapped[str] = mapped_column(String(64), index=True)
    rating: Mapped[int | None] = mapped_column(Integer, nullable=True)
    text: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    user_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    user_level: Mapped[str | None] = mapped_column(String(64), nullable=True)
    helpful_votes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    raw: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    fetched_at: Mapped[datetime] = mapped_column(DateTime)


class ProcessedReviewRow(Base):
    __tablename__ = "processed_reviews"
    platform: Mapped[str] = mapped_column(String(16), primary_key=True)
    review_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    product_id: Mapped[str] = mapped_column(String(64), index=True)
    rating: Mapped[int | None] = mapped_column(Integer, nullable=True)
    text: Mapped[str] = mapped_column(Text)
    clean_text: Mapped[str] = mapped_column(Text)
    tokens: Mapped[str] = mapped_column(Text)  # JSON-encoded list
    language: Mapped[str] = mapped_column(String(16))
    created_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    fetched_at: Mapped[datetime] = mapped_column(DateTime)


class AnalyzedReviewRow(Base):
    __tablename__ = "analyzed_reviews"
    platform: Mapped[str] = mapped_column(String(16), primary_key=True)
    review_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    product_id: Mapped[str] = mapped_column(String(64), index=True)
    rating: Mapped[int | None] = mapped_column(Integer, nullable=True)
    text: Mapped[str] = mapped_column(Text)
    clean_text: Mapped[str] = mapped_column(Text)
    tokens: Mapped[str] = mapped_column(Text)
    language: Mapped[str] = mapped_column(String(16))
    created_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    fetched_at: Mapped[datetime] = mapped_column(DateTime)
    sentiment_label: Mapped[str] = mapped_column(String(16), index=True)
    sentiment_score: Mapped[float] = mapped_column(Float)
    keywords: Mapped[str] = mapped_column(Text)  # JSON-encoded list


class PostgresReviewStore:
    """SQLAlchemy-backed store. Works with Postgres in prod and SQLite in tests."""

    def __init__(self, dsn: str) -> None:
        self._engine = create_engine(dsn, future=True)

    @property
    def dialect(self) -> str:
        return self._engine.dialect.name

    def init_schema(self) -> None:
        Base.metadata.create_all(self._engine)

    def close(self) -> None:
        self._engine.dispose()

    # ------------------------------------------------------------------ upserts

    def upsert_raw(self, items: Iterable[RawReview]) -> int:
        rows = [_raw_to_dict(i) for i in items]
        return self._upsert(RawReviewRow, rows, ["platform", "review_id"])

    def upsert_processed(self, items: Iterable[ProcessedReview]) -> int:
        rows = [_processed_to_dict(i) for i in items]
        return self._upsert(ProcessedReviewRow, rows, ["platform", "review_id"])

    def upsert_analyzed(self, items: Iterable[AnalyzedReview]) -> int:
        rows = [_analyzed_to_dict(i) for i in items]
        return self._upsert(AnalyzedReviewRow, rows, ["platform", "review_id"])

    # ------------------------------------------------------------------ queries

    def existing_review_ids(self, platform: str, product_id: str) -> set[str]:
        with Session(self._engine) as session:
            stmt = select(RawReviewRow.review_id).where(
                RawReviewRow.platform == platform,
                RawReviewRow.product_id == product_id,
            )
            return set(session.scalars(stmt))

    def list_analyzed(
        self, platform: str | None = None, product_id: str | None = None
    ) -> list[AnalyzedReview]:
        with Session(self._engine) as session:
            stmt = select(AnalyzedReviewRow)
            if platform:
                stmt = stmt.where(AnalyzedReviewRow.platform == platform)
            if product_id:
                stmt = stmt.where(AnalyzedReviewRow.product_id == product_id)
            rows = session.scalars(stmt).all()
            return [_row_to_analyzed(r) for r in rows]

    # ------------------------------------------------------------------ internals

    def _upsert(self, model: type, rows: list[dict[str, Any]], pk_cols: list[str]) -> int:
        if not rows:
            return 0
        dialect = self._engine.dialect.name
        with Session(self._engine) as session, session.begin():
            if dialect == "postgresql":
                stmt = pg_insert(model).values(rows)
                update_cols = {
                    c.name: stmt.excluded[c.name]
                    for c in model.__table__.columns
                    if c.name not in pk_cols
                }
                stmt = stmt.on_conflict_do_update(index_elements=pk_cols, set_=update_cols)
                session.execute(stmt)
            else:
                # Portable fallback (SQLite, tests).
                for row in rows:
                    pk_filter = {c: row[c] for c in pk_cols}
                    existing = session.get(model, tuple(pk_filter.values()))
                    if existing is None:
                        session.add(model(**row))
                    else:
                        for key, value in row.items():
                            setattr(existing, key, value)
        return len(rows)


# --------------------------------------------------------------------------- serde


def _raw_to_dict(r: RawReview) -> dict[str, Any]:
    return {
        "platform": r.platform,
        "review_id": r.review_id,
        "product_id": r.product_id,
        "rating": r.rating,
        "text": r.text,
        "created_at": r.created_at,
        "user_id": r.user_id,
        "user_level": r.user_level,
        "helpful_votes": r.helpful_votes,
        "raw": r.raw,
        "fetched_at": r.fetched_at,
    }


def _processed_to_dict(p: ProcessedReview) -> dict[str, Any]:
    return {
        "platform": p.platform,
        "review_id": p.review_id,
        "product_id": p.product_id,
        "rating": p.rating,
        "text": p.text,
        "clean_text": p.clean_text,
        "tokens": json.dumps(p.tokens, ensure_ascii=False),
        "language": p.language,
        "created_at": p.created_at,
        "fetched_at": p.fetched_at,
    }


def _analyzed_to_dict(a: AnalyzedReview) -> dict[str, Any]:
    return {
        "platform": a.platform,
        "review_id": a.review_id,
        "product_id": a.product_id,
        "rating": a.rating,
        "text": a.text,
        "clean_text": a.clean_text,
        "tokens": json.dumps(a.tokens, ensure_ascii=False),
        "language": a.language,
        "created_at": a.created_at,
        "fetched_at": a.fetched_at,
        "sentiment_label": a.sentiment_label,
        "sentiment_score": a.sentiment_score,
        "keywords": json.dumps(a.keywords, ensure_ascii=False),
    }


def _row_to_analyzed(row: AnalyzedReviewRow) -> AnalyzedReview:
    return AnalyzedReview(
        platform=row.platform,  # type: ignore[arg-type]
        review_id=row.review_id,
        product_id=row.product_id,
        rating=row.rating,
        text=row.text,
        clean_text=row.clean_text,
        tokens=json.loads(row.tokens or "[]"),
        language=row.language,
        created_at=row.created_at,
        fetched_at=row.fetched_at,
        sentiment_label=row.sentiment_label,  # type: ignore[arg-type]
        sentiment_score=row.sentiment_score,
        keywords=json.loads(row.keywords or "[]"),
    )
