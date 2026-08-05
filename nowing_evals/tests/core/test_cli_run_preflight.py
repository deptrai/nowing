"""``python -m nowing_evals run`` pre-auth hook (Story 3.14, D10).

A benchmark that declares ``validate_run_options`` (memory-recall's
``--backend-build-id`` requirement) must be rejected *before* ``load_config``/
``acquire_token`` ever run — otherwise a misconfigured run pays for config
resolution and a network round trip just to fail on a local, static check.
"""

from __future__ import annotations

import pytest

from nowing_evals.core import registry
from nowing_evals.core.cli import main
from nowing_evals.suites.memory.recall import MemoryRecallBenchmark


@pytest.fixture(autouse=True)
def _ensure_memory_suite_registered():
    """Auto-discovery may not have run yet in a narrow test invocation."""
    if ("memory", "recall") not in dict(registry.snapshot()):
        registry.register(MemoryRecallBenchmark())
    yield


def _explode(*_a, **_kw):
    raise AssertionError("must not be called before the pre-auth hook runs")


@pytest.mark.parametrize("backend_build_id_args", [[], ["--backend-build-id", "   "]])
def test_run_rejects_missing_or_blank_build_id_before_config_or_auth(
    tmp_env,
    monkeypatch,
    capsys,
    backend_build_id_args,  # noqa: ARG001
):
    """Neither ``load_config`` nor ``acquire_token`` may run for an invalid id."""
    monkeypatch.setattr("nowing_evals.core.cli.load_config", _explode)
    monkeypatch.setattr("nowing_evals.core.cli.acquire_token", _explode)

    exit_code = main(["run", "memory", "recall", *backend_build_id_args])

    assert exit_code == 2
    combined = capsys.readouterr().out
    assert "backend-build-id" in combined


def test_run_with_valid_build_id_proceeds_to_the_normal_auth_seam(
    tmp_env,
    capsys,  # noqa: ARG001
):
    """A non-blank id must clear the pre-auth hook and reach real credential
    resolution (which then fails on its own terms — no credentials configured
    in this hermetic env — proving the hook did not block a valid run)."""
    exit_code = main(["run", "memory", "recall", "--backend-build-id", "sha-abc123"])

    assert exit_code == 2
    combined = capsys.readouterr().out
    assert "No Nowing credentials configured" in combined


def test_run_catches_non_value_error_from_pre_auth_hook(
    tmp_env,
    monkeypatch,
    capsys,
):
    """C10: the pre-auth hook must catch any Exception, not just ValueError."""

    class BadHookBenchmark:
        suite = "demo-bad-hook"
        name = "bench"
        headline = False
        description = "pre-auth hook raises TypeError"
        requires_suite_setup = False

        def validate_run_options(self, **_opts):
            raise TypeError("build id must be a string")

        async def ingest(self, ctx, **opts):  # pragma: no cover - unused
            return None

        async def run(self, ctx, **opts):  # pragma: no cover - unreached
            raise NotImplementedError

        def add_run_args(self, parser):
            return None

        def report_section(self, artifacts):  # pragma: no cover - unused
            raise NotImplementedError

    monkeypatch.setattr("nowing_evals.core.cli.load_config", _explode)
    monkeypatch.setattr("nowing_evals.core.cli.acquire_token", _explode)

    registry.register(BadHookBenchmark())
    try:
        exit_code = main(["run", "demo-bad-hook", "bench"])
        assert exit_code == 2
        combined = capsys.readouterr().out
        assert "build id must be a string" in combined
    finally:
        registry.unregister("demo-bad-hook", "bench")


def test_run_without_validate_run_options_hook_is_unaffected(
    tmp_env,
    capsys,  # noqa: ARG001
):
    """A benchmark with no ``validate_run_options`` attribute (every suite
    besides memory-recall) must not be gated at all — the hook is optional."""

    class NoHookBenchmark:
        suite = "demo-no-hook"
        name = "bench"
        headline = False
        description = "no validate_run_options support"
        requires_suite_setup = False

        async def ingest(self, ctx, **opts):  # pragma: no cover - unused
            return None

        async def run(self, ctx, **opts):  # pragma: no cover - unreached: creds fail first
            raise NotImplementedError

        def add_run_args(self, parser):
            return None

        def report_section(self, artifacts):  # pragma: no cover - unused
            raise NotImplementedError

    registry.register(NoHookBenchmark())
    try:
        exit_code = main(["run", "demo-no-hook", "bench"])
        assert exit_code == 2
        combined = capsys.readouterr().out
        assert "No Nowing credentials configured" in combined
    finally:
        registry.unregister("demo-no-hook", "bench")
