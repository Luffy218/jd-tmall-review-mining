from datetime import datetime

from cn_review_pipeline.models import AnalyzedReview, ProcessedReview, RawReview
from cn_review_pipeline.storage import get_store


def _raw(review_id="r1", product_id="p1", text="很好") -> RawReview:
    return RawReview(
        platform="jd",
        product_id=product_id,
        review_id=review_id,
        rating=5,
        text=text,
        created_at=datetime(2024, 1, 1, 12, 0, 0),
        fetched_at=datetime(2024, 1, 2),
    )


def test_idempotent_upsert():
    store = get_store()
    store.init_schema()
    assert store.upsert_raw([_raw()]) == 1
    assert store.upsert_raw([_raw()]) == 1
    assert store.existing_review_ids("jd", "p1") == {"r1"}


def test_processed_and_analyzed_roundtrip():
    store = get_store()
    store.init_schema()
    r = _raw(review_id="r2")
    store.upsert_raw([r])
    p = ProcessedReview(
        platform=r.platform,
        product_id=r.product_id,
        review_id=r.review_id,
        rating=r.rating,
        text=r.text,
        clean_text=r.text,
        tokens=["很", "好"],
        language="zh-cn",
        created_at=r.created_at,
        fetched_at=r.fetched_at,
    )
    store.upsert_processed([p])
    a = AnalyzedReview(
        **p.model_dump(),
        sentiment_label="positive",
        sentiment_score=0.9,
        keywords=["好"],
    )
    store.upsert_analyzed([a])
    fetched = store.list_analyzed(platform="jd", product_id="p1")
    assert len(fetched) == 1
    assert fetched[0].sentiment_label == "positive"
    assert fetched[0].keywords == ["好"]
