"""CRM provider clients."""

from __future__ import annotations

from .base import CrmProvider
from .hubspot import HubSpotProvider
from .pipedrive import PipedriveProvider
from .salesforce import SalesforceProvider

__all__ = ["CrmProvider", "HubSpotProvider", "PipedriveProvider", "SalesforceProvider"]
