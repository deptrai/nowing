"""Shared embedding-vector validation (Story 3.14, D6).

Single source of truth for turning a raw value into a validated, contiguous
``np.float32`` 1-D vector — or a typed failure reason — used by the memory
repository (write path), hybrid search (query + stored-row path), and the
performance/audit tooling. Never index a provider or cardinality result
before checking it: see ``validate_single_embedding_result``.
"""

from __future__ import annotations

import numpy as np

#: Ordered per D6; kept in sync with the taxonomy documented in the story.
VECTOR_VALIDATION_REASONS = (
    "non_numeric",
    "invalid_shape",
    "invalid_dimension",
    "non_finite",
    "non_finite_norm",
    "zero_norm",
)

#: Caller cardinality reasons (D6): failures around the embedding provider
#: call itself, not the vector's own content.
CARDINALITY_VALIDATION_REASONS = ("provider_error", "invalid_count")


class VectorValidationError(ValueError):
    """A raw value failed embedding-vector validation (D6).

    ``reason`` is one of ``VECTOR_VALIDATION_REASONS`` or
    ``CARDINALITY_VALIDATION_REASONS``.
    """

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


def validate_embedding_vector(value: object, *, dimension: int) -> np.ndarray:
    """Validate ``value`` as an embedding vector of exactly ``dimension`` dims.

    Returns a contiguous ``np.float32`` 1-D array on success. Raises
    ``VectorValidationError`` on any failure, in the D6 taxonomy order:
    conversion failure -> ``non_numeric``; scalar/2-D/higher -> ``invalid_shape``;
    wrong length -> ``invalid_dimension``; NaN/Inf element -> ``non_finite``;
    non-finite norm -> ``non_finite_norm``; zero/negative norm -> ``zero_norm``.
    """
    try:
        array = np.asarray(value, dtype=np.float64)
    except (TypeError, ValueError, OverflowError) as exc:
        raise VectorValidationError("non_numeric") from exc

    if array.dtype == np.object_:
        raise VectorValidationError("non_numeric")
    if array.ndim != 1:
        raise VectorValidationError("invalid_shape")
    if array.shape[0] != dimension:
        raise VectorValidationError("invalid_dimension")
    if not np.all(np.isfinite(array)):
        raise VectorValidationError("non_finite")

    norm = np.linalg.norm(array)
    if not np.isfinite(norm):
        raise VectorValidationError("non_finite_norm")
    if norm <= 0:
        raise VectorValidationError("zero_norm")

    return np.ascontiguousarray(array, dtype=np.float32)


def validate_single_embedding_result(result: object) -> object:
    """Validate a batch-embedding provider result before indexing ``[0]``.

    ``embed_texts`` is always called with a single-item batch here, so the
    result must be a sequence of exactly one item. Raises
    ``VectorValidationError("invalid_count")`` otherwise — never index
    ``[0]`` before this check.
    """
    if not isinstance(result, (list, tuple)) or len(result) != 1:
        raise VectorValidationError("invalid_count")
    return result[0]
