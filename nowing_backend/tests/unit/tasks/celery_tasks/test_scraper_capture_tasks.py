"""Unit tests for scraper capture Celery task."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.tasks.celery_tasks.scraper_capture_tasks import _capture_session_impl


@pytest.mark.asyncio
async def test_capture_rejects_unsupported_platform():
    with pytest.raises(ValueError, match="Unsupported capture platform"):
        await _capture_session_impl("unknown")


@pytest.mark.asyncio
async def test_capture_rejects_invalid_cdp_url():
    with pytest.raises(ValueError, match="Invalid CDP URL"):
        await _capture_session_impl("batdongsan", cdp_url="not-a-ws-url")


@pytest.mark.asyncio
async def test_capture_starts_process_and_returns_success():
    mock_proc = AsyncMock()
    mock_proc.wait = AsyncMock(return_value=0)

    with patch("asyncio.create_subprocess_exec", return_value=mock_proc) as mock_exec:
        result = await _capture_session_impl("batdongsan")

    assert result["status"] == "success"
    assert result["returncode"] == 0
    assert result["platform"] == "batdongsan"
    assert "capture_id" in result

    args, _kwargs = mock_exec.call_args
    assert args[0] == sys.executable
    assert Path(args[1]).name == "capture_batdongsan_session.py"
    assert "--auto" in args
    assert "--timeout" in args
    assert "--platform" in args
    assert "batdongsan" in args


@pytest.mark.asyncio
async def test_capture_passes_cdp_url():
    mock_proc = AsyncMock()
    mock_proc.wait = AsyncMock(return_value=0)

    with patch("asyncio.create_subprocess_exec", return_value=mock_proc) as mock_exec:
        await _capture_session_impl("batdongsan", cdp_url="ws://localhost:9222")

    args = mock_exec.call_args[0]
    assert "--cdp" in args
    assert "ws://localhost:9222" in args


@pytest.mark.asyncio
async def test_capture_handles_timeout():
    mock_proc = AsyncMock()
    mock_proc.wait = AsyncMock(side_effect=asyncio.sleep(10))
    mock_proc.kill = MagicMock()

    with (
        patch("asyncio.create_subprocess_exec", return_value=mock_proc),
        patch("asyncio.wait_for", side_effect=TimeoutError),
    ):
        result = await _capture_session_impl("batdongsan")

    assert result["status"] == "timeout"
    assert result["returncode"] is None
    assert result["platform"] == "batdongsan"
    mock_proc.kill.assert_called_once()
