# Architecture

```
                    +----------------------------+
                    |        Dashboard           |
                    |     (Streamlit / Plotly)   |
                    +-------------+--------------+
                                  | reads
                                  v
+--------------+   +------------------------------+   +--------------+
|   FastAPI    |-->|        Storage adapter       |<--|  Celery/Redis|
|  /scrape     |   |  (Postgres | MongoDB)        |   |   workers    |
|  /reviews    |   |  idempotent upserts on       |   +------+-------+
|  /insights   |   |  (platform, review_id)       |          |
+------+-------+   +-------------+----------------+          |
       |                         ^                           |
       |                         |                           |
       | enqueue                 | writes                    |
       v                         |                           |
+--------------+      +----------+-----------+       +-------+--------+
|  scrape task |----> |   pipeline.py        |<------|  CLI (typer)   |
+--------------+      |  scraper -> processor|       +----------------+
                      |    -> analyzer       |
                      +----------+-----------+
                                 |
        +------------------------+-----------------------+
        |                        |                       |
        v                        v                       v
+----------------+     +-------------------+    +------------------+
|  Scraper       |     |  Processor        |    |  Analyzer        |
|  AsyncFetcher  |     |  clean + jieba    |    |  sentiment (rule |
|  JD / Tmall    |     |  + langdetect     |    |  or BERT)        |
|  robots.txt    |     |                   |    |  keywords (TFIDF,|
|  rate-limit    |     |                   |    |  TextRank, LDA)  |
|  fixtures mode |     |                   |    |  insights        |
+----------------+     +-------------------+    +------------------+
```

## Data flow

1. A **scrape job** (CLI, Celery, or FastAPI) calls `pipeline.run_full_pipeline`.
2. `AsyncFetcher` checks `robots.txt` (unless explicitly disabled), rotates the
   User-Agent from a small pool, applies per-host rate limits, and retries
   transient failures with exponential backoff. In offline mode it serves the
   HTTP response from `data/fixtures/` — useful for tests and demos.
3. The platform scraper parses the response into `RawReview` objects.
4. The processor cleans HTML/whitespace, UTF-8 normalises, detects language,
   and tokenises Chinese text with **jieba** minus a stopword list.
5. The analyzer computes sentiment (rule-based or fine-tuned BERT), TextRank
   keywords per review, and TF-IDF / LDA keywords at the corpus level.
6. The storage adapter (`PostgresReviewStore` or `MongoReviewStore`) upserts
   into three layers: `raw_reviews`, `processed_reviews`, `analyzed_reviews`.
   Upserts are idempotent on `(platform, review_id)`.
7. The Streamlit dashboard reads `analyzed_reviews` and renders sentiment
   distributions, word clouds, trends, rating correlation, and
   complaints/strengths.

## Why this shape

* **Layer boundaries are Pydantic models, not ORM rows.** Every layer consumes
  and emits domain models (`RawReview`, `ProcessedReview`, `AnalyzedReview`),
  so the storage backend is genuinely pluggable.
* **Incremental scraping is a single line.** `existing_review_ids()` is on the
  storage interface, so the pipeline can pre-filter before ever parsing.
* **Politeness is enforced in one place.** `AsyncFetcher` is the only thing
  that touches the network. Forgetting `robots.txt` or rate-limiting is not
  possible from a platform scraper.

## Scaling considerations

* **Horizontal scrape throughput**: add more Celery workers; they share the
  Redis broker and the same Postgres/Mongo. Because upserts are idempotent
  you can safely re-run tasks and over-enqueue.
* **Backpressure**: `AsyncFetcher` caps `max_concurrency` per worker and
  enforces `request_delay_seconds` per host. Tune via `CRP_*` env.
* **Storage growth**: `raw_reviews` is the heaviest table. Partition by
  `platform` + month, or TTL after N days, once `analyzed_reviews` has been
  extracted.
* **Analysis cost**: BERT inference dominates. Batch at the analyzer level
  (easy refactor: `analyze_reviews` already takes an iterable), pin to a
  single GPU worker queue, and keep rule-based as the fallback.
* **Multilingual**: `langdetect` tags each review; the analyzer branches
  naturally if you plug in a non-Chinese sentiment model for `en` etc.
