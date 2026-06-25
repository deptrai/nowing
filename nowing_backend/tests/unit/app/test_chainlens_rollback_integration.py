"""
Story 7.4 — Task 5: Integration rollback flow test (AC #1, #2).

Tests the ENABLED → DISABLED rollback path:
  - When ENABLED=true + full config: is_available() returns True, tool uses Chainlens path
  - When ENABLED=false: is_available() returns False immediately (no network), tool returns fallback
  - Rollback is silent: no error log, no UI error message (FR25)

NOTE: ChainlensResearchService imports `config` at module level:
    from app.config import config
We must patch "app.services.chainlens_research_service.config" (not "app.config.config")
to correctly override the module-level binding.
"""
import types
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


# ─── helpers ──────────────────────────────────────────────────────────────────

def _make_config(*, enabled: bool, url: str = "", key: str = "", ttl: int = 30):
    return types.SimpleNamespace(
        CHAINLENS_RESEARCH_ENABLED=enabled,
        CHAINLENS_RESEARCH_API_URL=url,
        CHAINLENS_RESEARCH_API_KEY=key,
        CHAINLENS_HEALTH_CACHE_TTL=ttl,
    )


def _reset_health_cache():
    """Reset ChainlensResearchService._health_cache to force re-evaluation."""
    from app.services.chainlens_research_service import ChainlensResearchService
    ChainlensResearchService._health_cache = (False, 0.0)
    ChainlensResearchService._error_cooldown_until = 0.0


@pytest.fixture(autouse=True)
def _isolate_chainlens_service_state():
    """Reset shared class state before/after EVERY test in this module.

    ChainlensResearchService caches `_health_cache` and `_error_cooldown_until`
    at class level — leaks between tests can cause false positives (e.g., a
    cooldown set by an earlier test makes is_available() return False not
    because of ENABLED=false but because of cooldown).
    """
    _reset_health_cache()
    yield
    _reset_health_cache()


def _make_mock_http_200():
    """Return an AsyncMock httpx client that responds 200 to .get()."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_http = AsyncMock()
    mock_http.get = AsyncMock(return_value=mock_response)
    mock_http.__aenter__ = AsyncMock(return_value=mock_http)
    mock_http.__aexit__ = AsyncMock(return_value=False)
    return mock_http


# ─── AC #1: ENABLED=false → is_available() = False, no network call ──────────

@pytest.mark.asyncio
async def test_rollback_disabled_is_available_false_no_network():
    """AC #1: With ENABLED=false, is_available() returns False immediately.

    No HTTP request should be made — purely config-based short-circuit.
    """
    from app.services.chainlens_research_service import ChainlensResearchService
    mock_cfg = _make_config(enabled=False)

    with patch("app.services.chainlens_research_service.config", mock_cfg):
        with patch("httpx.AsyncClient") as mock_client_cls:
            result = await ChainlensResearchService.is_available()

    assert result is False
    mock_client_cls.assert_not_called()


# ─── AC #2: ENABLED=true + full config → is_available() = True (mock network) ─

@pytest.mark.asyncio
async def test_enabled_full_config_is_available_true():
    """AC #2: With ENABLED=true + URL + KEY, is_available() returns True
    when health endpoint responds 200.
    """
    from app.services.chainlens_research_service import ChainlensResearchService
    mock_cfg = _make_config(
        enabled=True,
        url="https://api.chainlens.example.com",
        key="test-key-abc",
    )

    with patch("app.services.chainlens_research_service.config", mock_cfg):
        with patch("httpx.AsyncClient", return_value=_make_mock_http_200()):
            result = await ChainlensResearchService.is_available()

    assert result is True


# ─── Rollback flow: ENABLED → DISABLED ────────────────────────────────────────

@pytest.mark.asyncio
async def test_rollback_flow_enabled_then_disabled():
    """AC #1 + #2: Simulates the rollback scenario.

    Phase 1: ENABLED=true — Chainlens path available
    Phase 2: ENABLED=false (rollback) — fallback path, no error
    """
    from app.services.chainlens_research_service import ChainlensResearchService

    # ── Phase 1: ENABLED ────────────────────────────────────────────────────
    enabled_cfg = _make_config(
        enabled=True,
        url="https://api.chainlens.example.com",
        key="test-key-abc",
    )

    with patch("app.services.chainlens_research_service.config", enabled_cfg):
        with patch("httpx.AsyncClient", return_value=_make_mock_http_200()):
            is_avail_phase1 = await ChainlensResearchService.is_available()

    assert is_avail_phase1 is True, "Phase 1: should be available"

    # Reset cache between phases (phase 1 cached True; without reset phase 2
    # would hit the cache and return True even though ENABLED=false).
    _reset_health_cache()

    # ── Phase 2: Rollback (ENABLED=false) ───────────────────────────────────
    disabled_cfg = _make_config(enabled=False)

    with patch("app.services.chainlens_research_service.config", disabled_cfg):
        with patch("httpx.AsyncClient") as mock_client_cls:
            is_avail_phase2 = await ChainlensResearchService.is_available()

    assert is_avail_phase2 is False, "Phase 2: should be unavailable after rollback"
    mock_client_cls.assert_not_called()


# ─── AC #1: research() raises ChainlensUnavailableError when ENABLED=false ───

@pytest.mark.asyncio
async def test_research_raises_unavailable_when_disabled():
    """AC #1: ChainlensResearchService.research() raises ChainlensUnavailableError
    when is_available() = False (ENABLED=false).

    The LangGraph tool catches this and returns {"status": "fallback"}.
    This test verifies the service contract — not the tool wrapper.
    """
    from app.services.chainlens_research_service import (
        ChainlensResearchService,
        ChainlensUnavailableError,
    )
    disabled_cfg = _make_config(enabled=False)

    with patch("app.services.chainlens_research_service.config", disabled_cfg):
        with pytest.raises(ChainlensUnavailableError):
            await ChainlensResearchService.research("test query")


# ─── FR25: startup log doesn't raise / doesn't propagate to FE ───────────────

def test_validate_chainlens_config_silent_on_disabled(caplog):
    """FR25: Startup validation never raises, no error-level log for disabled state."""
    import logging
    import app.app as _app_mod

    records = []

    class _Capture(logging.Handler):
        def emit(self, record):
            records.append(record)

    handler = _Capture()
    _app_mod.logger.addHandler(handler)
    _app_mod.logger.setLevel(logging.DEBUG)

    disabled_cfg = _make_config(enabled=False)
    try:
        with patch("app.config.config", disabled_cfg):
            _app_mod._validate_chainlens_config()
    except Exception as exc:
        pytest.fail(f"Validator raised exception (would reach lifespan): {exc}")
    finally:
        _app_mod.logger.removeHandler(handler)

    assert any("DISABLED" in r.getMessage() for r in records)
    assert not any(r.levelno >= logging.ERROR for r in records)
