"""Framework configuration package for Budget Tracker."""

from config.celery import app as celery_app

__all__ = ("celery_app",)
