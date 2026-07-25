"""CLI-level coverage for `python -m nowing_evals purge` (previously untested).

``_cmd_purge`` is the only mutating CLI verb with zero existing test coverage:
it resolves credentials, opens an authenticated client, and calls a
benchmark's optional ``purge`` hook. These tests exercise it end to end
through ``main()`` against a hermetic respx-mocked backend, rather than only
unit-testing ``run_purge`` (already covered in
``tests/suites/test_memory_recall_ingest.py``).
"""

from __future__ import annotations

import json

import httpx
import pytest
import respx

from nowing_evals.core import registry
from nowing_evals.core.cli import main
from nowing_evals.core.config import load_config
from nowing_evals.suites.memory.recall import MemoryRecallBenchmark

_BASE = "http://localhost:8000"


@pytest.fixture(autouse=True)
def _ensure_memory_suite_registered():
    """Auto-discovery may not have run yet in a narrow test invocation."""
    if ("memory", "recall") not in dict(registry.snapshot()):
        registry.register(MemoryRecallBenchmark())
    yield


def test_purge_cli_reports_unsupported_benchmark(tmp_env, monkeypatch, capsys):  # noqa: ARG001
    """A benchmark with no ``purge`` attribute must fail with a clear message,
    not an AttributeError bubbling out of ``main()``."""

    class NoPurgeBenchmark:
        suite = "demo-no-purge"
        name = "bench"
        headline = False
        description = "no purge support"

        async def ingest(self, ctx, **opts):  # pragma: no cover - unused
            return None

        async def run(self, ctx, **opts):  # pragma: no cover - unused
            raise NotImplementedError

        def add_run_args(self, parser):
            return None

        def report_section(self, artifacts):  # pragma: no cover - unused
            raise NotImplementedError

    registry.register(NoPurgeBenchmark())
    try:
        exit_code = main(["purge", "--suite", "demo-no-purge", "--benchmark", "bench"])
        assert exit_code == 2
        combined = capsys.readouterr().out.lower()
        assert "does not support purge" in combined
    finally:
        registry.unregister("demo-no-purge", "bench")


def test_purge_cli_requires_credentials(tmp_env, monkeypatch, capsys):  # noqa: ARG001
    """No NOWING_JWT / NOWING_USER_EMAIL+PASSWORD configured -> exit 2 with a
    credential error, not an unhandled exception."""
    monkeypatch.setenv("NOWING_EVAL_WORKSPACE_ID", "42")

    exit_code = main(["purge", "--suite", "memory", "--benchmark", "recall"])

    assert exit_code == 2
    combined = capsys.readouterr().out
    assert "No Nowing credentials configured" in combined


@respx.mock(base_url=_BASE)
def test_purge_cli_deletes_seeded_fixtures_end_to_end(respx_mock, tmp_env, monkeypatch, capsys):  # noqa: ARG001
    """The success path: JWT credential resolves, the benchmark's purge hook
    runs against a real (mocked) DELETE endpoint, and main() returns 0."""
    monkeypatch.setenv("NOWING_JWT", "test-jwt")
    monkeypatch.setenv("NOWING_EVAL_WORKSPACE_ID", "42")

    config = load_config()
    maps_dir = config.suite_maps_dir("memory")
    maps_dir.mkdir(parents=True, exist_ok=True)
    map_path = maps_dir / "memory_recall_corpus_map.w42.jsonl"
    rows = [
        {"memory_ref": "m1", "memory_id": 101, "workspace_id": 42},
        {"memory_ref": "m2", "memory_id": 102, "workspace_id": 42},
    ]
    map_path.write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8"
    )

    respx_mock.delete(f"{_BASE}/api/v1/memories/101").mock(return_value=httpx.Response(204))
    respx_mock.delete(f"{_BASE}/api/v1/memories/102").mock(return_value=httpx.Response(204))

    exit_code = main(
        ["purge", "--suite", "memory", "--benchmark", "recall", "--workspace-id", "42"]
    )

    assert exit_code == 0
    combined = capsys.readouterr().out
    assert "purge OK" in combined
    assert "2 deleted" in combined
    assert not map_path.exists()
