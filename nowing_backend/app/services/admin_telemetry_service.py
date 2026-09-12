"""Compat shim — admin telemetry split into ``app/services/admin_telemetry/``.

Keeps ``from app.services.admin_telemetry_service import AdminTelemetryService``
working for routes, health probes, and tests.
"""

from app.services.admin_telemetry import AdminTelemetryService

__all__ = ["AdminTelemetryService"]
