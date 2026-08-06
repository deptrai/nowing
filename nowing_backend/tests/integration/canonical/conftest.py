"""Shared fixtures for canonical integration tests."""

from __future__ import annotations

import pytest

from app.canonical.services import unified_search_service
from app.config import config as app_config


@pytest.fixture(autouse=True)
def _patched_unified_search_embedding(monkeypatch):
    """Stub the unified search embedding call so tests stay fast and offline."""
    dim = app_config.embedding_model_instance.dimension
    dummy = [0.1] * dim
    monkeypatch.setattr(
        unified_search_service.config.embedding_model_instance,
        "embed",
        lambda _text: dummy,
    )
