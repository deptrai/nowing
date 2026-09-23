"""Google Drive indexer constants and type aliases."""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from app.db import SearchSourceConnectorType

ACCEPTED_DRIVE_CONNECTOR_TYPES = {
    SearchSourceConnectorType.GOOGLE_DRIVE_CONNECTOR,
    SearchSourceConnectorType.COMPOSIO_GOOGLE_DRIVE_CONNECTOR,
}

HeartbeatCallbackType = Callable[[int], Awaitable[None]]
HEARTBEAT_INTERVAL_SECONDS = 30
