import pytest

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
