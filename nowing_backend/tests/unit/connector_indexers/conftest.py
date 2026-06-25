"""Pre-register the connector_indexers package to bypass a circular import
in its ``__init__.py`` (airtable_indexer -> routes -> connector_indexers).

This lets tests import individual indexer modules (e.g.
``google_drive_indexer``) without triggering the full package init.
"""

import sys
import types
from pathlib import Path

_BACKEND = Path(__file__).resolve().parents[3]


def _stub_package(dotted: str, fs_dir: Path) -> None:
    if dotted not in sys.modules:
        mod = types.ModuleType(dotted)
        mod.__path__ = [str(fs_dir)]
        mod.__package__ = dotted
        sys.modules[dotted] = mod

    parts = dotted.split(".")
    if len(parts) > 1:
        parent_dotted = ".".join(parts[:-1])
        parent = sys.modules.get(parent_dotted)
        if parent is not None:
            setattr(parent, parts[-1], sys.modules[dotted])


_stub_package("app.tasks", _BACKEND / "app" / "tasks")
_stub_package(
    "app.tasks.connector_indexers",
    _BACKEND / "app" / "tasks" / "connector_indexers",
)


# ---------------------------------------------------------------------------
# Shared test constants — used by all connector indexer tests
# ---------------------------------------------------------------------------

CONNECTOR_USER_ID = "00000000-0000-0000-0000-000000000001"
CONNECTOR_ID = 42
CONNECTOR_SEARCH_SPACE_ID = 1


# ---------------------------------------------------------------------------
# Shared page-limit test helpers
# ---------------------------------------------------------------------------

from unittest.mock import AsyncMock, MagicMock

import pytest


class FakeUser:
    """Stands in for the User ORM model at the DB boundary."""

    def __init__(self, pages_used: int = 0, pages_limit: int = 100):
        self.pages_used = pages_used
        self.pages_limit = pages_limit


def make_page_limit_session(pages_used: int = 0, pages_limit: int = 100):
    """Return (session, fake_user) with execute() wired to return page-limit data."""
    fake_user = FakeUser(pages_used, pages_limit)
    session = AsyncMock()

    def _make_result(*_args, **_kwargs):
        result = MagicMock()
        result.first.return_value = (fake_user.pages_used, fake_user.pages_limit)
        result.unique.return_value.scalar_one_or_none.return_value = fake_user
        return result

    session.execute = AsyncMock(side_effect=_make_result)
    return session, fake_user
