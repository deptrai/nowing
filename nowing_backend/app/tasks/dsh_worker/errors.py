"""Error taxonomy for the DSH worker sidecar."""

from __future__ import annotations


class DshWorkerError(Exception):
    """Base class for DSH worker errors."""

    pass


class DshRetryableError(DshWorkerError):
    """A transient failure that should count against the retry budget."""

    pass


class DshNonRetryableError(DshWorkerError):
    """A failure that should move the mission straight to the DLQ."""

    pass


class DshBillingError(DshNonRetryableError):
    """The workspace cannot pay for the operation (402)."""

    pass


class DshNotFoundError(DshNonRetryableError):
    """A requested resource does not exist (404)."""

    pass


class DshValidationError(DshNonRetryableError):
    """The payload or state is invalid (422)."""

    pass


class DshTransientError(DshRetryableError):
    """A transient REST or upstream error (5xx, 429, timeout)."""

    pass
