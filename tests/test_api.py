import asyncio

from fastapi.testclient import TestClient

from cn_review_pipeline.api.app import app
from cn_review_pipeline.pipeline import run_full_pipeline


def test_healthz():
    with TestClient(app) as client:
        resp = client.get("/healthz")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_reviews_and_insights_endpoints():
    asyncio.run(run_full_pipeline("jd", "100012043978", max_pages=2))
    with TestClient(app) as client:
        reviews = client.get("/reviews", params={"platform": "jd", "product_id": "100012043978"})
        assert reviews.status_code == 200
        assert len(reviews.json()) == 4

        insights = client.get("/insights/jd/100012043978")
        assert insights.status_code == 200
        body = insights.json()
        assert "strengths" in body and "complaints" in body
