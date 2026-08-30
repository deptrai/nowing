"""Smoke test for the latest Alembic head downgrade path.

Story 8-13 / Phase H: every PR must prove that ``alembic downgrade -1`` from
head and ``alembic upgrade head`` again succeed on the current schema. The test
spawns the Alembic CLI against the integration test database so it runs exactly
as it does in production and in CI.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

pytestmark = [pytest.mark.integration]


def _run_alembic(cwd: Path, database_url: str, *args: str) -> None:
    """Run ``alembic <args>`` in a subprocess with DATABASE_URL set."""
    env = {**os.environ, "DATABASE_URL": database_url}
    result = subprocess.run(
        [sys.executable, "-m", "alembic", *args],
        cwd=str(cwd),
        env=env,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise AssertionError(
            f"alembic {' '.join(args)} failed\nstdout:\n{result.stdout}\n"
            f"stderr:\n{result.stderr}"
        )


async def _current_revision(async_engine: AsyncEngine) -> str | None:
    async with async_engine.connect() as conn:
        result = await conn.execute(
            text("SELECT version_num FROM alembic_version")
        )
        return result.scalar_one_or_none()


async def test_latest_downgrade_and_upgrade_roundtrip(
    async_engine: AsyncEngine,
) -> None:
    """``downgrade -1`` from head and ``upgrade head`` must both succeed."""
    from tests.conftest import TEST_DATABASE_URL

    backend_dir = Path(__file__).resolve().parents[3]
    assert (backend_dir / "alembic.ini").exists()

    # Ensure the DB is at head to begin with.
    _run_alembic(backend_dir, TEST_DATABASE_URL, "upgrade", "head")

    before = await _current_revision(async_engine)
    assert before is not None, "expected a recorded revision at head"

    # Downgrade one step.
    _run_alembic(backend_dir, TEST_DATABASE_URL, "downgrade", "-1")

    after_downgrade = await _current_revision(async_engine)
    assert after_downgrade != before, "revision did not move after downgrade"

    # Upgrade back to head.
    _run_alembic(backend_dir, TEST_DATABASE_URL, "upgrade", "head")

    after_upgrade = await _current_revision(async_engine)
    assert after_upgrade == before, f"expected {before}, got {after_upgrade}"
