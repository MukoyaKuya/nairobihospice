"""Config package initialization and Celery app exposure."""
from .celery import app as celery_app

__all__ = ('celery_app',)
