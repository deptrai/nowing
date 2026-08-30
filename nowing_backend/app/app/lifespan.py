"""App lifespan helpers."""
import asyncio
import gc
import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from slowapi.util import get_remote_address  # noqa: F401 — kept for reference

from app.agents.chat.runtime.checkpointer import (
    close_checkpointer,
    setup_checkpointer_tables,
)
from app.app.shared import _warn_if_build_id_unknown
from app.config import (
    config,
    initialize_image_gen_router,
    initialize_llm_router,
    initialize_openrouter_integration,
    initialize_pricing_registration,
    refresh_global_model_catalog,
)
from app.db import create_db_and_tables
from app.gateway.byo_long_poll import (
    start_byo_long_poll_supervisors,
    stop_byo_long_poll_supervisors,
)
from app.gateway.discord.intake import (
    start_discord_gateway_supervisor,
    stop_discord_gateway_supervisor,
)
from app.gateway.inbox_worker import (
    start_gateway_inbox_worker,
    stop_gateway_inbox_worker,
)
from app.observability.bootstrap import init_otel, shutdown_otel
from app.redis_client import get_redis_client
from app.services import scraper_rule_pubsub
from app.session_events import register_session_hooks
from app.utils.perf import log_system_snapshot

_error_logger = logging.getLogger("nowing.errors")

rate_limit_logger = logging.getLogger("nowing.rate_limit")


# ============================================================================
# Rate Limiting Configuration (SlowAPI + Redis)
# ============================================================================
# Uses the same Redis instance as Celery for zero additional infrastructure.
# Protects auth endpoints from brute force and user enumeration attacks.

# limiter is imported from app.rate_limiter (shared module to avoid circular imports)


def _enable_slow_callback_logging(threshold_sec: float = 0.5) -> None:
    """Monkey-patch the event loop to warn whenever a callback blocks longer than *threshold_sec*.

    This helps pinpoint synchronous code that freezes the entire FastAPI server.
    Only active when the PERF_DEBUG env var is set (to avoid overhead in production).
    """

    if not os.environ.get("PERF_DEBUG"):
        return

    _slow_log = logging.getLogger("nowing.perf.slow")
    _slow_log.setLevel(logging.WARNING)
    if not _slow_log.handlers:
        _h = logging.StreamHandler()
        _h.setFormatter(logging.Formatter("%(asctime)s [SLOW-CALLBACK] %(message)s"))
        _slow_log.addHandler(_h)
        _slow_log.propagate = False

    loop = asyncio.get_running_loop()
    loop.slow_callback_duration = threshold_sec  # type: ignore[attr-defined]
    loop.set_debug(True)
    _slow_log.warning(
        "Event-loop slow-callback detector ENABLED (threshold=%.1fs). "
        "Set PERF_DEBUG='' to disable.",
        threshold_sec,
    )


def _start_openrouter_background_refresh() -> None:
    """Start periodic OpenRouter model refresh if integration is enabled."""
    from app.services.openrouter_integration_service import OpenRouterIntegrationService

    if not OpenRouterIntegrationService.is_initialized():
        return
    settings = config.OPENROUTER_INTEGRATION_SETTINGS
    if settings:
        interval = settings.get("refresh_interval_hours", 24)
        OpenRouterIntegrationService.get_instance().start_background_refresh(interval)


def _stop_openrouter_background_refresh() -> None:
    """Cancel the periodic OpenRouter refresh task on shutdown."""
    from app.services.openrouter_integration_service import OpenRouterIntegrationService

    if OpenRouterIntegrationService.is_initialized():
        OpenRouterIntegrationService.get_instance().stop_background_refresh()


