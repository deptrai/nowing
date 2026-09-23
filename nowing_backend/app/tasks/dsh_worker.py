"""Backward-compatible shim for the refactored DSH worker package.

This module re-exports the public and internal API previously defined in the
monolithic ``app.tasks.dsh_worker`` module so that existing Celery bindings,
CLI entrypoints, and test monkeypatches continue to work.

New code should import directly from ``app.tasks.dsh_worker``.
"""

from __future__ import annotations

from app.tasks.dsh_worker.constants import (
    _DSH_CALL_TIMEOUT_SECONDS,
    _DSH_SYNC_TIMEOUT,
    _RENEW_LOCK_SCRIPT,
)
from app.tasks.dsh_worker.entrypoints import (
    _default_consumer_name,
    _validate_config,
    healthcheck,
    run_dsh_worker,
)
from app.tasks.dsh_worker.errors import (
    DshBillingError,
    DshNonRetryableError,
    DshNotFoundError,
    DshRetryableError,
    DshTransientError,
    DshValidationError,
    DshWorkerError,
)
from app.tasks.dsh_worker.executors import DeepLeadResearchExecutor
from app.tasks.dsh_worker.helpers import _checkpoint_update
from app.tasks.dsh_worker.rest_client import DshRestClient
from app.tasks.dsh_worker.worker import DshWorker

__all__ = [
    "_DSH_CALL_TIMEOUT_SECONDS",
    "_DSH_SYNC_TIMEOUT",
    "_RENEW_LOCK_SCRIPT",
    "DeepLeadResearchExecutor",
    "DshBillingError",
    "DshNonRetryableError",
    "DshNotFoundError",
    "DshRestClient",
    "DshRetryableError",
    "DshTransientError",
    "DshValidationError",
    "DshWorker",
    "DshWorkerError",
    "_checkpoint_update",
    "_default_consumer_name",
    "_validate_config",
    "healthcheck",
    "run_dsh_worker",
]
