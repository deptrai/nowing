"""CRM integration bounded context (Story 21.5)."""

from __future__ import annotations

from .service import CrmConnectionService, CrmSyncService

__all__ = ["CrmConnectionService", "CrmSyncService"]
