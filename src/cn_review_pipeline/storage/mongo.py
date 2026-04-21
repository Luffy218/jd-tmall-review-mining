"""MongoDB adapter.

Three collections mirror the Postgres tables. We use a compound unique index
on ``(platform, review_id)`` to enforce idempotent upserts.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from pymongo import ASCENDING, MongoClient, UpdateOne

from ..models import AnalyzedReview, ProcessedReview, RawReview


class MongoReviewStore:
    def __init__(self, uri: str, db_name: str) -> None:
        self._client: MongoClient = MongoClient(uri)
        self._db = self._client[db_name]

    @property
    def raw(self):
        return self._db["raw_reviews"]

    @property
    def processed(self):
        return self._db["processed_reviews"]

    @property
    def analyzed(self):
        return self._db["analyzed_reviews"]

    def init_schema(self) -> None:
        for coll in (self.raw, self.processed, self.analyzed):
            coll.create_index(
                [("platform", ASCENDING), ("review_id", ASCENDING)], unique=True
            )
            coll.create_index([("product_id", ASCENDING)])

    def close(self) -> None:
        self._client.close()

    # ------------------------------------------------------------------

    def upsert_raw(self, items: Iterable[RawReview]) -> int:
        return self._bulk_upsert(self.raw, (i.model_dump(mode="python") for i in items))

    def upsert_processed(self, items: Iterable[ProcessedReview]) -> int:
        return self._bulk_upsert(
            self.processed, (i.model_dump(mode="python") for i in items)
        )

    def upsert_analyzed(self, items: Iterable[AnalyzedReview]) -> int:
        return self._bulk_upsert(
            self.analyzed, (i.model_dump(mode="python") for i in items)
        )

    def existing_review_ids(self, platform: str, product_id: str) -> set[str]:
        cursor = self.raw.find(
            {"platform": platform, "product_id": product_id},
            {"review_id": 1, "_id": 0},
        )
        return {doc["review_id"] for doc in cursor}

    def list_analyzed(
        self, platform: str | None = None, product_id: str | None = None
    ) -> list[AnalyzedReview]:
        query: dict[str, Any] = {}
        if platform:
            query["platform"] = platform
        if product_id:
            query["product_id"] = product_id
        docs = list(self.analyzed.find(query, {"_id": 0}))
        return [AnalyzedReview.model_validate(d) for d in docs]

    # ------------------------------------------------------------------

    @staticmethod
    def _bulk_upsert(collection, docs: Iterable[dict[str, Any]]) -> int:
        ops: list[UpdateOne] = []
        for d in docs:
            ops.append(
                UpdateOne(
                    {"platform": d["platform"], "review_id": d["review_id"]},
                    {"$set": d},
                    upsert=True,
                )
            )
        if not ops:
            return 0
        result = collection.bulk_write(ops, ordered=False)
        return (result.upserted_count or 0) + (result.modified_count or 0)
