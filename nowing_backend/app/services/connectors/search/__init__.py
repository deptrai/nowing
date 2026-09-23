"""Connector search service package."""

from .comms import CommsSearchMixin
from .core import ConnectorSearchCore
from .google import GoogleSearchMixin
from .productivity import ProductivitySearchMixin
from .storage import StorageSearchMixin
from .web import WebSearchMixin


class ConnectorSearchService(ConnectorSearchCore, WebSearchMixin, CommsSearchMixin, ProductivitySearchMixin, GoogleSearchMixin, StorageSearchMixin):
    """Combined connector search service."""
