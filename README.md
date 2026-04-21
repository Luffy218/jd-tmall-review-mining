# cn-review-pipeline

Scalable review scraping, NLP, and analytics pipeline for Chinese e-commerce
platforms (JD.com, Tmall). Modular layers you can run end-to-end in under a
minute on the bundled offline fixtures.

```
scraper  ->  processor  ->  analyzer  ->  storage  ->  dashboard / API
```

| Layer      | Tech                                                      |
|------------|-----------------------------------------------------------|
| Scraper    | `httpx` async, `tenacity` retries, `robotparser`, fake-UA |
| Processor  | `beautifulsoup4` + `lxml`, `jieba`, `langdetect`          |
| Analyzer   | rule-based lexicon + optional fine-tuned Chinese BERT     |
| Storage    | pluggable adapter — PostgreSQL (SQLAlchemy) or MongoDB    |
| Dashboard  | Streamlit + Plotly + wordcloud                            |
| API        | FastAPI                                                   |
| Orchestr.  | Celery + Redis                                            |
| CLI        | Typer (`crp ...`)                                         |

See [`docs/architecture.md`](docs/architecture.md) for the full diagram and
layer contracts.

---

## Legal / ToS

**JD.com and Tmall's Terms of Service prohibit automated scraping.** This
project ships in **offline fixture mode by default** (`CRP_OFFLINE_FIXTURES=1`)
so the full pipeline is runnable without hitting their servers. If you flip
that off:

* `AsyncFetcher` checks `robots.txt` before every request. Set
  `CRP_RESPECT_ROBOTS=0` to disable — but you are on your own for ToS/legal
  compliance in your jurisdiction.
* We do **not** ship anti-bot bypass techniques (residential-proxy rotation,
  CAPTCHA solving, token/cookie forgery). You can plug your own fetcher in by
  subclassing `AsyncFetcher`.
* The header rotation in `AsyncFetcher.DEFAULT_USER_AGENTS` is for politeness
  (varied traffic), not evasion.

Use this for research, coursework, or your own review stores. Do not point it
at sites whose ToS you haven't agreed to.

---

## Quick start (offline demo)

```bash
git clone https://github.com/<you>/cn-ecommerce-review-pipeline.git
cd cn-ecommerce-review-pipeline

python -m venv .venv && source .venv/bin/activate
pip install -e '.[dev]'          # lean install
# pip install -e '.[dev,ml]'     # adds torch + transformers for BERT sentiment

cp .env.example .env             # defaults to SQLite-compatible Postgres adapter + offline mode
export CRP_POSTGRES_DSN=sqlite:///data/demo.db

# End-to-end: scrape (fixtures) -> clean -> tokenise -> sentiment -> store
python scripts/load_fixtures.py

# Poke around
crp list-reviews --platform jd
crp dashboard                    # -> http://localhost:8501
crp api                          # -> http://localhost:8000/docs
```

The `scripts/load_fixtures.py` command walks both shipped fixtures (one JD
product, one Tmall product) through the whole pipeline so the dashboard has
data immediately.

---

## Full dev stack (Postgres + Mongo + Redis)

```bash
docker compose up -d postgres mongo redis
cp .env.example .env
pip install -e '.[dev]'

# Run a real scrape (still offline fixtures by default)
crp scrape jd 100012043978 --max-pages 2

# Or via the FastAPI + Celery path
celery -A cn_review_pipeline.tasks.celery_app:celery_app worker --loglevel=INFO &
crp api &
curl -X POST localhost:8000/scrape -H 'content-type: application/json' \
     -d '{"platform":"jd","product_id":"100012043978","max_pages":2}'
```

Switch the storage backend by flipping one env var:

```bash
export CRP_STORAGE_BACKEND=mongo
export CRP_MONGO_URI=mongodb://localhost:27017
```

---

## Configuration

All configuration is in `src/cn_review_pipeline/config.py` and driven by
`CRP_*` environment variables (see `.env.example`). The highlights:

| Variable                      | Default                       | Notes                                            |
|-------------------------------|-------------------------------|--------------------------------------------------|
| `CRP_STORAGE_BACKEND`         | `postgres`                    | `postgres` or `mongo`                            |
| `CRP_POSTGRES_DSN`            | `postgresql+psycopg://...`    | Any SQLAlchemy URL (SQLite works too)            |
| `CRP_OFFLINE_FIXTURES`        | `1`                           | Serve fixtures from `data/fixtures/`             |
| `CRP_RESPECT_ROBOTS`          | `1`                           | Enforce `robots.txt`                             |
| `CRP_REQUEST_DELAY_SECONDS`   | `2.0`                         | Per-host floor between requests                  |
| `CRP_MAX_CONCURRENCY`         | `2`                           | Async semaphore width                            |
| `CRP_SENTIMENT_BACKEND`       | `baseline`                    | `baseline` (rule-based) or `bert`                |
| `CRP_BERT_MODEL`              | `uer/roberta-base-...`        | Any HuggingFace Chinese sentiment model          |
| `CRP_CELERY_BROKER_URL`       | `redis://localhost:6379/0`    | Redis broker                                     |

---

## Scaling

Covered in [`docs/architecture.md`](docs/architecture.md#scaling-considerations):

* Horizontal scrape throughput via Celery workers (idempotent upserts).
* Per-host rate limit + concurrency cap in the fetcher.
* Pluggable BERT analyzer with batching hooks and rule-based fallback.
* Partition / TTL strategy for the `raw_reviews` table.
* Multilingual hook via `langdetect` per review.

---

## Tests

```bash
pytest                 # full suite, runs entirely on SQLite + offline fixtures
ruff check src tests
```

GitHub Actions runs the same matrix on Python 3.10 and 3.11.
