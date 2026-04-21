import pytest

from cn_review_pipeline.scraper import AsyncFetcher, JDReviewScraper, TmallReviewScraper


@pytest.mark.asyncio
async def test_jd_scraper_offline_fixture():
    async with AsyncFetcher() as fetcher:
        scraper = JDReviewScraper(fetcher)
        reviews = await scraper.fetch_page("100012043978", page=0)
    assert len(reviews) == 4
    assert reviews[0].platform == "jd"
    assert reviews[0].rating == 5
    assert "屏幕" in reviews[0].text


@pytest.mark.asyncio
async def test_jd_scraper_fetch_all_terminates_on_empty():
    async with AsyncFetcher() as fetcher:
        scraper = JDReviewScraper(fetcher)
        reviews = await scraper.fetch_all("100012043978", max_pages=3)
    assert len(reviews) == 4  # page 0 has 4, page 1 is empty -> break


@pytest.mark.asyncio
async def test_tmall_scraper_offline_fixture():
    async with AsyncFetcher() as fetcher:
        scraper = TmallReviewScraper(fetcher)
        reviews = await scraper.fetch_page("620010218888", page=1)
    assert len(reviews) == 3
    assert reviews[0].platform == "tmall"
    assert "漂亮" in reviews[0].text
