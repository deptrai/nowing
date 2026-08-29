"""Tests for deprecated-key warnings and back-compat in
``load_openrouter_integration_settings``.
"""

from __future__ import annotations

from pathlib import Path

import pytest

pytestmark = pytest.mark.unit


def _write_yaml(tmp_path: Path, body: str) -> Path:
    cfg_dir = tmp_path / "app" / "config"
    cfg_dir.mkdir(parents=True)
    cfg_path = cfg_dir / "global_llm_config.yaml"
    cfg_path.write_text(body, encoding="utf-8")
    return cfg_path


def _patch_base_dir(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    from app import config as config_module

    monkeypatch.setattr(config_module, "BASE_DIR", tmp_path)
    # Ensure the test's on-disk YAML is used; an injected env var would
    # otherwise take precedence and produce an empty config.
    monkeypatch.delenv("GLOBAL_LLM_CONFIG_B64", raising=False)


def test_legacy_billing_tier_emits_warning(monkeypatch, tmp_path, caplog):
    _write_yaml(
        tmp_path,
        """
openrouter_integration:
  enabled: true
  api_key: "sk-or-test"
  billing_tier: "premium"
""".lstrip(),
    )
    _patch_base_dir(monkeypatch, tmp_path)

    from app.config import load_openrouter_integration_settings

    settings = load_openrouter_integration_settings()
    assert settings is not None
    assert any("billing_tier is deprecated" in rec.message for rec in caplog.records)


def test_legacy_anonymous_enabled_back_compat(monkeypatch, tmp_path, caplog):
    _write_yaml(
        tmp_path,
        """
openrouter_integration:
  enabled: true
  api_key: "sk-or-test"
  anonymous_enabled: true
""".lstrip(),
    )
    _patch_base_dir(monkeypatch, tmp_path)

    from app.config import load_openrouter_integration_settings

    settings = load_openrouter_integration_settings()
    assert settings is not None
    assert settings["anonymous_enabled_paid"] is True
    assert settings["anonymous_enabled_free"] is True
    assert any("anonymous_enabled is" in rec.message for rec in caplog.records)
    assert any("deprecated" in rec.message for rec in caplog.records)


def test_new_keys_take_priority_over_legacy_back_compat(monkeypatch, tmp_path, capsys):
    """If both legacy and new keys are present, new keys win (setdefault)."""
    _write_yaml(
        tmp_path,
        """
openrouter_integration:
  enabled: true
  api_key: "sk-or-test"
  anonymous_enabled: true
  anonymous_enabled_paid: false
  anonymous_enabled_free: false
""".lstrip(),
    )
    _patch_base_dir(monkeypatch, tmp_path)

    from app.config import load_openrouter_integration_settings

    settings = load_openrouter_integration_settings()
    capsys.readouterr()
    assert settings is not None
    assert settings["anonymous_enabled_paid"] is False
    assert settings["anonymous_enabled_free"] is False


def test_disabled_integration_returns_none(monkeypatch, tmp_path):
    _write_yaml(
        tmp_path,
        """
openrouter_integration:
  enabled: false
  api_key: "sk-or-test"
""".lstrip(),
    )
    _patch_base_dir(monkeypatch, tmp_path)

    from app.config import load_openrouter_integration_settings

    assert load_openrouter_integration_settings() is None
