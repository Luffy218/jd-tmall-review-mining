"""Celery application used by workers and the FastAPI service.

Run a worker with::

    celery -A cn_review_pipeline.tasks.celery_app:celery_app worker --loglevel=INFO

Tasks are declared in ``cn_review_pipeline.tasks.jobs`` so the Celery
autodiscover picks them up via this module import.
"""

from __future__ import annotations

from celery import Celery

from ..config import get_settings

settings = get_settings()

celery_app = Celery(
    "cn_review_pipeline",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=["cn_review_pipeline.tasks.jobs"],
)

celery_app.conf.update(
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,
    task_default_queue="crp",
    task_time_limit=600,
    task_soft_time_limit=540,
)
