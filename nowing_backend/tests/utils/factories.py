"""Shared data factory helpers for backend tests.

Provides builder functions that return domain objects with sensible defaults
and allow field-level overrides. Use these instead of hardcoding test data
in individual test files or conftest fixtures.

Usage:
    thread = make_thread(user_id=user.id, title="My thread")
    doc = make_connector_document(connector_id=connector.id)
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime


def make_user(**overrides) -> dict:
    """Return a dict of User field defaults suitable for ORM construction."""
    return {
        "id": uuid.uuid4(),
        "email": f"test-{uuid.uuid4().hex[:8]}@nowing.test",
        "hashed_password": "hashed",
        "is_active": True,
        "is_superuser": False,
        "is_verified": True,
        **overrides,
    }


def make_search_space(user_id: uuid.UUID, **overrides) -> dict:
    return {
        "id": uuid.uuid4(),
        "name": f"Space-{uuid.uuid4().hex[:6]}",
        "user_id": user_id,
        "created_at": datetime.now(UTC),
        **overrides,
    }


def make_connector_document(**overrides) -> dict:
    """Return field defaults for ConnectorDocument construction."""
    base_id = uuid.uuid4()
    return {
        "title": f"Doc {base_id.hex[:6]}",
        "source_markdown": "## Test\n\nContent.",
        "unique_id": f"uid-{base_id.hex}",
        "created_by_id": str(uuid.uuid4()),
        **overrides,
    }
