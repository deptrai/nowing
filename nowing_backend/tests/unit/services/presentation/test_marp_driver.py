"""Unit tests for Marp driver subprocess safety."""

from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.presentation.marp_driver import render_marp_html

pytestmark = pytest.mark.unit


@pytest.mark.asyncio
async def test_render_marp_html_validates_missing_input(tmp_path):
    missing = tmp_path / "missing.md"
    output = tmp_path / "out.html"

    ok, reason = await render_marp_html(missing, output)

    assert ok is False
    assert reason == "input_missing"


@pytest.mark.asyncio
async def test_render_marp_html_runs_marp_with_timeout_and_kills_on_timeout(tmp_path):
    md = tmp_path / "slides.md"
    md.write_text("---\n# Test\n", encoding="utf-8")
    output = tmp_path / "out.html"

    mock_proc = AsyncMock()
    mock_proc.returncode = 0
    mock_proc.communicate = AsyncMock(return_value=(b"", b""))

    with patch("shutil.which", return_value="/usr/bin/marp") as _mock_which, patch(
        "asyncio.create_subprocess_exec", return_value=mock_proc
    ) as mock_exec:
        ok, reason = await render_marp_html(md, output)

    assert ok is True
    assert reason is None
    args = mock_exec.call_args[0]
    assert args[0] == "/usr/bin/marp"
    assert Path(args[1]).name == "slides.md"
    assert Path(args[3]).name == "out.html"


@pytest.mark.asyncio
async def test_render_marp_html_rejects_missing_binary(tmp_path):
    md = tmp_path / "slides.md"
    md.write_text("---\n# Test\n", encoding="utf-8")
    output = tmp_path / "out.html"

    with patch("shutil.which", return_value=None):
        ok, reason = await render_marp_html(md, output)

    assert ok is False
    assert reason == "dependency_missing"


@pytest.mark.asyncio
async def test_render_marp_html_kills_and_returns_timeout(tmp_path):
    md = tmp_path / "slides.md"
    md.write_text("---\n# Test\n", encoding="utf-8")
    output = tmp_path / "out.html"

    mock_proc = AsyncMock()
    mock_proc.returncode = None
    # Simulate marp hanging until the wait_for timeout fires.
    mock_proc.communicate = AsyncMock(side_effect=asyncio.TimeoutError)
    mock_proc.kill = MagicMock()

    async def _wait_for(coro, timeout):
        await coro

    with (
        patch("shutil.which", return_value="/usr/bin/marp"),
        patch("asyncio.create_subprocess_exec", return_value=mock_proc),
        patch("asyncio.wait_for", side_effect=_wait_for),
    ):
        ok, reason = await render_marp_html(md, output, timeout=0.001)

    assert ok is False
    assert reason == "marp_timeout"

