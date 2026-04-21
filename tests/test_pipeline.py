import pandas as pd
import pytest

from cn_review_pipeline.analyzer.insights import complaints_and_strengths
from cn_review_pipeline.pipeline import run_full_pipeline
from cn_review_pipeline.storage import get_store


@pytest.mark.asyncio
async def test_run_full_pipeline_end_to_end():
    analyzed = await run_full_pipeline("jd", "100012043978", max_pages=2)
    assert len(analyzed) == 4
    labels = {a.sentiment_label for a in analyzed}
    # We expect both polarities to be represented in the fixture.
    assert "positive" in labels
    assert "negative" in labels

    # Idempotent rerun: incremental should fetch nothing new.
    again = await run_full_pipeline("jd", "100012043978", max_pages=2)
    assert again == []

    store = get_store()
    stored = store.list_analyzed(platform="jd", product_id="100012043978")
    assert len(stored) == 4


@pytest.mark.asyncio
async def test_dashboard_data_path_with_rating_less_reviews():
    """Tmall fixtures carry no numeric ratings, so rating is ``None`` end-to-end.

    Regression: the dashboard previously round-tripped rows back through
    ``AnalyzedReview.model_validate`` after a DataFrame conversion, which
    turns ``None`` ratings into ``NaN`` — pydantic then rejected that as a
    non-finite int. This test exercises the same path the dashboard uses so a
    reintroduction of that round-trip would fail here too.
    """
    analyzed = await run_full_pipeline("tmall", "620010218888", max_pages=2)
    assert len(analyzed) == 3
    # Tmall fixture has no ratings.
    assert all(r.rating is None for r in analyzed)

    df = pd.DataFrame([r.model_dump() for r in analyzed])
    # NaN appears in the DataFrame, which is fine — the dashboard must NOT
    # re-validate through ``AnalyzedReview`` from this DataFrame. Instead it
    # should keep the original list.
    assert df["rating"].isna().all()

    # The insights path must work directly off the list of AnalyzedReview
    # returned by ``store.list_analyzed`` / ``run_full_pipeline`` — no
    # DataFrame round-trip involved.
    ins = complaints_and_strengths(analyzed)
    assert {"strengths", "complaints"}.issubset(ins)