async def _warm_agent_jit_caches() -> None:
    """Pay the LangChain / LangGraph / Deepagents JIT cost at startup.

    Why
    ----
    A cold ``create_agent`` + ``StateGraph.compile()`` + Pydantic schema
    generation chain takes 1.5-2 seconds of pure CPU on first invocation
    inside any Python process: the graph compiler builds reducers,
    Pydantic v2 generates and JITs validator schemas, deepagents
    eagerly compiles its general-purpose subagent, etc. Subsequent
    compiles in the same process pay only ~50% of that cost (the lazy
    JIT bits are cached in module-level dicts).

    Doing one throwaway compile during ``lifespan`` startup pre-pays
    that cost so the *first real request* doesn't. We do NOT prime
    :mod:`agent_cache` because the cache key requires real
    ``thread_id`` / ``user_id`` / ``workspace_id`` / etc. — the
    throwaway agent is genuinely thrown away and immediately collected.

    Safety
    ------
    * No DB access. We construct a stub LLM (no real keys), pass an
      empty tools list, and pass ``checkpointer=None`` so we never
      touch Postgres.
    * Bounded by ``asyncio.wait_for`` so a hang here can never block
      worker startup. On any failure, we log + swallow — the worst
      case is the first real request pays the full cold cost (i.e.
      pre-warmup behaviour).
    """
    import time as _time

    logger = logging.getLogger(__name__)
    t0 = _time.perf_counter()
    try:
        from langchain.agents import create_agent
        from langchain.agents.middleware import (
            ModelCallLimitMiddleware,
            TodoListMiddleware,
            ToolCallLimitMiddleware,
        )
        from langchain_core.language_models.fake_chat_models import (
            FakeListChatModel,
        )
        from langchain_core.tools import tool

        from app.agents.chat.shared.context import NowingContextSchema

        # Minimal LLM stub. ``FakeListChatModel`` satisfies
        # ``BaseChatModel`` without any network or auth — perfect for
        # exercising the compile path without side effects.
        stub_llm = FakeListChatModel(responses=["warmup-response"])

        # Two trivial tools with arg + return schemas — exercises the
        # Pydantic v2 schema JIT path. Without at least one tool the
        # graph compile skips the tool-loop bytecode generation that
        # accounts for ~30-50% of cold compile cost.
        @tool
        def _warmup_tool_a(query: str, limit: int = 5) -> str:
            """Warmup tool A — never actually invoked."""
            return query[:limit]

        @tool
        def _warmup_tool_b(name: str, value: float | None = None) -> dict[str, object]:
            """Warmup tool B — never actually invoked."""
            return {"name": name, "value": value}

        # A handful of common middleware so the compile pre-pays the
        # ``AgentMiddleware`` resolver path. These instances never run
        # because the throwaway agent is immediately collected.
        # ``SubAgentMiddleware`` is the single heaviest line in cold
        # ``create_nowing_deep_agent`` (1.5-2s of CPU per call to
        # compile its general-purpose subagent's full inner graph),
        # so we include it here to make sure that compile path is JIT'd.
        warmup_middleware: list = [
            TodoListMiddleware(),
            ModelCallLimitMiddleware(
                thread_limit=120, run_limit=80, exit_behavior="end"
            ),
            ToolCallLimitMiddleware(
                thread_limit=300, run_limit=80, exit_behavior="continue"
            ),
        ]
        try:
            from deepagents import SubAgentMiddleware
            from deepagents.backends import StateBackend
            from deepagents.middleware.subagents import GENERAL_PURPOSE_SUBAGENT

            gp_warmup_spec = {  # type: ignore[var-annotated]
                **GENERAL_PURPOSE_SUBAGENT,
                "model": stub_llm,
                "tools": [_warmup_tool_a],
                "middleware": [TodoListMiddleware()],
            }
            warmup_middleware.append(
                SubAgentMiddleware(backend=StateBackend, subagents=[gp_warmup_spec])
            )
        except Exception:
            # Deepagents missing/incompatible — middleware-only warmup
            # still produces a useful (smaller) speedup.
            logger.debug("[startup] SubAgentMiddleware warmup skipped", exc_info=True)

        compiled = create_agent(
            stub_llm,
            tools=[_warmup_tool_a, _warmup_tool_b],
            system_prompt="You are a warmup stub.",
            middleware=warmup_middleware,
            context_schema=NowingContextSchema,
            checkpointer=None,
        )

        # Touch the compiled graph's stream_channels / nodes so any
        # remaining lazy schema work fires now instead of on first
        # real invocation.
        _ = list(getattr(compiled, "nodes", {}).keys())

        del compiled
        logger.info(
            "[startup] Agent JIT warmup completed in %.3fs",
            _time.perf_counter() - t0,
        )
    except Exception:
        logger.warning(
            "[startup] Agent JIT warmup failed in %.3fs (non-fatal — first "
            "real request will pay the full compile cost)",
            _time.perf_counter() - t0,
            exc_info=True,
        )


def initialize_event_loop_policy() -> None:
    """Set the default asyncio event loop policy at startup.

    Must be called explicitly during application lifespan or worker startup,
    not at module import time, to avoid side effects on import.
    """
    try:
        asyncio.set_event_loop_policy(asyncio.DefaultEventLoopPolicy())
    except RuntimeError:
        logger = logging.getLogger(__name__)
        logger.warning("Failed to set default event loop policy", exc_info=True)


