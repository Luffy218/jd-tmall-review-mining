"""Typer CLI: scrape, process, analyze, and inspect reviews.

Examples:

    crp scrape jd 100012043978 --max-pages 2
    crp analyze --platform jd --product 100012043978
    crp dashboard
    crp api
"""

from __future__ import annotations

import asyncio

import typer

from .logging_setup import configure_logging, logger
from .pipeline import run_full_pipeline

app = typer.Typer(add_completion=False, help="Chinese e-commerce review pipeline CLI")


@app.callback()
def _main() -> None:
    configure_logging()


@app.command()
def scrape(
    platform: str = typer.Argument(..., help="jd | tmall"),
    product_id: str = typer.Argument(..., help="Platform product ID"),
    max_pages: int = typer.Option(5, help="Max review pages to fetch"),
    incremental: bool = typer.Option(True, help="Skip already-stored review_ids"),
) -> None:
    """Run the full scrape -> process -> analyze -> store pipeline."""
    analyzed = asyncio.run(
        run_full_pipeline(
            platform, product_id, max_pages=max_pages, incremental=incremental
        )
    )
    logger.info(f"Stored {len(analyzed)} analyzed reviews")


@app.command()
def list_reviews(
    platform: str = typer.Option(None),
    product_id: str = typer.Option(None),
    limit: int = typer.Option(20),
) -> None:
    """Print the first ``limit`` analyzed reviews from storage."""
    from .storage import get_store

    store = get_store()
    store.init_schema()
    rows = store.list_analyzed(platform=platform, product_id=product_id)[:limit]
    for r in rows:
        typer.echo(
            f"[{r.platform}/{r.product_id}/{r.review_id}] "
            f"{r.sentiment_label:>8} {r.sentiment_score:+.2f} | "
            f"{r.clean_text[:80]}"
        )


@app.command()
def dashboard(port: int = typer.Option(8501)) -> None:
    """Launch the Streamlit dashboard (wrapper around ``streamlit run``)."""
    import subprocess
    import sys
    from pathlib import Path

    dashboard_py = Path(__file__).parent / "dashboard" / "app.py"
    subprocess.run(
        [sys.executable, "-m", "streamlit", "run", str(dashboard_py), "--server.port", str(port)],
        check=False,
    )


@app.command()
def api(host: str = typer.Option("0.0.0.0"), port: int = typer.Option(8000)) -> None:
    """Launch the FastAPI microservice."""
    import uvicorn

    uvicorn.run("cn_review_pipeline.api.app:app", host=host, port=port, reload=False)


if __name__ == "__main__":
    app()
