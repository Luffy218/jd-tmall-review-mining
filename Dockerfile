FROM python:3.11-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        fonts-noto-cjk \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY pyproject.toml README.md ./
COPY src ./src
COPY data ./data
COPY scripts ./scripts

RUN pip install --upgrade pip \
    && pip install -e .

EXPOSE 8000 8501
CMD ["python", "-m", "cn_review_pipeline.cli", "--help"]
