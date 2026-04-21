.PHONY: install dev lint fmt test demo api dashboard worker

install:
	pip install -e '.[dev]'

lint:
	ruff check src tests

fmt:
	ruff format src tests

test:
	pytest -q

demo:
	CRP_OFFLINE_FIXTURES=1 CRP_STORAGE_BACKEND=postgres \
	CRP_POSTGRES_DSN=sqlite:///data/demo.db \
	python scripts/load_fixtures.py

api:
	uvicorn cn_review_pipeline.api.app:app --reload --port 8000

dashboard:
	streamlit run src/cn_review_pipeline/dashboard/app.py --server.port 8501

worker:
	celery -A cn_review_pipeline.tasks.celery_app:celery_app worker --loglevel=INFO
