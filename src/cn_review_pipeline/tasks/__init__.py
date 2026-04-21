from .celery_app import celery_app
from .jobs import scrape_product_task

__all__ = ["celery_app", "scrape_product_task"]
