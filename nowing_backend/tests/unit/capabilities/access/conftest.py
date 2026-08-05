"""Shared fixtures for access unit tests.

The REST door unit tests use ``SimpleNamespace`` in place of an ``AsyncSession``.
Story 8.12 added ``workspace_limit_service.check_run_limit`` before the meter-gate,
which requires a real session. Stub it for unit tests; integration tests still use
a real session.
"""

import pytest

from app.services.workspace_limits import workspace_limit_service


@pytest.fixture(autouse=True)
def _stub_workspace_run_limit(monkeypatch):
    """Make workspace run-limit checks a no-op in unit tests."""

    async def _noop(*args, **kwargs):
        return None

    monkeypatch.setattr(
        workspace_limit_service,
        "check_run_limit",
        _noop,
    )
