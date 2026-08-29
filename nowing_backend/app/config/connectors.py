"""Config domain: connectors."""

from __future__ import annotations

import os

# Connector discovery cache TTL
CONNECTOR_DISCOVERY_TTL_SECONDS = float(
    os.getenv("NOWING_CONNECTOR_DISCOVERY_TTL_SECONDS", "30")
)



__all__ = ['CONNECTOR_DISCOVERY_TTL_SECONDS']