async def _warm_embedding_model() -> None:
    """Pre-load/JIT the embedding model so the first KB search is fast.

    With lazy KB retrieval (OpenCode-style), the main agent no longer embeds
    on every turn — it calls the on-demand ``search_knowledge_base`` tool only
    when it needs KB content, and that tool's first ``embed_texts`` call in a
    fresh process pays the model's one-time load/JIT (local sentence-transformer
    warm or API client init). Doing one throwaway embed at startup moves that
    cost off the first real search.

    Safety: behind the embedding global lock (run in a worker thread), bounded
    by the caller's ``asyncio.wait_for``, and non-fatal — on any failure we log
    and swallow so the worst case is the first real search pays the cold cost.
    """
    import time as _time

    logger = logging.getLogger(__name__)
    t0 = _time.perf_counter()
    try:
        from app.utils.document_converters import embed_texts

        await asyncio.to_thread(embed_texts, ["warmup"])
        logger.info(
            "[startup] Embedding model warmup completed in %.3fs",
            _time.perf_counter() - t0,
        )
    except Exception:
        logger.warning(
            "[startup] Embedding model warmup failed in %.3fs (non-fatal — first "
            "KB search will pay the cold embed cost)",
            _time.perf_counter() - t0,
            exc_info=True,
        )


async def _sweep_stale_scraper_runs() -> None:
    """Fail scraper runs left ``running`` by a previous process (single-process).

    The async scraper door tracks in-flight runs as ``running``; a restart kills
    those background tasks, so any such row at boot is dead. Non-fatal.
    """
    logger = logging.getLogger(__name__)
    try:
        from app.capabilities.core.runs import fail_stale_running_runs
        from app.db import async_session_maker

        async with async_session_maker() as session:
            swept = await fail_stale_running_runs(session)
        if swept:
            logger.info(
                "[startup] Marked %d stale running scraper run(s) as error", swept
            )
    except Exception:
        logger.warning(
            "[startup] Stale scraper-run sweep failed (non-fatal)", exc_info=True
        )


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Tune GC: lower gen-2 threshold so long-lived garbage is collected
    # sooner (default 700/10/10 → 700/10/5). This reduces peak RSS
    # with minimal CPU overhead.
    gc.set_threshold(700, 10, 5)

    # Ensure the standard asyncio event loop policy is selected before any
    # other imports or warmups create a loop. Previously this ran as a
    # documents_routes module side effect.
    initialize_event_loop_policy()

    _enable_slow_callback_logging(threshold_sec=0.5)
    init_otel(app)
    _warn_if_build_id_unknown()
    await create_db_and_tables()
    from app.automations.services.playbook_seed_service import seed_system_playbooks
    from app.db import async_session_maker

    async with async_session_maker() as _seed_sess:
        await seed_system_playbooks(_seed_sess)
    await _sweep_stale_scraper_runs()
    await setup_checkpointer_tables()
    initialize_openrouter_integration()
    await refresh_global_model_catalog()
    _start_openrouter_background_refresh()
    initialize_pricing_registration()
    initialize_llm_router()
    initialize_image_gen_router()

    # Start scraper-rule Pub/Sub subscriber for live cache invalidation.
    try:
        redis = await get_redis_client()
        scraper_rule_pubsub.start_background_subscriber(redis)
    except Exception:
        logging.getLogger(__name__).warning(
            "[startup] Failed to start scraper rule subscriber (non-fatal)",
            exc_info=True,
        )

    # Phase 1.7 — JIT warmup. Bounded so a stuck warmup never delays
    # worker readiness. ``shield`` so Uvicorn cancelling startup
    # doesn't leave half-warmed Pydantic schemas in an inconsistent
    # state.
    try:
        await asyncio.wait_for(asyncio.shield(_warm_agent_jit_caches()), timeout=20)
    except (TimeoutError, Exception):  # pragma: no cover - defensive
        logging.getLogger(__name__).warning(
            "[startup] Agent JIT warmup hit timeout/error — skipping; "
            "first real request will pay the full compile cost."
        )

    # Phase 2 — embedding warmup so the first lazy ``search_knowledge_base``
    # call doesn't pay the cold embed-model load. Bounded + non-fatal.
    try:
        await asyncio.wait_for(asyncio.shield(_warm_embedding_model()), timeout=20)
    except (TimeoutError, Exception):  # pragma: no cover - defensive
        logging.getLogger(__name__).warning(
            "[startup] Embedding warmup hit timeout/error — skipping; "
            "first KB search will pay the cold embed cost."
        )

    register_session_hooks()
    log_system_snapshot("startup_complete")
    await start_gateway_inbox_worker()
    await start_byo_long_poll_supervisors()
    await start_discord_gateway_supervisor()

    try:
        yield
    finally:
        for task in list(scraper_rule_pubsub.SUBSCRIBER_TASKS):
            task.cancel()
        await stop_discord_gateway_supervisor()
        await stop_byo_long_poll_supervisors()
        await stop_gateway_inbox_worker()
        _stop_openrouter_background_refresh()
        await close_checkpointer()
        shutdown_otel()



