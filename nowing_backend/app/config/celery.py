"""Config domain: celery."""

from __future__ import annotations

import os

# Celery / Redis
# Redis (single endpoint for Celery broker, result backend, and app cache).
# Legacy CELERY_BROKER_URL / CELERY_RESULT_BACKEND / REDIS_APP_URL still
# override individually when you need to split Redis across instances.
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL", REDIS_URL)
CELERY_RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND", REDIS_URL)
CELERY_TASK_DEFAULT_QUEUE = os.getenv("CELERY_TASK_DEFAULT_QUEUE", "nowing")
REDIS_APP_URL = os.getenv("REDIS_APP_URL", CELERY_BROKER_URL)
CONNECTOR_INDEXING_LOCK_TTL_SECONDS = int(
    os.getenv("CONNECTOR_INDEXING_LOCK_TTL_SECONDS", str(8 * 60 * 60))
)

# Celery beat scheduling intervals (format: "<number><unit>", e.g. "2m", "1h")
SCHEDULE_CHECKER_INTERVAL = os.getenv("SCHEDULE_CHECKER_INTERVAL", "2m")
STRIPE_RECONCILIATION_INTERVAL = os.getenv("STRIPE_RECONCILIATION_INTERVAL", "10m")



__all__ = ['CELERY_BROKER_URL', 'CELERY_RESULT_BACKEND', 'CELERY_TASK_DEFAULT_QUEUE', 'CONNECTOR_INDEXING_LOCK_TTL_SECONDS', 'REDIS_APP_URL', 'REDIS_URL', 'SCHEDULE_CHECKER_INTERVAL', 'STRIPE_RECONCILIATION_INTERVAL']
