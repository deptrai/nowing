"""TTL cache and ORM invalidation listeners for connector discovery."""

from __future__ import annotations

import logging
import time
from threading import Lock

from app.config import config
from app.db import SearchSourceConnectorType

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Connector / document-type discovery TTL cache (Phase 1.4)
# ---------------------------------------------------------------------------
#
# Both ``get_available_connectors`` and ``get_available_document_types`` are
# called on EVERY chat turn from ``create_nowing_deep_agent``. Each query
# hits Postgres and contributes to per-turn agent build latency. Their
# results change infrequently — only when the user adds/edits/removes a
# connector, or when an indexer commits a new document type. A short TTL
# cache (default 30s, env-tunable) collapses N concurrent calls into one
# DB roundtrip with bounded staleness.
#
# Invalidation: connector mutation routes (create / update / delete) call
# ``invalidate_connector_discovery_cache(workspace_id)`` to clear the
# entry for the affected space. Multi-replica deployments still pay one
# DB roundtrip per replica per TTL window, which is fine — staleness is
# bounded and the alternative (cross-replica fanout) is not worth the
# coupling here.

_DISCOVERY_TTL_SECONDS: float = config.CONNECTOR_DISCOVERY_TTL_SECONDS

# Per-workspace caches. Keyed by ``workspace_id``; value is
# ``(expires_at_monotonic, payload)``. Plain dicts protected by a lock —
# read-mostly workload, sub-microsecond contention.
_connectors_cache: dict[int, tuple[float, list[SearchSourceConnectorType]]] = {}
_doc_types_cache: dict[int, tuple[float, list[str]]] = {}
_cache_lock = Lock()


def _get_cached_connectors(
    workspace_id: int,
) -> list[SearchSourceConnectorType] | None:
    if _DISCOVERY_TTL_SECONDS <= 0:
        return None
    with _cache_lock:
        entry = _connectors_cache.get(workspace_id)
        if entry is None:
            return None
        expires_at, payload = entry
        if time.monotonic() >= expires_at:
            _connectors_cache.pop(workspace_id, None)
            return None
        return payload


def _set_cached_connectors(
    workspace_id: int, payload: list[SearchSourceConnectorType]
) -> None:
    if _DISCOVERY_TTL_SECONDS <= 0:
        return
    expires_at = time.monotonic() + _DISCOVERY_TTL_SECONDS
    with _cache_lock:
        _connectors_cache[workspace_id] = (expires_at, list(payload))


def _get_cached_doc_types(workspace_id: int) -> list[str] | None:
    if _DISCOVERY_TTL_SECONDS <= 0:
        return None
    with _cache_lock:
        entry = _doc_types_cache.get(workspace_id)
        if entry is None:
            return None
        expires_at, payload = entry
        if time.monotonic() >= expires_at:
            _doc_types_cache.pop(workspace_id, None)
            return None
        return payload


def _set_cached_doc_types(workspace_id: int, payload: list[str]) -> None:
    if _DISCOVERY_TTL_SECONDS <= 0:
        return
    expires_at = time.monotonic() + _DISCOVERY_TTL_SECONDS
    with _cache_lock:
        _doc_types_cache[workspace_id] = (expires_at, list(payload))


def invalidate_connector_discovery_cache(workspace_id: int | None = None) -> None:
    """Drop cached discovery results for ``workspace_id`` (or all spaces).

    Connector CRUD routes / indexer pipelines call this when they mutate
    the rows backing :func:`ConnectorService.get_available_connectors` /
    :func:`get_available_document_types`. ``None`` clears every space —
    useful in tests and on bulk imports.
    """
    with _cache_lock:
        if workspace_id is None:
            _connectors_cache.clear()
            _doc_types_cache.clear()
        else:
            _connectors_cache.pop(workspace_id, None)
            _doc_types_cache.pop(workspace_id, None)


def _invalidate_connectors_only(workspace_id: int | None = None) -> None:
    with _cache_lock:
        if workspace_id is None:
            _connectors_cache.clear()
        else:
            _connectors_cache.pop(workspace_id, None)


def _invalidate_doc_types_only(workspace_id: int | None = None) -> None:
    with _cache_lock:
        if workspace_id is None:
            _doc_types_cache.clear()
        else:
            _doc_types_cache.pop(workspace_id, None)


def _register_invalidation_listeners() -> None:
    """Wire SQLAlchemy ORM events so cache stays consistent automatically.

    Listening on ``after_insert`` / ``after_update`` / ``after_delete``
    means every successful INSERT/UPDATE/DELETE that goes through the ORM
    invalidates the affected workspace's cached discovery payload —
    no need to sprinkle ``invalidate_*`` calls across 30+ connector
    routes. Bulk operations that bypass the ORM (e.g.
    ``session.execute(insert(...))`` without a mapped object) still need
    explicit invalidation; document indexers already commit through the
    ORM so document-type discovery is covered.
    """
    from sqlalchemy import event

    # Imported here (not at module top) to avoid a circular import:
    # app.services.connector_service is itself imported from app.db's
    # ecosystem indirectly via several CRUD modules.
    from app.db import Document, SearchSourceConnector

    def _connector_changed(_mapper, _connection, target) -> None:
        sid = getattr(target, "workspace_id", None)
        if sid is not None:
            _invalidate_connectors_only(int(sid))

    def _document_changed(_mapper, _connection, target) -> None:
        sid = getattr(target, "workspace_id", None)
        if sid is not None:
            _invalidate_doc_types_only(int(sid))

    for evt in ("after_insert", "after_update", "after_delete"):
        event.listen(SearchSourceConnector, evt, _connector_changed)
        event.listen(Document, evt, _document_changed)


try:
    _register_invalidation_listeners()
except Exception:  # pragma: no cover - defensive; never block module import
    import logging as _logging

    _logging.getLogger(__name__).exception(
        "Failed to register connector discovery cache invalidation listeners; "
        "stale cache risk: explicit invalidate_connector_discovery_cache calls "
        "may be required."
    )
