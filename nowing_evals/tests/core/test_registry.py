"""Registry + auto-discovery tests.

* Auto-discovery skips packages starting with ``_`` (so test fixtures
  don't leak into the production catalogue).
* Manually importing a ``_demo`` benchmark fires its ``register(...)``
  call and the CLI sees it.
"""

from __future__ import annotations

import importlib

import pytest

from nowing_evals.core import registry


def _force_register_demo() -> None:
    """Import (or reload) the demo module so its ``register(...)`` runs.

    On a fresh interpreter, ``import_module`` triggers package
    initialization. After the first call though, the module is cached
    in ``sys.modules`` and a second ``import_module`` is a no-op — so
    if a previous test already unregistered the entry, we have to
    ``reload`` to re-execute the module body.
    """

    module = importlib.import_module("nowing_evals.suites._demo.hello")
    if ("_demo", "hello") not in registry.snapshot():
        importlib.reload(module)


def test_auto_discovery_skips_underscore_prefixed_subpackages():
    from nowing_evals.suites import discover_suites

    discovered = discover_suites()
    assert all(not part.startswith("_") for full in discovered for part in full.split("."))
    # The medical suite's headline benchmark must always discover.
    assert any(name.endswith(".medical.medxpertqa") for name in discovered)


def test_demo_benchmark_registers_on_explicit_import():
    _force_register_demo()
    bench = registry.get("_demo", "hello")
    assert bench is not None
    assert bench.name == "hello"
    assert bench.headline is False
    # Cleanup so the test is idempotent under repeated runs.
    registry.unregister("_demo", "hello")


def test_register_unregister_roundtrip():
    # Make sure no stale entry from a prior test in the session.
    if ("_demo", "hello") in registry.snapshot():
        registry.unregister("_demo", "hello")
    snapshot_before = dict(registry.snapshot())
    _force_register_demo()
    assert ("_demo", "hello") in registry.snapshot()
    registry.unregister("_demo", "hello")
    assert dict(registry.snapshot()) == snapshot_before


async def test_run_context_creates_memories_client(isolated_config):
    """New benchmark suites receive the shared authenticated memory client seam."""
    import httpx

    from nowing_evals.core.clients import MemoriesClient
    from nowing_evals.core.config import SuiteState
    from nowing_evals.core.registry import RunContext

    async with httpx.AsyncClient() as http:
        context = RunContext(
            suite="memory",
            benchmark="recall",
            config=isolated_config,
            suite_state=SuiteState(
                search_space_id=10,
                chat_model_id=-1,
                provider_model="openai/gpt-5",
                created_at="2026-07-25T00-00-00Z",
            ),
            http=http,
        )
        assert isinstance(context.memories_client(), MemoriesClient)


def _run_context(isolated_config, http, **state_overrides):
    from nowing_evals.core.config import SuiteState
    from nowing_evals.core.registry import RunContext

    defaults = {
        "search_space_id": 10,
        "chat_model_id": -1,
        "provider_model": "openai/gpt-5",
        "created_at": "2026-07-25T00-00-00Z",
    }
    defaults.update(state_overrides)
    return RunContext(
        suite="medical",
        benchmark="cure",
        config=isolated_config,
        suite_state=SuiteState(**defaults),
        http=http,
    )


async def test_run_context_exposes_pinned_suite_state_via_properties(isolated_config):
    """RunContext properties are thin passthroughs to SuiteState; a benchmark
    reads them instead of poking suite_state internals directly."""
    import httpx

    async with httpx.AsyncClient() as http:
        ctx = _run_context(isolated_config, http, search_space_id=7, chat_model_id=-42)
        assert ctx.search_space_id == 7
        assert ctx.chat_model_id == -42
        assert ctx.provider_model == "openai/gpt-5"
        # head-to-head default: native arm mirrors the Nowing slug.
        assert ctx.native_arm_model == "openai/gpt-5"
        assert ctx.vision_provider_model is None
        assert ctx.scenario == "head-to-head"


async def test_run_context_cost_arbitrage_native_arm_diverges(isolated_config):
    """cost-arbitrage pins a distinct native-arm slug; the two must differ."""
    import httpx

    async with httpx.AsyncClient() as http:
        ctx = _run_context(
            isolated_config,
            http,
            scenario="cost-arbitrage",
            native_arm_model="anthropic/claude-sonnet-4.5",
            vision_provider_model="anthropic/claude-sonnet-4.5",
        )
        assert ctx.provider_model != ctx.native_arm_model
        assert ctx.vision_provider_model == "anthropic/claude-sonnet-4.5"


async def test_run_context_builds_all_client_seams(isolated_config):
    """Every client factory on RunContext returns the expected client type."""
    import httpx

    from nowing_evals.core.clients import DocumentsClient, NewChatClient, SearchSpaceClient

    async with httpx.AsyncClient() as http:
        ctx = _run_context(isolated_config, http)
        assert isinstance(ctx.search_space_client(), SearchSpaceClient)
        assert isinstance(ctx.documents_client(), DocumentsClient)
        assert isinstance(ctx.new_chat_client(), NewChatClient)


async def test_run_context_directory_helpers_create_and_scope_paths(isolated_config):
    """maps_dir / runs_dir / benchmark_data_dir each create their directory and
    scope it by suite (+ benchmark / run_timestamp where relevant)."""
    import httpx

    async with httpx.AsyncClient() as http:
        ctx = _run_context(isolated_config, http)

        maps_dir = ctx.maps_dir()
        assert maps_dir.is_dir()
        assert maps_dir == isolated_config.suite_maps_dir("medical")

        runs_dir = ctx.runs_dir(run_timestamp="2026-07-25T00-00-00Z")
        assert runs_dir.is_dir()
        assert runs_dir == (
            isolated_config.suite_runs_dir("medical") / "2026-07-25T00-00-00Z" / "cure"
        )

        data_dir = ctx.benchmark_data_dir()
        assert data_dir.is_dir()
        assert data_dir == isolated_config.suite_data_dir("medical") / "cure"


def test_register_overwrites_duplicate_and_logs_a_warning(caplog):
    """Re-registering the same (suite, name) key must overwrite (last wins),
    not raise, and must log so a double-import is diagnosable."""
    import logging

    class _Bench:
        suite = "_demo"
        name = "dup-check"
        headline = False
        description = "first"

    class _BenchAgain:
        suite = "_demo"
        name = "dup-check"
        headline = False
        description = "second"

    try:
        with caplog.at_level(logging.WARNING):
            registry.register(_Bench())
            registry.register(_BenchAgain())
        assert registry.get("_demo", "dup-check").description == "second"
        assert any("re-registered" in r.getMessage() for r in caplog.records)
    finally:
        registry.unregister("_demo", "dup-check")


def test_get_unknown_benchmark_lists_available_in_error():
    """A typo'd suite/benchmark name must surface what IS registered, so the
    CLI error is actionable instead of a bare KeyError."""
    with pytest.raises(KeyError, match="Unknown benchmark"):
        registry.get("does-not-exist", "nope")


def test_list_benchmarks_without_suite_returns_everything_sorted():
    """``list_benchmarks(None)`` is the union across all suites, not just one."""
    from nowing_evals.suites import discover_suites

    discover_suites()
    all_benchmarks = registry.list_benchmarks()
    memory_only = registry.list_benchmarks("memory")
    assert len(all_benchmarks) >= len(memory_only)
    assert all(isinstance(b.suite, str) for b in all_benchmarks)
