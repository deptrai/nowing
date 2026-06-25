"""Unit tests for Story 7.4 — _validate_chainlens_config() startup validation.

Strategy: patch `app.config.config` directly with a SimpleNamespace mock
instead of reloading modules (which triggers load_dotenv from .env file,
making monkeypatch.delenv ineffective for fields with .env defaults).
"""
import logging
import types

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_config(*, enabled: bool, url: str = "", key: str = "", ttl: int = 30):
    """Build a SimpleNamespace mimicking app.config.config for testing."""
    return types.SimpleNamespace(
        CHAINLENS_RESEARCH_ENABLED=enabled,
        CHAINLENS_RESEARCH_API_URL=url,
        CHAINLENS_RESEARCH_API_KEY=key,
        CHAINLENS_HEALTH_CACHE_TTL=ttl,
    )


def _capture_logs(validator_fn) -> list[logging.LogRecord]:
    """Run validator and return captured LogRecords from the app.app logger."""
    import app.app as _app_mod  # noqa: PLC0415

    records: list[logging.LogRecord] = []

    class _Capture(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:  # noqa: D102
            records.append(record)

    handler = _Capture()
    _app_mod.logger.addHandler(handler)
    _prev_level = _app_mod.logger.level
    _app_mod.logger.setLevel(logging.DEBUG)
    try:
        validator_fn()
    finally:
        _app_mod.logger.removeHandler(handler)
        _app_mod.logger.setLevel(_prev_level)

    return records


def _run_with_config(mock_cfg) -> list[logging.LogRecord]:
    """Patch app.config.config with mock_cfg, run validator, return records."""
    from unittest.mock import patch  # noqa: PLC0415
    import app.app as _app_mod  # noqa: PLC0415

    with patch("app.config.config", mock_cfg):
        return _capture_logs(_app_mod._validate_chainlens_config)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_disabled_logs_info_disabled():
    """AC #5: ENABLED=false → INFO log contains 'DISABLED', no WARNING."""
    cfg = _make_config(enabled=False)
    records = _run_with_config(cfg)

    assert any("DISABLED" in r.getMessage() for r in records), \
        f"Expected 'DISABLED' in log — got: {[r.getMessage() for r in records]}"
    assert not any(r.levelname == "WARNING" for r in records)


def test_enabled_full_config_logs_enabled():
    """AC #2: ENABLED=true + URL + KEY → INFO log contains 'ENABLED' and URL."""
    cfg = _make_config(
        enabled=True,
        url="https://api.example.com",
        key="test-key-abc",
    )
    records = _run_with_config(cfg)
    messages = [r.getMessage() for r in records]

    assert any("ENABLED" in m for m in messages), f"Expected 'ENABLED' — got: {messages}"
    assert any("https://api.example.com" in m for m in messages), \
        f"Expected URL in log — got: {messages}"
    assert not any(r.levelname == "WARNING" for r in records)


@pytest.mark.parametrize(
    "cfg_kwargs,expected_var",
    [
        ({"url": "https://api.example.com", "key": ""}, "CHAINLENS_RESEARCH_API_KEY"),
        ({"url": "", "key": "test-key-abc"}, "CHAINLENS_RESEARCH_API_URL"),
    ],
    ids=["missing_key", "missing_url"],
)
def test_enabled_single_missing_var_logs_warning(cfg_kwargs, expected_var):
    """AC #3/#4: ENABLED=true + one missing var → WARNING mentioning that var's name."""
    cfg = _make_config(enabled=True, **cfg_kwargs)
    records = _run_with_config(cfg)

    assert any(r.levelname == "WARNING" for r in records), \
        f"Expected WARNING — got levels: {[r.levelname for r in records]}"
    assert any(expected_var in r.getMessage() for r in records), \
        f"Expected {expected_var} mention in warning — got: {[r.getMessage() for r in records]}"


def test_disabled_with_missing_key_url_no_warning():
    """AC #5 edge: ENABLED=false + missing key/url → only INFO 'DISABLED', NO warning.

    When feature is disabled, absence of API key/URL is not a misconfiguration.
    """
    cfg = _make_config(enabled=False, url="", key="")
    records = _run_with_config(cfg)

    assert any("DISABLED" in r.getMessage() for r in records)
    assert not any(r.levelname == "WARNING" for r in records)


@pytest.mark.parametrize(
    "cfg_kwargs,expected_var",
    [
        ({"url": "   \n\t  ", "key": "real-key"}, "CHAINLENS_RESEARCH_API_URL"),
        ({"url": "https://api.example.com", "key": "   "}, "CHAINLENS_RESEARCH_API_KEY"),
    ],
    ids=["whitespace_url", "whitespace_key"],
)
def test_enabled_whitespace_only_var_treated_as_missing(cfg_kwargs, expected_var):
    """Edge case: whitespace-only URL or KEY must be treated as missing (not 'ENABLED')."""
    cfg = _make_config(enabled=True, **cfg_kwargs)
    records = _run_with_config(cfg)

    assert any(r.levelname == "WARNING" for r in records), \
        f"Whitespace-only {expected_var} must trigger missing-var warning"
    assert any(expected_var in r.getMessage() for r in records)


def test_enabled_missing_both_key_and_url_single_consolidated_warning():
    """D2: Both KEY+URL missing → exactly ONE consolidated WARNING line
    listing both vars (not N separate warnings).

    Operator gets a single alert per restart, easier to grep + page on.
    """
    cfg = _make_config(enabled=True, url="", key="")
    records = _run_with_config(cfg)

    warnings = [r for r in records if r.levelname == "WARNING"]
    assert len(warnings) == 1, \
        f"Expected exactly 1 consolidated warning, got {len(warnings)}: " \
        f"{[w.getMessage() for w in warnings]}"

    msg = warnings[0].getMessage()
    assert "CHAINLENS_RESEARCH_API_URL" in msg
    assert "CHAINLENS_RESEARCH_API_KEY" in msg
    # Plural form when both missing
    assert "are missing" in msg


def test_validator_never_raises_on_exception():
    """AC #8: validator wraps exceptions — lifespan must never crash.

    Patches app.config.config with a broken object whose property access raises.
    """
    from unittest.mock import patch  # noqa: PLC0415
    import app.app as _app_mod  # noqa: PLC0415

    class _BrokenConfig:
        @property
        def CHAINLENS_RESEARCH_ENABLED(self) -> bool:
            raise RuntimeError("config exploded")

    with patch("app.config.config", _BrokenConfig()):
        try:
            _app_mod._validate_chainlens_config()
        except Exception as exc:  # noqa: BLE001
            pytest.fail(f"Validator raised unexpectedly — must be graceful: {exc}")


def test_lifespan_calls_validate_chainlens_config():
    """AC #8: ensure `_validate_chainlens_config()` is wired into `lifespan()`.

    Source-level guard: scans the lifespan function body to ensure the
    validator call is present. Catches the regression where someone removes
    the call and all other tests still pass (since they invoke the helper
    directly, not through lifespan).
    """
    import inspect  # noqa: PLC0415
    import app.app as _app_mod  # noqa: PLC0415

    src = inspect.getsource(_app_mod.lifespan)
    assert "_validate_chainlens_config()" in src, (
        "lifespan() must call _validate_chainlens_config() — "
        "removing this call silently disables AC #2/#3/#4/#5 startup logging"
    )
