import asyncio
import copy
import json
import logging
import os
import shutil
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from chonkie import AutoEmbeddings, CodeChunker, RecursiveChunker
from dotenv import load_dotenv
from rerankers import Reranker

from app.config.embedding_settings import (
    build_embedding_kwargs,
    resolve_embedding_base_url,
)

# Get the base directory of the project
BASE_DIR = Path(__file__).resolve().parent.parent.parent

env_file = BASE_DIR / ".env"
load_dotenv(env_file)

os.environ.setdefault("OR_APP_NAME", "Nowing")
os.environ.setdefault("OR_SITE_URL", "https://nowing.com")

logger = logging.getLogger(__name__)


def _env_float(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        return float(raw)
    except (ValueError, OverflowError):
        logger.warning("Invalid %s=%r; using default %s", name, raw, default)
        return default


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        return int(raw)
    except (ValueError, OverflowError):
        logger.warning("Invalid %s=%r; using default %s", name, raw, default)
        return default


def _env_json(name: str, default: dict | None = None) -> dict | None:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        logger.warning("Invalid JSON in %s=%r; ignoring", name, raw)
        return default


def _env_choice(name: str, default: str, allowed: tuple[str, ...]) -> str:
    """Read a lower-cased enum-like env var, warning on unrecognised values.

    Without this, a typo in an enum-valued setting silently falls through to
    whatever branch the consumer treats as its else-case — e.g.
    ``MEMORY_AUTO_EXTRACT_BUDGET_WINDOW=monthly`` reading as a 1-day window,
    a 30x tighter cap than the operator intended. Mirrors ``_env_int``'s
    warn-and-default behaviour.
    """
    raw = os.getenv(name)
    if raw is None:
        return default
    value = raw.strip().lower()
    if value not in allowed:
        logger.warning(
            "Invalid %s=%r; expected one of %s; using default %r",
            name,
            raw,
            "/".join(allowed),
            default,
        )
        return default
    return value


@lru_cache(maxsize=8)
def _read_global_config_yaml(path_str: str) -> dict:
    """Read and parse ``global_llm_config.yaml`` once per resolved path.

    Cached so the seven ``load_*`` helpers (and their re-invocations during
    startup) don't re-open and re-parse the same file repeatedly. Keyed on the
    resolved path string so tests that monkeypatch ``BASE_DIR`` to a unique
    ``tmp_path`` still get a fresh parse. Callers MUST treat the returned dict
    as read-only and deep-copy any section they intend to mutate.
    """
    f = Path(path_str)
    if not f.exists():
        return {}
    try:
        with open(f, encoding="utf-8") as fh:
            return yaml.safe_load(fh) or {}
    except Exception as e:
        print(f"Warning: Failed to read global_llm_config.yaml: {e}")
        return {}


def _global_config_data() -> dict:
    """Return the parsed global config YAML for the current ``BASE_DIR``.

    ``BASE_DIR`` is read at call time (not bound at import) so a
    ``monkeypatch.setattr(config, "BASE_DIR", tmp_path)`` is honored.

    If ``GLOBAL_LLM_CONFIG_B64`` is set, it takes precedence over the local
    ``global_llm_config.yaml`` file. This matches the Docker entrypoint
    behaviour and lets local developers keep keys in ``.env`` instead of a
    gitignored file.
    """
    b64 = os.environ.get("GLOBAL_LLM_CONFIG_B64")
    if b64:
        import base64

        try:
            decoded = base64.b64decode(b64).decode("utf-8")
            return yaml.safe_load(decoded) or {}
        except Exception as e:
            print(f"Warning: Failed to decode GLOBAL_LLM_CONFIG_B64: {e}")

    path = BASE_DIR / "app" / "config" / "global_llm_config.yaml"
    return _read_global_config_yaml(str(path))


def is_ffmpeg_installed():
    """
    Check if ffmpeg is installed on the current system.

    Returns:
        bool: True if ffmpeg is installed, False otherwise.
    """
    return shutil.which("ffmpeg") is not None


def load_global_llm_configs():
    """
    Load global LLM configurations from YAML file.
    Falls back to example file if main file doesn't exist.

    Returns:
        list: List of global LLM config dictionaries, or empty list if file doesn't exist
    """
    data = _global_config_data()
    if not data:
        # No global configs available
        return []

    try:
        # Deep-copy so the in-place mutations below (setdefault, scoring
        # stamps) never leak into the cached YAML structure.
        configs = copy.deepcopy(data.get("global_llm_configs", []))

        # Lazy import keeps the `app.config` -> `app.services` edge one-way.
        from app.services.provider_capabilities import derive_supports_image_input

        seen_slugs: dict[str, int] = {}
        for cfg in configs:
            tier = str(cfg.get("tier_required", "free")).lower()
            default_billing = "premium" if tier == "pro" else tier or "free"
            cfg.setdefault("billing_tier", default_billing)
            cfg.setdefault("anonymous_enabled", False)
            cfg.setdefault("seo_enabled", False)
            # Capability flag: explicit YAML override always wins. When the
            # operator has not annotated the model, defer to LiteLLM's
            # authoritative model map (`supports_vision`) which already
            # knows GPT-5.x / GPT-4o / Claude 3.x / Gemini 2.x are
            # vision-capable. Unknown / unmapped models default-allow so
            # we don't lock the user out of a freshly added third-party
            # entry; the streaming-task safety net (driven by
            # `is_known_text_only_chat_model`) is the only place a False
            # actually blocks a request.
            if "supports_image_input" not in cfg:
                litellm_params = cfg.get("litellm_params") or {}
                base_model = (
                    litellm_params.get("base_model")
                    if isinstance(litellm_params, dict)
                    else None
                )
                cfg["supports_image_input"] = derive_supports_image_input(
                    provider=cfg.get("provider") or cfg.get("litellm_provider"),
                    model_name=cfg.get("model_name"),
                    base_model=base_model,
                    custom_provider=cfg.get("custom_provider"),
                )

            if cfg.get("seo_enabled") and cfg.get("seo_slug"):
                slug = cfg["seo_slug"]
                if slug in seen_slugs:
                    print(
                        f"Warning: Duplicate seo_slug '{slug}' in global LLM configs "
                        f"(ids {seen_slugs[slug]} and {cfg.get('id')})"
                    )
                else:
                    seen_slugs[slug] = cfg.get("id", 0)

        # Stamp Auto ranking metadata. YAML configs are always
        # Tier A — operator-curated, locked first when premium-eligible.
        # The OpenRouter refresh tick later re-stamps health for any cfg
        # whose provider == "openrouter" via _enrich_health.
        try:
            from app.services.quality_score import static_score_yaml

            for cfg in configs:
                cfg["auto_pin_tier"] = "A"
                static_q = static_score_yaml(cfg)
                cfg["quality_score_static"] = static_q
                cfg["quality_score"] = static_q
                cfg["quality_score_health"] = None
                # YAML cfgs whose provider is openrouter are also subject
                # to health gating against their own /endpoints data — a
                # hand-picked dead OR model is still dead. _enrich_health
                # re-stamps health_gated for them on the next refresh tick.
                cfg["health_gated"] = False
        except Exception as e:
            print(f"Warning: Failed to score global LLM configs: {e}")

        # Planner LLM is a singleton role. If an operator accidentally
        # marks multiple configs ``is_planner: true``, only the first one
        # is used at runtime — surface the others at startup so the
        # mistake is caught before traffic, not silently buried.
        planner_cfgs = [c for c in configs if c.get("is_planner") is True]
        if len(planner_cfgs) > 1:
            extra_ids = [c.get("id") for c in planner_cfgs[1:]]
            print(
                "Warning: Multiple global LLM configs marked is_planner=true "
                f"(ids {[c.get('id') for c in planner_cfgs]}); using id "
                f"{planner_cfgs[0].get('id')} and ignoring {extra_ids}"
            )

        return configs
    except Exception as e:
        print(f"Warning: Failed to load global LLM configs: {e}")
        return []


def load_router_settings():
    """
    Load router settings for Auto mode from YAML file.
    Falls back to default settings if not found.

    Returns:
        dict: Router settings dictionary
    """
    # Default router settings
    default_settings = {
        "routing_strategy": "usage-based-routing",
        "num_retries": 3,
        "allowed_fails": 3,
        "cooldown_time": 60,
    }

    data = _global_config_data()
    if not data:
        return default_settings

    try:
        settings = data.get("router_settings", {})
        # Merge with defaults
        return {**default_settings, **settings}
    except Exception as e:
        print(f"Warning: Failed to load router settings: {e}")
        return default_settings


def load_global_image_gen_configs():
    """
    Load global image generation configurations from YAML file.

    Returns:
        list: List of global image generation config dictionaries, or empty list
    """
    data = _global_config_data()
    if not data:
        return []

    try:
        configs = copy.deepcopy(data.get("global_image_generation_configs", []) or [])
        for cfg in configs:
            if isinstance(cfg, dict):
                tier = str(cfg.get("tier_required", "free")).lower()
                default_billing = "premium" if tier == "pro" else tier or "free"
                cfg.setdefault("billing_tier", default_billing)
        return configs
    except Exception as e:
        print(f"Warning: Failed to load global image generation configs: {e}")
        return []


def load_image_gen_router_settings():
    """
    Load router settings for image generation Auto mode from YAML file.

    Returns:
        dict: Router settings dictionary
    """
    default_settings = {
        "routing_strategy": "usage-based-routing",
        "num_retries": 3,
        "allowed_fails": 3,
        "cooldown_time": 60,
    }

    data = _global_config_data()
    if not data:
        return default_settings

    try:
        settings = data.get("image_generation_router_settings", {})
        return {**default_settings, **settings}
    except Exception as e:
        print(f"Warning: Failed to load image generation router settings: {e}")
        return default_settings


def load_openrouter_integration_settings() -> dict | None:
    """
    Load OpenRouter integration settings from the YAML config.

    Emits startup warnings for deprecated keys (``billing_tier``,
    ``anonymous_enabled``) and seeds their replacements for back-compat.

    Returns:
        dict with settings if present and enabled, None otherwise
    """
    data = _global_config_data()
    if not data:
        return None

    try:
        # Deep-copy so the setdefault back-compat seeding below never mutates
        # the cached YAML structure.
        settings = copy.deepcopy(data.get("openrouter_integration"))
        if not settings or not settings.get("enabled"):
            return None

        if "billing_tier" in settings:
            print(
                "Warning: openrouter_integration.billing_tier is deprecated; "
                "tier is now derived per model from OpenRouter data "
                "(':free' suffix or zero pricing). Remove this key."
            )

        if "anonymous_enabled" in settings:
            print(
                "Warning: openrouter_integration.anonymous_enabled is "
                "deprecated; use anonymous_enabled_paid and/or "
                "anonymous_enabled_free instead. Both new flags have been "
                "seeded from the legacy value for back-compat."
            )
            settings.setdefault("anonymous_enabled_paid", settings["anonymous_enabled"])
            settings.setdefault("anonymous_enabled_free", settings["anonymous_enabled"])

        # Image generation + vision LLM emission are opt-in (issue L).
        # OpenRouter's catalogue contains hundreds of image / vision
        # capable models; auto-injecting all of them into every
        # deployment would explode the model selector and surprise
        # operators upgrading from prior versions. Default to False so
        # admins must explicitly turn them on.
        settings.setdefault("image_generation_enabled", False)
        settings.setdefault("vision_enabled", False)

        return settings
    except Exception as e:
        print(f"Warning: Failed to load OpenRouter integration settings: {e}")
        return None


def initialize_openrouter_integration():
    """
    If enabled, fetch all OpenRouter models and append them to
    config.GLOBAL_LLM_CONFIGS as dynamic entries. Each model's ``billing_tier``
    is derived per-model from OpenRouter's API signals (``:free`` suffix or
    zero pricing), so free OpenRouter models correctly skip premium quota.

    Should be called BEFORE initialize_llm_router(). Dynamic entries are
    tagged ``router_pool_eligible=False`` so the LiteLLM Router pool (used
    by title-gen / sub-agent flows) remains scoped to curated YAML configs,
    while user-facing Auto-mode thread pinning still considers them.
    """
    settings = load_openrouter_integration_settings()
    if not settings:
        return

    try:
        from app.services.openrouter_integration_service import (
            OpenRouterIntegrationService,
        )

        service = OpenRouterIntegrationService.get_instance()
        new_configs = service.initialize(settings)

        if new_configs:
            config.GLOBAL_LLM_CONFIGS.extend(new_configs)
            free_count = sum(1 for c in new_configs if c.get("billing_tier") == "free")
            premium_count = sum(
                1 for c in new_configs if c.get("billing_tier") == "premium"
            )
            print(
                f"Info: OpenRouter integration added {len(new_configs)} models "
                f"(free={free_count}, premium={premium_count})"
            )
        else:
            print("Info: OpenRouter integration enabled but no models fetched")

        # Image generation emissions reuse the catalogue already cached by
        # ``service.initialize``
        # so we don't make additional network calls here.
        if settings.get("image_generation_enabled"):
            try:
                image_configs = service.get_image_generation_configs()
                if image_configs:
                    config.GLOBAL_IMAGE_GEN_CONFIGS.extend(image_configs)
                    print(
                        f"Info: OpenRouter integration added {len(image_configs)} "
                        f"image-generation models"
                    )
            except Exception as e:
                print(f"Warning: Failed to inject OpenRouter image-gen configs: {e}")

        # Global catalog refresh is intentionally deferred to the async
        # lifespan so DB-managed GLOBAL rows can be merged.
        pass
    except Exception as e:
        print(f"Warning: Failed to initialize OpenRouter integration: {e}")


def materialize_global_configs():
    from app.services.global_model_catalog import materialize_global_model_catalog

    return materialize_global_model_catalog(
        chat_configs=getattr(config, "GLOBAL_LLM_CONFIGS", []),
        image_configs=getattr(config, "GLOBAL_IMAGE_GEN_CONFIGS", []),
    )


_global_catalog_refresh_lock = asyncio.Lock()


async def refresh_global_model_catalog(
    session: Any | None = None,
    *,
    rebuild_routers: bool = False,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Rebuild the in-memory global catalog, including DB-managed rows.

    Uses a process-local lock to serialize concurrent refresh calls.  When
    ``rebuild_routers`` is True (post-admin-mutation), also re-register
    LiteLLM pricing and rebuild the LLM Router so the new global pool is
    visible to router-backed paths.
    """
    from app.services.global_model_catalog import (
        refresh_global_model_catalog as _service_refresh,
    )

    async with _global_catalog_refresh_lock:
        connections, models = await _service_refresh(session)

        if rebuild_routers:
            try:
                from app.services.pricing_registration import (
                    register_pricing_for_managed_global_models,
                    register_pricing_from_global_configs,
                )

                register_pricing_from_global_configs()
                register_pricing_for_managed_global_models()
            except Exception as exc:
                logger.exception("Pricing registration failed after catalog refresh")
                raise RuntimeError(f"Pricing registration failed: {exc}") from exc

            try:
                from app.services.llm_router_service import LLMRouterService

                LLMRouterService.rebuild(
                    getattr(config, "GLOBAL_LLM_CONFIGS", []),
                    getattr(config, "ROUTER_SETTINGS", {}),
                )
            except Exception as exc:
                logger.exception("LLM Router rebuild failed after catalog refresh")
                raise RuntimeError(f"LLM Router rebuild failed: {exc}") from exc

        return connections, models


def initialize_pricing_registration():
    """
    Teach LiteLLM the per-token cost of every deployment in
    ``config.GLOBAL_LLM_CONFIGS`` (OpenRouter dynamic models pulled
    from the OpenRouter catalogue + any operator-declared YAML pricing).

    Must run AFTER ``initialize_openrouter_integration()`` so the
    OpenRouter catalogue is populated and BEFORE the first LLM call so
    ``response_cost`` is available in ``TokenTrackingCallback``.

    Failures are logged but never raised — startup must not be blocked
    by a missing pricing entry; the worst-case is the model debits 0.
    """
    try:
        from app.services.pricing_registration import (
            register_pricing_for_managed_global_models,
            register_pricing_from_global_configs,
        )

        register_pricing_from_global_configs()
        register_pricing_for_managed_global_models()
    except Exception as e:
        print(f"Warning: Failed to register LiteLLM pricing: {e}")


def initialize_llm_router():
    """
    Initialize the LLM Router service for Auto mode.
    This should be called during application startup, AFTER
    initialize_openrouter_integration() so dynamic models are included.
    Uses config.GLOBAL_LLM_CONFIGS (in-memory) which includes both
    static YAML configs and dynamic OpenRouter models.
    """
    all_configs = config.GLOBAL_LLM_CONFIGS
    # Reuse the router settings already parsed at Config construction instead
    # of re-reading the YAML here.
    router_settings = config.ROUTER_SETTINGS

    if not all_configs:
        print(
            "Info: No global LLM configs found; global Auto pool is unavailable. "
            "Auto can still use enabled BYOK models."
        )
        return

    try:
        from app.services.llm_router_service import LLMRouterService

        LLMRouterService.initialize(all_configs, router_settings)
        print(
            f"Info: LLM Router initialized with {len(all_configs)} models "
            f"(strategy: {router_settings.get('routing_strategy', 'usage-based-routing')})"
        )
    except Exception as e:
        print(f"Warning: Failed to initialize LLM Router: {e}")


def initialize_image_gen_router():
    """
    Initialize the Image Generation Router service for Auto mode.
    This should be called during application startup.
    """
    image_gen_configs = load_global_image_gen_configs()
    # Reuse the router settings already parsed at Config construction. The
    # *configs* list is intentionally re-read from YAML (it must exclude the
    # OpenRouter-injected dynamic models held in config.GLOBAL_IMAGE_GEN_CONFIGS).
    router_settings = config.IMAGE_GEN_ROUTER_SETTINGS

    if not image_gen_configs:
        print(
            "Info: No global image generation configs found, "
            "Image Generation Auto mode will not be available"
        )
        return

    try:
        from app.services.image_gen_router_service import ImageGenRouterService

        ImageGenRouterService.initialize(image_gen_configs, router_settings)
        print(
            f"Info: Image Generation Router initialized with {len(image_gen_configs)} models "
            f"(strategy: {router_settings.get('routing_strategy', 'usage-based-routing')})"
        )
    except Exception as e:
        print(f"Warning: Failed to initialize Image Generation Router: {e}")


class Config:
    # Check if ffmpeg is installed
    if not is_ffmpeg_installed():
        allow_static_ffmpeg = (
            os.getenv("NOWING_ALLOW_STATIC_FFMPEG_DOWNLOAD", "TRUE").upper() == "TRUE"
        )
        if allow_static_ffmpeg:
            import static_ffmpeg

            # ffmpeg installed on first call to add_paths(), threadsafe.
            static_ffmpeg.add_paths()

        # check if ffmpeg is installed again
        if not is_ffmpeg_installed():
            raise ValueError(
                "FFmpeg is not installed on the system. Please install it to use the Nowing Podcaster."
            )

    # Deployment Mode (self-hosted or cloud)
    # self-hosted: Full access to local file system connectors (Obsidian, etc.)
    # cloud: Only cloud-based connectors available
    DEPLOYMENT_MODE = os.getenv("NOWING_DEPLOYMENT_MODE", "self-hosted")
    ENABLE_DESKTOP_LOCAL_FILESYSTEM = (
        os.getenv("ENABLE_DESKTOP_LOCAL_FILESYSTEM", "FALSE").upper() == "TRUE"
    )

    @classmethod
    def is_self_hosted(cls) -> bool:
        """Check if running in self-hosted mode."""
        return cls.DEPLOYMENT_MODE == "self-hosted"

    @classmethod
    def is_cloud(cls) -> bool:
        """Check if running in cloud mode."""
        return cls.DEPLOYMENT_MODE == "cloud"

    # Optional plan-limit overrides.  Values must be a JSON object mapping
    # plan tier -> {max_documents, max_members, max_runs, max_storage_bytes,
    # run_period_hours}.  Database seeded defaults remain the source of truth
    # unless overridden here.
    WORKSPACE_PLAN_LIMITS: dict[str, dict[str, Any]] | None = _env_json(
        "WORKSPACE_PLAN_LIMITS"
    )

    # Database
    DATABASE_URL = os.getenv("DATABASE_URL")

    # When TRUE (default) the app ensures extensions/tables/indexes exist on
    # startup. Set FALSE in environments where schema is owned exclusively by
    # Alembic migrations to skip all boot-time DDL.
    DB_BOOTSTRAP_ON_STARTUP = (
        os.getenv("DB_BOOTSTRAP_ON_STARTUP", "TRUE").upper() == "TRUE"
    )
    # Per-session lock_timeout (ms) applied to boot-time DDL so a contended
    # CREATE INDEX / CREATE TABLE fails fast instead of hanging the FastAPI
    # lifespan forever behind another transaction's lock.
    DB_DDL_LOCK_TIMEOUT_MS = int(os.getenv("DB_DDL_LOCK_TIMEOUT_MS", "5000"))
    # Global idle_in_transaction_session_timeout (ms) applied to every pooled
    # connection so an abandoned "idle in transaction" session can't wedge the
    # database indefinitely. 0 disables. Only applied to asyncpg connections.
    DB_IDLE_IN_TX_TIMEOUT_MS = int(os.getenv("DB_IDLE_IN_TX_TIMEOUT_MS", "900000"))
    # Same protection for the separate Celery worker engine, where long-running
    # ingestion/podcast/video tasks live. Kept higher than the web default so a
    # legitimate per-document embed window is never reaped: if a task hasn't
    # touched the DB in 60 min it's treated as orphaned and dropped. 0 disables.
    DB_CELERY_IDLE_IN_TX_TIMEOUT_MS = int(
        os.getenv("DB_CELERY_IDLE_IN_TX_TIMEOUT_MS", "3600000")
    )

    # Celery / Redis
    # Redis (single endpoint for Celery broker, result backend, and app cache).
    # Legacy CELERY_BROKER_URL / CELERY_RESULT_BACKEND / REDIS_APP_URL still
    # override individually when you need to split Redis across instances.
    REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL", REDIS_URL)
    CELERY_RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND", REDIS_URL)
    CELERY_TASK_DEFAULT_QUEUE = os.getenv("CELERY_TASK_DEFAULT_QUEUE", "nowing")
    REDIS_APP_URL = os.getenv("REDIS_APP_URL", CELERY_BROKER_URL)
    CONNECTOR_INDEXING_LOCK_TTL_SECONDS = int(
        os.getenv("CONNECTOR_INDEXING_LOCK_TTL_SECONDS", str(8 * 60 * 60))
    )

    # Celery beat scheduling intervals (format: "<number><unit>", e.g. "2m", "1h")
    SCHEDULE_CHECKER_INTERVAL = os.getenv("SCHEDULE_CHECKER_INTERVAL", "2m")
    STRIPE_RECONCILIATION_INTERVAL = os.getenv("STRIPE_RECONCILIATION_INTERVAL", "10m")

    # File storage (local filesystem by default; Azure Blob optional)
    FILE_STORAGE_BACKEND = os.getenv("FILE_STORAGE_BACKEND", "local").strip().lower()
    AZURE_STORAGE_CONNECTION_STRING = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
    AZURE_STORAGE_CONTAINER = os.getenv("AZURE_STORAGE_CONTAINER")
    FILE_STORAGE_LOCAL_PATH = os.getenv(
        "FILE_STORAGE_LOCAL_PATH", str(BASE_DIR / ".local_object_store")
    )

    # Daytona sandbox (code execution / filesystem sandbox)
    DAYTONA_SANDBOX_ENABLED = (
        os.getenv("DAYTONA_SANDBOX_ENABLED", "FALSE").upper() == "TRUE"
    )
    DAYTONA_API_KEY = os.getenv("DAYTONA_API_KEY", "")
    DAYTONA_API_URL = os.getenv("DAYTONA_API_URL", "https://app.daytona.io/api")
    DAYTONA_TARGET = os.getenv("DAYTONA_TARGET", "us")
    DAYTONA_SNAPSHOT_ID = os.getenv("DAYTONA_SNAPSHOT_ID") or None
    SANDBOX_FILES_DIR = os.getenv("SANDBOX_FILES_DIR", "sandbox_files")

    # Agent chat public API surface (Epic 18)
    # Default FALSE until the security review checklist is green.
    AGENT_CHAT_PUBLIC_ENABLED = (
        os.getenv("AGENT_CHAT_PUBLIC_ENABLED", "false").strip().upper() == "TRUE"
    )
    AGENT_CHAT_RATE_LIMIT_RPM = _env_int("AGENT_CHAT_RATE_LIMIT_RPM", 30)
    AGENT_CHAT_WORKSPACE_RATE_LIMIT_RPM = _env_int(
        "AGENT_CHAT_WORKSPACE_RATE_LIMIT_RPM", 100
    )

    # Agent cache (in-process LRU+TTL cache for built agents)
    AGENT_CACHE_MAXSIZE = int(os.getenv("NOWING_AGENT_CACHE_MAXSIZE", "256"))
    AGENT_CACHE_TTL_SECONDS = float(os.getenv("NOWING_AGENT_CACHE_TTL_SECONDS", "1800"))

    # Connector discovery cache TTL
    CONNECTOR_DISCOVERY_TTL_SECONDS = float(
        os.getenv("NOWING_CONNECTOR_DISCOVERY_TTL_SECONDS", "30")
    )

    # Memory auto-extraction defaults.
    MEMORY_AUTO_EXTRACT_ENABLED = (
        os.getenv("MEMORY_AUTO_EXTRACT_ENABLED", "true").strip().lower() == "true"
    )
    MEMORY_AUTO_EXTRACT_CONFIDENCE = max(
        0.0, min(1.0, _env_float("MEMORY_AUTO_EXTRACT_CONFIDENCE", 0.7))
    )
    MEMORY_AUTO_EXTRACT_MAX_ITEMS = max(1, _env_int("MEMORY_AUTO_EXTRACT_MAX_ITEMS", 3))

    # Memory auto-extraction cost controls (Story 8.7 / AR-6 / RS-1).
    # The budget cap and rate-limit default to disabled/no-op so enabling
    # auto-extract introduces no new gating until an operator opts in. The
    # wallet pre-check is the only always-on gate, but note what it is: an
    # ELIGIBILITY gate (skip optional background work for an owner who cannot
    # pay for their foreground work), NOT a spend meter for extraction. Per
    # AD-8 the wallet-debit surface is ETL pages / premium model calls /
    # deep-research; memory extraction is deliberately excluded, and
    # usage_type="memory_create" is Story 8.9's observability record, not a
    # debit. The bounds that actually apply to extraction spend are
    # MEMORY_AUTO_EXTRACT_ENABLED (kill-switch, Story 8.8) and the opt-in
    # budget cap below. See app.services.memory.extract_budget.
    #
    # Clamped to >= 1: 0 would disable the always-on gate entirely. Use 1 to
    # mean "only block a fully empty wallet".
    MEMORY_AUTO_EXTRACT_MIN_RESERVE_MICROS = max(
        1, _env_int("MEMORY_AUTO_EXTRACT_MIN_RESERVE_MICROS", 100)
    )
    # Per-workspace spend ceiling (micro-USD) for memory_create TokenUsage over
    # the current MEMORY_AUTO_EXTRACT_BUDGET_WINDOW. 0 = disabled (no gating).
    # Ships at 0 on purpose: AD-8's 2026-07-25 amendment forbids fixing a cost
    # figure before story 8-7 + FR-37 produce measured numbers.
    # Clamped to >= 0: negative values are treated as disabled, but we normalise
    # them to 0 to match the documented "0 = disabled" convention.
    MEMORY_AUTO_EXTRACT_BUDGET_MICROS = max(
        0, _env_int("MEMORY_AUTO_EXTRACT_BUDGET_MICROS", 0)
    )
    # Rolling budget window; "day" is a rolling 24h lookback (not a calendar-day
    # cliff) to avoid a midnight reset that lets a burst through right after
    # rollover. "month" is a flat 30-day lookback, not a calendar month.
    MEMORY_AUTO_EXTRACT_BUDGET_WINDOW = _env_choice(
        "MEMORY_AUTO_EXTRACT_BUDGET_WINDOW", "day", ("day", "week", "month")
    )
    # Max extractions per workspace per MEMORY_AUTO_EXTRACT_RATE_WINDOW_SECONDS.
    # 0 = disabled (no throttling). Clamped to >= 0 for the same reason as
    # MEMORY_AUTO_EXTRACT_BUDGET_MICROS.
    MEMORY_AUTO_EXTRACT_RATE_MAX = max(0, _env_int("MEMORY_AUTO_EXTRACT_RATE_MAX", 0))
    # Clamped to >= 1: Redis EXPIRE with a non-positive TTL deletes the key, so
    # 0 would make every increment self-destruct and silently void the limit.
    MEMORY_AUTO_EXTRACT_RATE_WINDOW_SECONDS = max(
        1, _env_int("MEMORY_AUTO_EXTRACT_RATE_WINDOW_SECONDS", 3600)
    )

    NOWING_PUBLIC_URL = os.getenv("NOWING_PUBLIC_URL")
    NEXT_FRONTEND_URL = os.getenv("NEXT_FRONTEND_URL") or NOWING_PUBLIC_URL
    # Backend URL to override the http to https in the OAuth redirect URI
    BACKEND_URL = os.getenv("BACKEND_URL") or NOWING_PUBLIC_URL

    # Messaging gateway
    # Global master switch: when FALSE, no gateway supervisors/workers start and all
    # gated gateway HTTP routes return 404, regardless of the per-channel flags below.
    GATEWAY_ENABLED = os.getenv("GATEWAY_ENABLED", "FALSE").upper() == "TRUE"
    TELEGRAM_SHARED_BOT_TOKEN = os.getenv("TELEGRAM_SHARED_BOT_TOKEN")
    TELEGRAM_SHARED_BOT_USERNAME = os.getenv("TELEGRAM_SHARED_BOT_USERNAME")
    TELEGRAM_WEBHOOK_SECRET = os.getenv("TELEGRAM_WEBHOOK_SECRET")
    GATEWAY_BASE_URL = os.getenv("GATEWAY_BASE_URL", BACKEND_URL)
    GATEWAY_TELEGRAM_INTAKE_MODE = os.getenv(
        "GATEWAY_TELEGRAM_INTAKE_MODE", "webhook"
    ).lower()
    if GATEWAY_TELEGRAM_INTAKE_MODE not in {"webhook", "longpoll", "disabled"}:
        raise ValueError(
            "GATEWAY_TELEGRAM_INTAKE_MODE must be one of: webhook, longpoll, disabled"
        )
    WHATSAPP_SHARED_BUSINESS_TOKEN = os.getenv("WHATSAPP_SHARED_BUSINESS_TOKEN")
    WHATSAPP_SHARED_PHONE_NUMBER_ID = os.getenv("WHATSAPP_SHARED_PHONE_NUMBER_ID")
    WHATSAPP_SHARED_DISPLAY_PHONE_NUMBER = os.getenv(
        "WHATSAPP_SHARED_DISPLAY_PHONE_NUMBER"
    )
    WHATSAPP_SHARED_WABA_ID = os.getenv("WHATSAPP_SHARED_WABA_ID")
    WHATSAPP_GRAPH_API_VERSION = os.getenv("WHATSAPP_GRAPH_API_VERSION", "v25.0")
    WHATSAPP_WEBHOOK_VERIFY_TOKEN = os.getenv("WHATSAPP_WEBHOOK_VERIFY_TOKEN")
    WHATSAPP_WEBHOOK_APP_SECRET = os.getenv("WHATSAPP_WEBHOOK_APP_SECRET")
    WHATSAPP_BRIDGE_URL = os.getenv(
        "WHATSAPP_BRIDGE_URL", "http://whatsapp-bridge:9929"
    )
    GATEWAY_WHATSAPP_INTAKE_MODE = os.getenv(
        "GATEWAY_WHATSAPP_INTAKE_MODE", "disabled"
    ).lower()
    if GATEWAY_WHATSAPP_INTAKE_MODE not in {"cloud", "baileys", "disabled"}:
        raise ValueError(
            "GATEWAY_WHATSAPP_INTAKE_MODE must be one of: cloud, baileys, disabled"
        )
    GATEWAY_SLACK_CLIENT_ID = os.getenv("SLACK_CLIENT_ID")
    GATEWAY_SLACK_CLIENT_SECRET = os.getenv("SLACK_CLIENT_SECRET")
    GATEWAY_SLACK_ENABLED = (
        os.getenv("GATEWAY_SLACK_ENABLED", "FALSE").upper() == "TRUE"
    )
    GATEWAY_SLACK_SIGNING_SECRET = os.getenv("GATEWAY_SLACK_SIGNING_SECRET")
    GATEWAY_SLACK_REDIRECT_URI = os.getenv("GATEWAY_SLACK_REDIRECT_URI")
    GATEWAY_DISCORD_ENABLED = (
        os.getenv("GATEWAY_DISCORD_ENABLED", "FALSE").upper() == "TRUE"
    )
    GATEWAY_DISCORD_REDIRECT_URI = os.getenv("GATEWAY_DISCORD_REDIRECT_URI")

    # Stripe checkout (shared secrets for the unified credit wallet)
    STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY")
    STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET")
    STRIPE_RECONCILIATION_LOOKBACK_MINUTES = int(
        os.getenv("STRIPE_RECONCILIATION_LOOKBACK_MINUTES", "10")
    )
    STRIPE_RECONCILIATION_BATCH_SIZE = int(
        os.getenv("STRIPE_RECONCILIATION_BATCH_SIZE", "100")
    )

    # Unified credit wallet (micro-USD) settings.
    #
    # Storage unit is integer micro-USD (1_000_000 = $1.00). A single
    # ``credit_micros_balance`` funds both ETL page processing and premium
    # model calls. New users start with ``DEFAULT_CREDIT_MICROS_BALANCE``
    # ($5 by default).
    #
    # Legacy env names (``PREMIUM_CREDIT_MICROS_LIMIT`` / ``PREMIUM_TOKEN_LIMIT``,
    # ``STRIPE_PREMIUM_TOKEN_PRICE_ID``, ``STRIPE_CREDIT_MICROS_PER_UNIT`` /
    # ``STRIPE_TOKENS_PER_UNIT``, ``STRIPE_TOKEN_BUYING_ENABLED``) are still
    # honoured as fall-backs for one release; deprecation warnings fire below.
    DEFAULT_CREDIT_MICROS_BALANCE = int(
        os.getenv("DEFAULT_CREDIT_MICROS_BALANCE")
        or os.getenv("PREMIUM_CREDIT_MICROS_LIMIT")
        or os.getenv("PREMIUM_TOKEN_LIMIT", "5000000")
    )
    STRIPE_CREDIT_PRICE_ID = os.getenv("STRIPE_CREDIT_PRICE_ID") or os.getenv(
        "STRIPE_PREMIUM_TOKEN_PRICE_ID"
    )
    STRIPE_CREDIT_MICROS_PER_UNIT = int(
        os.getenv("STRIPE_CREDIT_MICROS_PER_UNIT")
        or os.getenv("STRIPE_TOKENS_PER_UNIT", "1000000")
    )
    STRIPE_CREDIT_BUYING_ENABLED = (
        os.getenv("STRIPE_CREDIT_BUYING_ENABLED")
        or os.getenv("STRIPE_TOKEN_BUYING_ENABLED", "FALSE")
    ).upper() == "TRUE"

    # ETL page processing debits the credit wallet only when enabled. Defaults
    # to FALSE so self-hosted / OSS installs keep effectively-free ETL; hosted
    # deployments set this TRUE. 1 page == ``MICROS_PER_PAGE`` micro-USD.
    ETL_CREDIT_BILLING_ENABLED = (
        os.getenv("ETL_CREDIT_BILLING_ENABLED", "FALSE").upper() == "TRUE"
    )
    MICROS_PER_PAGE = int(os.getenv("MICROS_PER_PAGE", "1000"))

    # Web-crawl billing debits the credit wallet per *successful* crawl request
    # (CrawlOutcomeStatus.SUCCESS). Off by default so self-hosted / OSS installs
    # keep crawling effectively-free; hosted deployments set this TRUE.
    #
    # The price is fully config-driven — there is no hardcoded rate anywhere.
    # ``WEB_CRAWL_MICROS_PER_SUCCESS`` is the single source of truth; retune it
    # to any rate with just an env change + restart (no code/migration):
    #   WEB_CRAWL_MICROS_PER_SUCCESS = round(USD_per_1000_crawls * 1_000)
    #   $2/1000 -> 2000 (default) | $1/1000 -> 1000 | $0.50/1000 -> 500
    WEB_CRAWL_CREDIT_BILLING_ENABLED = (
        os.getenv("WEB_CRAWL_CREDIT_BILLING_ENABLED", "FALSE").upper() == "TRUE"
    )
    WEB_CRAWL_MICROS_PER_SUCCESS = int(
        os.getenv("WEB_CRAWL_MICROS_PER_SUCCESS", "2000")
    )

    # Phase 3d captcha-solve billing. Captcha can't ride the per-success crawl
    # meter above: the solver charges per *attempt* regardless of whether the
    # crawl ultimately succeeds, so solves are metered as a SEPARATE per-attempt
    # unit (usage_type="web_crawl_captcha"). Off by default; independent of the
    # crawl-billing flag. Price is config-driven (no hardcoded rate):
    #   WEB_CRAWL_CAPTCHA_MICROS_PER_SOLVE = round(USD_per_1000_solves * 1_000)
    #   $3/1000 -> 3000 (default) | $5/1000 -> 5000
    # Set with margin over the solver vendor's per-attempt price.
    WEB_CRAWL_CAPTCHA_BILLING_ENABLED = (
        os.getenv("WEB_CRAWL_CAPTCHA_BILLING_ENABLED", "FALSE").upper() == "TRUE"
    )
    WEB_CRAWL_CAPTCHA_MICROS_PER_SOLVE = int(
        os.getenv("WEB_CRAWL_CAPTCHA_MICROS_PER_SOLVE", "3000")
    )

    # Platform-native scraper billing (Reddit, Google Search, Google Maps,
    # YouTube). Debits the credit wallet per *item returned* — the same
    # per-unit model as web crawl, one meter per verb. Off by default so
    # self-hosted / OSS installs keep scraping effectively-free; hosted
    # deployments set this TRUE.
    #
    # Rates are fully config-driven (no hardcoded price). Each is micro-USD
    # per item; retune with an env change + restart (no code/migration):
    #   <KEY> = round(USD_per_1000_items * 1_000)
    #   $3.50/1000 -> 3500 | $5.00/1000 -> 5000 | $2.00/1000 -> 2000
    # Defaults include margin for proxy, compute, and storage costs while
    # remaining independently adjustable for each platform.
    PLATFORM_SCRAPE_BILLING_ENABLED = (
        os.getenv("PLATFORM_SCRAPE_BILLING_ENABLED", "FALSE").upper() == "TRUE"
    )
    REDDIT_SCRAPE_MICROS_PER_ITEM = int(
        os.getenv("REDDIT_SCRAPE_MICROS_PER_ITEM", "3500")
    )
    GOOGLE_SEARCH_MICROS_PER_SERP = int(
        os.getenv("GOOGLE_SEARCH_MICROS_PER_SERP", "5500")
    )
    GOOGLE_MAPS_MICROS_PER_PLACE = int(
        os.getenv("GOOGLE_MAPS_MICROS_PER_PLACE", "3500")
    )
    GOOGLE_MAPS_MICROS_PER_REVIEW = int(
        os.getenv("GOOGLE_MAPS_MICROS_PER_REVIEW", "1500")
    )
    AMAZON_MICROS_PER_PRODUCT = int(os.getenv("AMAZON_MICROS_PER_PRODUCT", "3500"))
    YOUTUBE_MICROS_PER_VIDEO = int(os.getenv("YOUTUBE_MICROS_PER_VIDEO", "2500"))
    # Kept separate from the video rate so comments can be re-tuned toward the
    # cheaper per-comment market ($0.40-2.00/1k) without touching video pricing.
    YOUTUBE_MICROS_PER_COMMENT = int(os.getenv("YOUTUBE_MICROS_PER_COMMENT", "1500"))
    INSTAGRAM_SCRAPE_MICROS_PER_ITEM = int(
        os.getenv("INSTAGRAM_SCRAPE_MICROS_PER_ITEM", "3500")
    )
    # Kept separate from the item rate so comments can be re-tuned toward the
    # cheaper per-comment market without touching post/reel pricing.
    INSTAGRAM_SCRAPE_MICROS_PER_COMMENT = int(
        os.getenv("INSTAGRAM_SCRAPE_MICROS_PER_COMMENT", "1500")
    )
    # Mobile API listings are cheap and stable, priced near Reddit/Instagram.
    BATDONGSAN_SCRAPE_MICROS_PER_ITEM = int(
        os.getenv("BATDONGSAN_SCRAPE_MICROS_PER_ITEM", "3500")
    )
    # Pacing: seconds between page requests while paginating, and the base of
    # the exponential backoff (base * 2**attempt) between retries. Politeness
    # keeps the mobile endpoint from rate-limiting us.
    BATDONGSAN_PAGE_DELAY_S = float(os.getenv("BATDONGSAN_PAGE_DELAY_S", "0.5"))
    BATDONGSAN_RETRY_BACKOFF_BASE_S = float(
        os.getenv("BATDONGSAN_RETRY_BACKOFF_BASE_S", "0.5")
    )
    # Phone-reveal rate limits per account.  These are conservative defaults
    # for batdongsan.com.vn; tune them once you have measured the real threshold.
    BATDONGSAN_PHONE_RPM = float(os.getenv("BATDONGSAN_PHONE_RPM", "5.0"))
    BATDONGSAN_PHONE_BURST = int(os.getenv("BATDONGSAN_PHONE_BURST", "2"))
    BATDONGSAN_PHONE_COOLDOWN_S = float(
        os.getenv("BATDONGSAN_PHONE_COOLDOWN_S", "300.0")
    )
    BATDONGSAN_PHONE_MAX_CONSECUTIVE_FAILURES = int(
        os.getenv("BATDONGSAN_PHONE_MAX_CONSECUTIVE_FAILURES", "3")
    )
    # Chợ Tốt Nhà uses a public JSON gateway, similar cost to Batdongsan.
    CHOTOT_BDS_SCRAPE_MICROS_PER_ITEM = int(
        os.getenv("CHOTOT_BDS_SCRAPE_MICROS_PER_ITEM", "3500")
    )
    CHOTOT_SCRAPE_MICROS_PER_ITEM = int(
        os.getenv("CHOTOT_SCRAPE_MICROS_PER_ITEM", "3500")
    )
    CHOTOT_BDS_PAGE_DELAY_S = float(os.getenv("CHOTOT_BDS_PAGE_DELAY_S", "0.5"))
    CHOTOT_BDS_RETRY_BACKOFF_BASE_S = float(
        os.getenv("CHOTOT_BDS_RETRY_BACKOFF_BASE_S", "0.5")
    )
    CHOTOT_BDS_TIMEOUT_S = float(os.getenv("CHOTOT_BDS_TIMEOUT_S", "30.0"))
    CHOTOT_BDS_USER_AGENT = os.getenv("CHOTOT_BDS_USER_AGENT", "")
    # Muaban.net requires a headless browser to pass Cloudflare, so the per-item
    # rate sits above the API-backed Batdongsan/Chotot rates.
    MUABAN_BDS_SCRAPE_MICROS_PER_ITEM = int(
        os.getenv("MUABAN_BDS_SCRAPE_MICROS_PER_ITEM", "5500")
    )
    MUABAN_BDS_PAGE_DELAY_S = float(os.getenv("MUABAN_BDS_PAGE_DELAY_S", "1.0"))
    MUABAN_BDS_RETRY_BACKOFF_BASE_S = float(
        os.getenv("MUABAN_BDS_RETRY_BACKOFF_BASE_S", "1.0")
    )
    # Multi-source BĐS aggregation charges a flat query fee on top of the
    # underlying scraper item costs. This covers normalize/dedupe/conflict work.
    VN_BDS_AGGREGATE_QUERY_MICROS_PER_QUERY = int(
        os.getenv("VN_BDS_AGGREGATE_QUERY_MICROS_PER_QUERY", "5000")
    )
    # VietnamWorks is a public API-backed source; price near other API platforms.
    VIETNAMWORKS_SCRAPE_MICROS_PER_ITEM = int(
        os.getenv("VIETNAMWORKS_SCRAPE_MICROS_PER_ITEM", "3000")
    )
    VIETNAMWORKS_PAGE_DELAY_S = float(os.getenv("VIETNAMWORKS_PAGE_DELAY_S", "0.5"))
    VIETNAMWORKS_TIMEOUT_S = float(os.getenv("VIETNAMWORKS_TIMEOUT_S", "30.0"))
    VIETNAMWORKS_MAX_PAGES = int(os.getenv("VIETNAMWORKS_MAX_PAGES", "5"))
    VIETNAMWORKS_MAX_ITEMS = int(os.getenv("VIETNAMWORKS_MAX_ITEMS", "100"))
    VIETNAMWORKS_RETRY_ATTEMPTS = int(os.getenv("VIETNAMWORKS_RETRY_ATTEMPTS", "2"))
    VIETNAMWORKS_RETRY_BACKOFF_BASE_S = float(
        os.getenv("VIETNAMWORKS_RETRY_BACKOFF_BASE_S", "0.5")
    )
    VIETNAMWORKS_USER_AGENT = os.getenv(
        "VIETNAMWORKS_USER_AGENT",
        (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/126.0.0.0 Safari/537.36"
        ),
    )
    TOPCV_USER_AGENT = os.getenv(
        "TOPCV_USER_AGENT",
        (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/126.0.0.0 Safari/537.36"
        ),
    )
    # TopCV is Cloudflare-protected and uses the web crawler stack. The platform
    # per-item rate is a pass-through; actual anti-bot cost is metered via
    # WEB_CRAWL + WEB_CRAWL_CAPTCHA_MICROS_PER_SOLVE (see AD-23).
    TOPCV_ENABLED = os.getenv("TOPCV_ENABLED", "TRUE").upper() == "TRUE"
    TOPCV_SCRAPE_MICROS_PER_ITEM = int(
        os.getenv("TOPCV_SCRAPE_MICROS_PER_ITEM", "5500")
    )
    TOPCV_PAGE_DELAY_S = float(os.getenv("TOPCV_PAGE_DELAY_S", "1.0"))
    TOPCV_TIMEOUT_S = float(os.getenv("TOPCV_TIMEOUT_S", "60.0"))
    TOPCV_MAX_PAGES = int(os.getenv("TOPCV_MAX_PAGES", "3"))
    TOPCV_RETRY_ATTEMPTS = int(os.getenv("TOPCV_RETRY_ATTEMPTS", "2"))
    TOPCV_RETRY_BACKOFF_BASE_S = float(os.getenv("TOPCV_RETRY_BACKOFF_BASE_S", "2.0"))
    TOPCV_CIRCUIT_BREAKER_THRESHOLD = int(
        os.getenv("TOPCV_CIRCUIT_BREAKER_THRESHOLD", "3")
    )
    TOPCV_CIRCUIT_BREAKER_TIMEOUT_S = float(
        os.getenv("TOPCV_CIRCUIT_BREAKER_TIMEOUT_S", "60.0")
    )
    # ITviec is server-rendered HTML; cheaper than TopCV, no anti-bot expected.
    ITVIEC_SCRAPE_MICROS_PER_ITEM = int(
        os.getenv("ITVIEC_SCRAPE_MICROS_PER_ITEM", "3000")
    )
    ITVIEC_PAGE_DELAY_S = float(os.getenv("ITVIEC_PAGE_DELAY_S", "0.5"))
    ITVIEC_TIMEOUT_S = float(os.getenv("ITVIEC_TIMEOUT_S", "30.0"))
    ITVIEC_MAX_PAGES = int(os.getenv("ITVIEC_MAX_PAGES", "5"))
    # Indeed is Cloudflare-protected and uses the browser/anti-bot stack.
    INDEED_SCRAPE_MICROS_PER_ITEM = int(
        os.getenv("INDEED_SCRAPE_MICROS_PER_ITEM", "5000")
    )
    INDEED_PAGE_DELAY_S = float(os.getenv("INDEED_PAGE_DELAY_S", "1.0"))
    INDEED_MAX_PAGES = int(os.getenv("INDEED_MAX_PAGES", "5"))
    INDEED_MAX_ITEMS = int(os.getenv("INDEED_MAX_ITEMS", "50"))
    # Walmart is a Next.js storefront; data is primarily in __NEXT_DATA__ JSON.
    WALMART_SCRAPE_MICROS_PER_ITEM = int(
        os.getenv("WALMART_SCRAPE_MICROS_PER_ITEM", "5000")
    )
    WALMART_REVIEW_MICROS_PER_ITEM = int(
        os.getenv("WALMART_REVIEW_MICROS_PER_ITEM", "500")
    )
    WALMART_PAGE_DELAY_S = float(os.getenv("WALMART_PAGE_DELAY_S", "1.0"))
    WALMART_MAX_ITEMS = int(os.getenv("WALMART_MAX_ITEMS", "50"))
    WALMART_MAX_REVIEWS = int(os.getenv("WALMART_MAX_REVIEWS", "100"))
    # CafeF unofficial API. Demo mode uses stable synthetic data so the
    # capability works in tests and demos without relying on undocumented
    # public quote/news endpoints. Set CAFEF_DEMO_MODE=false and supply live
    # URLs to hit the real CafeF APIs.
    CAFEF_DATA_MICROS_PER_ITEM = int(os.getenv("CAFEF_DATA_MICROS_PER_ITEM", "5000"))
    CAFEF_RATE_LIMIT_RPS = float(os.getenv("CAFEF_RATE_LIMIT_RPS", str(20 / 60)))
    CAFEF_TIMEOUT_S = float(os.getenv("CAFEF_TIMEOUT_S", "15.0"))
    CAFEF_DEMO_MODE = os.getenv("CAFEF_DEMO_MODE", "TRUE").upper() == "TRUE"
    CAFEF_QUOTE_URL = os.getenv("CAFEF_QUOTE_URL", "")
    CAFEF_NEWS_URL = os.getenv("CAFEF_NEWS_URL", "")
    CAFEF_FINANCIAL_BASE_URL = os.getenv("CAFEF_FINANCIAL_BASE_URL", "")
    # Vietstock unofficial API. Demo mode uses stable synthetic data so the
    # capability works in tests and demos without real credentials.
    VIETSTOCK_DATA_MICROS_PER_ITEM = int(
        os.getenv("VIETSTOCK_DATA_MICROS_PER_ITEM", "5000")
    )
    VIETSTOCK_RATE_LIMIT_RPS = float(
        os.getenv("VIETSTOCK_RATE_LIMIT_RPS", str(20 / 60))
    )
    VIETSTOCK_TIMEOUT_S = float(os.getenv("VIETSTOCK_TIMEOUT_S", "15.0"))
    VIETSTOCK_DEMO_MODE = os.getenv("VIETSTOCK_DEMO_MODE", "TRUE").upper() == "TRUE"
    VIETSTOCK_QUOTE_URL = os.getenv("VIETSTOCK_QUOTE_URL", "")
    VIETSTOCK_FINANCIAL_URL = os.getenv("VIETSTOCK_FINANCIAL_URL", "")
    VIETSTOCK_SESSION_COOKIE = os.getenv("VIETSTOCK_SESSION_COOKIE", "")
    # masothue.com company directory. Cloudflare-protected; use polite pacing.
    MASOTHUE_SCRAPE_MICROS_PER_ITEM = int(
        os.getenv("MASOTHUE_SCRAPE_MICROS_PER_ITEM", "3000")
    )
    MASOTHUE_PAGE_DELAY_S = float(os.getenv("MASOTHUE_PAGE_DELAY_S", "1.0"))
    MASOTHUE_TIMEOUT_S = float(os.getenv("MASOTHUE_TIMEOUT_S", "30.0"))
    MASOTHUE_MAX_PAGES = int(os.getenv("MASOTHUE_MAX_PAGES", "5"))
    MASOTHUE_MAX_ITEMS = int(os.getenv("MASOTHUE_MAX_ITEMS", "50"))
    # Multi-source job aggregation (VietnamWorks/TopCV/ITviec).
    VN_JOBS_AGGREGATE_QUERY_MICROS_PER_QUERY = int(
        os.getenv("VN_JOBS_AGGREGATE_QUERY_MICROS_PER_QUERY", "5000")
    )
    VN_JOBS_AGGREGATE_MAX_ITEMS_PER_SOURCE = int(
        os.getenv("VN_JOBS_AGGREGATE_MAX_ITEMS_PER_SOURCE", "50")
    )
    VN_JOBS_AGGREGATE_MAX_PAGES = int(os.getenv("VN_JOBS_AGGREGATE_MAX_PAGES", "5"))
    # PII redaction confidence threshold (0-1) before treating a source as unsafe
    # for memory extraction.
    PII_REDACTION_MIN_CONFIDENCE = float(
        os.getenv("PII_REDACTION_MIN_CONFIDENCE", "0.7")
    )
    # Browser-driven listings make TikTok heavier per item than the API-backed
    # video meter, so it sits a touch above YouTube's video rate.
    TIKTOK_MICROS_PER_VIDEO = int(os.getenv("TIKTOK_MICROS_PER_VIDEO", "3500"))
    # User search returns lighter account records (name/followers/bio), priced
    # below the video meter to mirror the cheaper account-discovery market.
    TIKTOK_MICROS_PER_USER = int(os.getenv("TIKTOK_MICROS_PER_USER", "2500"))
    # Comments are the cheapest per-item TikTok data, matching the per-comment
    # market (and YouTube's comment meter).
    TIKTOK_MICROS_PER_COMMENT = int(os.getenv("TIKTOK_MICROS_PER_COMMENT", "1500"))
    # Retry an empty listing draw on a fresh rotating IP. Set to 1 for a static
    # proxy, where every retry re-hits the same exit.
    TIKTOK_LISTING_MAX_ATTEMPTS = int(os.getenv("TIKTOK_LISTING_MAX_ATTEMPTS", "3"))

    # ChainLens Research / Ingest integration (https://research-api.chainlens.net or local).
    # CHAINLENS_SERVICE_TOKEN is the preferred service-to-service token for ingest.
    # CHAINLENS_API_KEY is kept as a legacy alias for deep-research calls.
    CHAINLENS_API_URL = os.getenv("CHAINLENS_API_URL", "http://localhost:3001").rstrip(
        "/"
    )
    CHAINLENS_SERVICE_TOKEN = os.getenv("CHAINLENS_SERVICE_TOKEN", "")
    CHAINLENS_API_KEY = os.getenv("CHAINLENS_API_KEY", "")
    CHAINLENS_REQUEST_TIMEOUT_SECONDS = float(
        os.getenv("CHAINLENS_REQUEST_TIMEOUT_SECONDS", "300")
    )
    # Fallback flat rate for deep-research calls that do not emit costDollars.
    # Default is ~the average real cost observed in ChainLens benchmark 2026-08-02
    # (report-per-mode.md: avg $0.0519; research balanced $0.0482, quality $0.0671).
    # Override via env for a specific deployment/pricing model.
    CHAINLENS_QUERY_MICROS_PER_CALL = int(
        os.getenv("CHAINLENS_QUERY_MICROS_PER_CALL", "60000")
    )
    # Margin applied to the engine-reported cost for self-host calls to cover
    # full-pipeline overhead until ChainLens emits aggregated cost (Story 42-1b).
    # Default 1.5x; billed_micros = floor(cost_micros * multiplier).
    _self_host_multiplier = _env_float("SELF_HOST_RESEARCH_COST_MULTIPLIER", 1.5)
    if _self_host_multiplier <= 0:
        _self_host_multiplier = 1.5
    SELF_HOST_RESEARCH_COST_MULTIPLIER = _self_host_multiplier
    # Scraper feed ingest settings.
    CHAINLENS_INGEST_MAX_BATCH_SIZE = int(
        os.getenv("CHAINLENS_INGEST_MAX_BATCH_SIZE", "1000")
    )
    CHAINLENS_INGEST_TIMEOUT_SECONDS = float(
        os.getenv("CHAINLENS_INGEST_TIMEOUT_SECONDS", "5")
    )
    CHAINLENS_INGEST_RETRY_MAX_ATTEMPTS = int(
        os.getenv("CHAINLENS_INGEST_RETRY_MAX_ATTEMPTS", "3")
    )
    CHAINLENS_INGEST_RETRY_BACKOFF_SECONDS = float(
        os.getenv("CHAINLENS_INGEST_RETRY_BACKOFF_SECONDS", "1.0")
    )

    # Capability run event bus backend. "memory" keeps events in-process (the
    # default for single-process/test deployments); "redis" uses Redis pub/sub
    # so multiple API replicas can tail the same run.
    RUN_EVENT_BUS = os.getenv("RUN_EVENT_BUS", "memory").strip().lower()

    # Default research mode. "balanced" is the planned new default (SD6/PRD D3);
    # "quality" is the old default and remains an explicit opt-in.
    _default_mode = os.getenv("DEFAULT_RESEARCH_MODE", "balanced").strip().lower()
    if _default_mode not in {"speed", "balanced", "quality", "auto"}:
        logger.warning(
            "Invalid DEFAULT_RESEARCH_MODE=%r; falling back to 'balanced'",
            _default_mode,
        )
        _default_mode = "balanced"
    DEFAULT_RESEARCH_MODE = _default_mode
    # NFR-9 State A vs State B for deep research in chat.
    #
    # State A (default, launch setting): DEEP_RESEARCH_SYNC_CHAT_MODE_ENABLED is
    # False. Both the REST and agent paths force chainlens.research to async mode
    # so the chat turn returns immediately and ChainLens runs in the background.
    # This is the launch default because the GTM review shows ChainLens balanced
    # p95 at 44.3s, which is above the 30s synchronous target.
    #
    # State B (opt-in): DEEP_RESEARCH_SYNC_CHAT_MODE_ENABLED is True. The REST
    # and agent paths may run chainlens.research synchronously, blocking on
    # ChainLens. Do not enable until a ratified baseline shows p95 <= 30s.
    DEEP_RESEARCH_SYNC_CHAT_MODE_ENABLED = (
        os.getenv("DEEP_RESEARCH_SYNC_CHAT_MODE_ENABLED", "FALSE").upper() == "TRUE"
    )

    # Low-balance WARNING threshold (micro-USD). Surfaced by the quota service
    # so the UI can nudge the user to top up / enable auto-reload. $0.50.
    CREDIT_LOW_BALANCE_WARNING_MICROS = int(
        os.getenv("CREDIT_LOW_BALANCE_WARNING_MICROS", "500000")
    )

    # Auto-reload (off-session Stripe top-up) feature flag and guards.
    AUTO_RELOAD_ENABLED = os.getenv("AUTO_RELOAD_ENABLED", "FALSE").upper() == "TRUE"
    # Minimum configurable reload amount (micro-USD). $1.00 to match pack pricing.
    AUTO_RELOAD_MIN_AMOUNT_MICROS = int(
        os.getenv("AUTO_RELOAD_MIN_AMOUNT_MICROS", "1000000")
    )
    # Cooldown so a burst of debits can't fire multiple charges (minutes).
    AUTO_RELOAD_COOLDOWN_MINUTES = int(os.getenv("AUTO_RELOAD_COOLDOWN_MINUTES", "10"))

    # Safety ceiling on the per-call premium reservation. ``stream_new_chat``
    # estimates an upper-bound cost from ``litellm.get_model_info`` x the
    # config's ``quota_reserve_tokens`` and clamps the result to this value
    # so a misconfigured "$1000/M" model can't lock the user's whole balance
    # on one call. Default $1.00 covers realistic worst-cases (Opus + 4K
    # reserve_tokens ≈ $0.36) with headroom.
    QUOTA_MAX_RESERVE_MICROS = int(os.getenv("QUOTA_MAX_RESERVE_MICROS", "1000000"))

    if (
        os.getenv("PREMIUM_TOKEN_LIMIT") or os.getenv("PREMIUM_CREDIT_MICROS_LIMIT")
    ) and not os.getenv("DEFAULT_CREDIT_MICROS_BALANCE"):
        print(
            "Warning: PREMIUM_TOKEN_LIMIT / PREMIUM_CREDIT_MICROS_LIMIT are "
            "deprecated; rename to DEFAULT_CREDIT_MICROS_BALANCE. The old keys "
            "will be removed in a future release."
        )
    if os.getenv("STRIPE_TOKENS_PER_UNIT") and not os.getenv(
        "STRIPE_CREDIT_MICROS_PER_UNIT"
    ):
        print(
            "Warning: STRIPE_TOKENS_PER_UNIT is deprecated; rename to "
            "STRIPE_CREDIT_MICROS_PER_UNIT (1:1 numerical mapping). "
            "The old key will be removed in a future release."
        )
    if os.getenv("STRIPE_PREMIUM_TOKEN_PRICE_ID") and not os.getenv(
        "STRIPE_CREDIT_PRICE_ID"
    ):
        print(
            "Warning: STRIPE_PREMIUM_TOKEN_PRICE_ID is deprecated; rename to "
            "STRIPE_CREDIT_PRICE_ID. The old key will be removed in a future "
            "release."
        )
    if os.getenv("STRIPE_TOKEN_BUYING_ENABLED") and not os.getenv(
        "STRIPE_CREDIT_BUYING_ENABLED"
    ):
        print(
            "Warning: STRIPE_TOKEN_BUYING_ENABLED is deprecated; rename to "
            "STRIPE_CREDIT_BUYING_ENABLED. The old key will be removed in a "
            "future release."
        )

    # Anonymous / no-login mode settings
    NOLOGIN_MODE_ENABLED = os.getenv("NOLOGIN_MODE_ENABLED", "FALSE").upper() == "TRUE"
    ANON_TOKEN_LIMIT = int(os.getenv("ANON_TOKEN_LIMIT", "500000"))
    ANON_TOKEN_WARNING_THRESHOLD = int(
        os.getenv("ANON_TOKEN_WARNING_THRESHOLD", "400000")
    )
    ANON_TOKEN_QUOTA_TTL_DAYS = int(os.getenv("ANON_TOKEN_QUOTA_TTL_DAYS", "30"))
    ANON_MAX_UPLOAD_SIZE_MB = int(os.getenv("ANON_MAX_UPLOAD_SIZE_MB", "5"))

    # Default quota reserve tokens when not specified per-model
    QUOTA_MAX_RESERVE_PER_CALL = int(os.getenv("QUOTA_MAX_RESERVE_PER_CALL", "8000"))

    # Per-image reservation (in micro-USD) used by ``billable_call`` for the
    # ``POST /image-generations`` endpoint when the global config does not
    # override it. $0.05 covers realistic worst-cases for current OpenAI /
    # OpenRouter image-gen pricing. Bypassed entirely for free configs.
    QUOTA_DEFAULT_IMAGE_RESERVE_MICROS = int(
        os.getenv("QUOTA_DEFAULT_IMAGE_RESERVE_MICROS", "50000")
    )

    # Per-podcast reservation (in micro-USD). One chat model call generating
    # a transcript, typically 5k-20k completion tokens. $0.20 covers a long
    # premium-model run. Tune via env.
    QUOTA_DEFAULT_PODCAST_RESERVE_MICROS = int(
        os.getenv("QUOTA_DEFAULT_PODCAST_RESERVE_MICROS", "200000")
    )

    # Per-video-presentation reservation (in micro-USD). Fan-out of N
    # slide-scene generations (up to ``VIDEO_PRESENTATION_MAX_SLIDES=30``)
    # plus refine retries; can produce many premium completions. $1.00
    # covers worst-case. Tune via env.
    #
    # NOTE: this equals the existing ``QUOTA_MAX_RESERVE_MICROS`` default of
    # 1_000_000. The override path in ``billable_call`` bypasses the
    # per-call clamp in ``estimate_call_reserve_micros``, so this is the
    # *actual* hold — raising it via env is fine but means a single video
    # task can lock $1+ of credit.
    QUOTA_DEFAULT_VIDEO_PRESENTATION_RESERVE_MICROS = int(
        os.getenv("QUOTA_DEFAULT_VIDEO_PRESENTATION_RESERVE_MICROS", "1000000")
    )

    # Abuse prevention: concurrent stream cap and CAPTCHA
    ANON_MAX_CONCURRENT_STREAMS = int(os.getenv("ANON_MAX_CONCURRENT_STREAMS", "2"))
    ANON_CAPTCHA_REQUEST_THRESHOLD = int(
        os.getenv("ANON_CAPTCHA_REQUEST_THRESHOLD", "5")
    )

    # Cloudflare Turnstile CAPTCHA
    TURNSTILE_ENABLED = os.getenv("TURNSTILE_ENABLED", "FALSE").upper() == "TRUE"
    TURNSTILE_SECRET_KEY = os.getenv("TURNSTILE_SECRET_KEY", "")

    # Auth
    AUTH_TYPE = os.getenv("AUTH_TYPE", "LOCAL")
    REGISTRATION_ENABLED = os.getenv("REGISTRATION_ENABLED", "TRUE").upper() == "TRUE"

    # Google OAuth
    GOOGLE_OAUTH_CLIENT_ID = os.getenv("GOOGLE_OAUTH_CLIENT_ID")
    GOOGLE_OAUTH_CLIENT_SECRET = os.getenv("GOOGLE_OAUTH_CLIENT_SECRET")
    GOOGLE_DESKTOP_CLIENT_ID = os.getenv("GOOGLE_DESKTOP_CLIENT_ID")
    GOOGLE_DESKTOP_CLIENT_SECRET = os.getenv("GOOGLE_DESKTOP_CLIENT_SECRET")
    GOOGLE_PICKER_API_KEY = os.getenv("GOOGLE_PICKER_API_KEY")

    # Google Calendar redirect URI
    GOOGLE_CALENDAR_REDIRECT_URI = os.getenv("GOOGLE_CALENDAR_REDIRECT_URI")

    # Google Gmail redirect URI
    GOOGLE_GMAIL_REDIRECT_URI = os.getenv("GOOGLE_GMAIL_REDIRECT_URI")

    # Google Drive redirect URI
    GOOGLE_DRIVE_REDIRECT_URI = os.getenv("GOOGLE_DRIVE_REDIRECT_URI")

    # Airtable OAuth
    AIRTABLE_CLIENT_ID = os.getenv("AIRTABLE_CLIENT_ID")
    AIRTABLE_CLIENT_SECRET = os.getenv("AIRTABLE_CLIENT_SECRET")
    AIRTABLE_REDIRECT_URI = os.getenv("AIRTABLE_REDIRECT_URI")

    # Notion OAuth
    NOTION_CLIENT_ID = os.getenv("NOTION_CLIENT_ID")
    NOTION_CLIENT_SECRET = os.getenv("NOTION_CLIENT_SECRET")
    NOTION_REDIRECT_URI = os.getenv("NOTION_REDIRECT_URI")

    # Atlassian OAuth (shared for Jira and Confluence)
    ATLASSIAN_CLIENT_ID = os.getenv("ATLASSIAN_CLIENT_ID")
    ATLASSIAN_CLIENT_SECRET = os.getenv("ATLASSIAN_CLIENT_SECRET")
    JIRA_REDIRECT_URI = os.getenv("JIRA_REDIRECT_URI")
    CONFLUENCE_REDIRECT_URI = os.getenv("CONFLUENCE_REDIRECT_URI")

    # Linear OAuth
    LINEAR_CLIENT_ID = os.getenv("LINEAR_CLIENT_ID")
    LINEAR_CLIENT_SECRET = os.getenv("LINEAR_CLIENT_SECRET")
    LINEAR_REDIRECT_URI = os.getenv("LINEAR_REDIRECT_URI")

    # Slack OAuth
    SLACK_CLIENT_ID = os.getenv("SLACK_CLIENT_ID")
    SLACK_CLIENT_SECRET = os.getenv("SLACK_CLIENT_SECRET")
    SLACK_REDIRECT_URI = os.getenv("SLACK_REDIRECT_URI")

    # Discord OAuth
    DISCORD_CLIENT_ID = os.getenv("DISCORD_CLIENT_ID")
    DISCORD_CLIENT_SECRET = os.getenv("DISCORD_CLIENT_SECRET")
    DISCORD_REDIRECT_URI = os.getenv("DISCORD_REDIRECT_URI")
    DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN")

    # Microsoft OAuth (shared for Teams and OneDrive)
    MICROSOFT_CLIENT_ID = os.getenv("MICROSOFT_CLIENT_ID")
    MICROSOFT_CLIENT_SECRET = os.getenv("MICROSOFT_CLIENT_SECRET")
    TEAMS_REDIRECT_URI = os.getenv("TEAMS_REDIRECT_URI")
    ONEDRIVE_REDIRECT_URI = os.getenv("ONEDRIVE_REDIRECT_URI")

    # ClickUp OAuth
    CLICKUP_CLIENT_ID = os.getenv("CLICKUP_CLIENT_ID")
    CLICKUP_CLIENT_SECRET = os.getenv("CLICKUP_CLIENT_SECRET")
    CLICKUP_REDIRECT_URI = os.getenv("CLICKUP_REDIRECT_URI")

    # Dropbox OAuth
    DROPBOX_APP_KEY = os.getenv("DROPBOX_APP_KEY")
    DROPBOX_APP_SECRET = os.getenv("DROPBOX_APP_SECRET")
    DROPBOX_REDIRECT_URI = os.getenv("DROPBOX_REDIRECT_URI")

    # Composio Configuration (for managed OAuth integrations)
    # Get your API key from https://app.composio.dev
    COMPOSIO_API_KEY = os.getenv("COMPOSIO_API_KEY")
    COMPOSIO_ENABLED = os.getenv("COMPOSIO_ENABLED", "FALSE").upper() == "TRUE"
    COMPOSIO_REDIRECT_URI = os.getenv("COMPOSIO_REDIRECT_URI")

    # LLM instances are now managed per-user through the LLMConfig system
    # Legacy environment variables removed in favor of user-specific configurations

    # True when an operator-provided global_llm_config.yaml is present.
    # Used to gate the per-workspace LLM onboarding flow: when a global
    # config file exists, workspaces inherit it and onboarding is skipped.
    GLOBAL_LLM_CONFIG_FILE_EXISTS = (
        BASE_DIR / "app" / "config" / "global_llm_config.yaml"
    ).exists() or bool(os.environ.get("GLOBAL_LLM_CONFIG_B64"))

    # Global LLM Configurations (optional)
    # Load from global_llm_config.yaml if available
    # These can be used as default options for users
    GLOBAL_LLM_CONFIGS = load_global_llm_configs()

    # Router settings for Auto mode (LiteLLM Router load balancing)
    ROUTER_SETTINGS = load_router_settings()

    # Global Image Generation Configurations (optional)
    GLOBAL_IMAGE_GEN_CONFIGS = load_global_image_gen_configs()

    # Router settings for Image Generation Auto mode
    IMAGE_GEN_ROUTER_SETTINGS = load_image_gen_router_settings()

    # Virtual GLOBAL connection/model catalog. This is server-only metadata
    # derived from global_llm_config.yaml; GLOBAL keys are not stored in DB.
    from app.services.global_model_catalog import (
        materialize_global_model_catalog as _materialize_global_model_catalog,
    )

    GLOBAL_CONNECTIONS, GLOBAL_MODELS = _materialize_global_model_catalog(
        chat_configs=GLOBAL_LLM_CONFIGS,
        image_configs=GLOBAL_IMAGE_GEN_CONFIGS,
    )
    del _materialize_global_model_catalog

    # OpenRouter Integration settings (optional)
    OPENROUTER_INTEGRATION_SETTINGS = load_openrouter_integration_settings()

    # Chonkie Configuration | Edit this to your needs
    EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL")
    EMBEDDING_BASE_URL = resolve_embedding_base_url()
    # Azure OpenAI credentials from environment variables
    AZURE_OPENAI_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT")
    AZURE_OPENAI_API_KEY = os.getenv("AZURE_OPENAI_API_KEY")

    # Pass provider-specific settings to embeddings when supported.
    embedding_kwargs = build_embedding_kwargs(embedding_model=EMBEDDING_MODEL)

    embedding_model_instance = AutoEmbeddings.get_embeddings(
        EMBEDDING_MODEL,
        **embedding_kwargs,
    )
    is_local_embedding_model = "://" not in (EMBEDDING_MODEL or "")
    chunker_instance = RecursiveChunker(
        chunk_size=getattr(embedding_model_instance, "max_seq_length", 512)
    )
    code_chunker_instance = CodeChunker(
        chunk_size=getattr(embedding_model_instance, "max_seq_length", 512)
    )

    # Reranker's Configuration | Pinecone, Cohere etc. Read more at https://github.com/AnswerDotAI/rerankers?tab=readme-ov-file#usage
    RERANKERS_ENABLED = os.getenv("RERANKERS_ENABLED", "FALSE").upper() == "TRUE"
    if RERANKERS_ENABLED:
        RERANKERS_MODEL_NAME = os.getenv("RERANKERS_MODEL_NAME")
        RERANKERS_MODEL_TYPE = os.getenv("RERANKERS_MODEL_TYPE")
        reranker_instance = Reranker(
            model_name=RERANKERS_MODEL_NAME,
            model_type=RERANKERS_MODEL_TYPE,
        )
    else:
        reranker_instance = None

    # OAuth JWT
    SECRET_KEY = os.getenv("SECRET_KEY")

    # JWT Token Lifetimes
    ACCESS_TOKEN_LIFETIME_SECONDS = int(
        os.getenv("ACCESS_TOKEN_LIFETIME_SECONDS", str(60 * 60))  # 60 minutes
    )
    MIN_ISSUED_AT = int(os.getenv("MIN_ISSUED_AT", "0"))
    REFRESH_TOKEN_LIFETIME_SECONDS = int(
        os.getenv("REFRESH_TOKEN_LIFETIME_SECONDS", str(14 * 24 * 60 * 60))  # 2 weeks
    )
    REFRESH_ROTATION_GRACE_SECONDS = int(
        os.getenv("REFRESH_ROTATION_GRACE_SECONDS", "45")
    )
    REFRESH_ABSOLUTE_LIFETIME_SECONDS = int(
        os.getenv("REFRESH_ABSOLUTE_LIFETIME_SECONDS", str(30 * 24 * 60 * 60))
    )
    if REFRESH_ABSOLUTE_LIFETIME_SECONDS <= REFRESH_TOKEN_LIFETIME_SECONDS:
        raise ValueError(
            "REFRESH_ABSOLUTE_LIFETIME_SECONDS must be greater than "
            "REFRESH_TOKEN_LIFETIME_SECONDS so the sliding inactivity window works."
        )
    SESSION_COOKIE_NAME = os.getenv("SESSION_COOKIE_NAME", "nowing_session")
    REFRESH_COOKIE_NAME = os.getenv("REFRESH_COOKIE_NAME", "nowing_refresh")
    SESSION_COOKIE_SECURE_POLICY = os.getenv(
        "SESSION_COOKIE_SECURE_POLICY", "auto"
    ).lower()
    SESSION_COOKIE_SAMESITE = os.getenv("SESSION_COOKIE_SAMESITE", "lax").lower()
    if SESSION_COOKIE_SAMESITE == "none":
        raise ValueError("SESSION_COOKIE_SAMESITE=none is not supported")
    COOKIE_DOMAIN = os.getenv("COOKIE_DOMAIN") or None
    CSRF_ALLOWED_ORIGINS = [
        origin.strip()
        for origin in os.getenv("CSRF_ALLOWED_ORIGINS", "").split(",")
        if origin.strip()
    ]
    _CSRF_ALLOW_LOOPBACK = os.getenv("CSRF_ALLOW_LOOPBACK", "").strip().lower()
    CSRF_ALLOW_LOOPBACK = _CSRF_ALLOW_LOOPBACK in {"1", "true", "yes"}
    _PAT_MAX_EXPIRY_DAYS = os.getenv("PAT_MAX_EXPIRY_DAYS", "").strip()
    PAT_MAX_EXPIRY_DAYS = int(_PAT_MAX_EXPIRY_DAYS) if _PAT_MAX_EXPIRY_DAYS else None

    # ETL Service
    ETL_SERVICE = os.getenv("ETL_SERVICE")

    if ETL_SERVICE == "UNSTRUCTURED":
        # Unstructured API Key
        UNSTRUCTURED_API_KEY = os.getenv("UNSTRUCTURED_API_KEY")

    elif ETL_SERVICE == "LLAMACLOUD":
        LLAMA_CLOUD_API_KEY = os.getenv("LLAMA_CLOUD_API_KEY")
        # Optional: Azure Document Intelligence accelerator for supported file types
        AZURE_DI_ENDPOINT = os.getenv("AZURE_DI_ENDPOINT")
        AZURE_DI_KEY = os.getenv("AZURE_DI_KEY")

    # ETL parse cache: reuse parser output for identical bytes across workspaces.
    ETL_CACHE_ENABLED = (
        os.getenv("ETL_CACHE_ENABLED", "false").strip().lower() == "true"
    )
    # Bump to invalidate every cached entry after a parser/behaviour change.
    ETL_CACHE_PARSER_VERSION = int(os.getenv("ETL_CACHE_PARSER_VERSION", "1"))
    ETL_CACHE_TTL_DAYS = int(os.getenv("ETL_CACHE_TTL_DAYS", "90"))
    ETL_CACHE_MAX_TOTAL_MB = int(os.getenv("ETL_CACHE_MAX_TOTAL_MB", "5120"))
    ETL_CACHE_EVICTION_BATCH = int(os.getenv("ETL_CACHE_EVICTION_BATCH", "500"))
    # Optional dedicated blob storage; unset reuses the main file_storage backend.
    ETL_CACHE_STORAGE_BACKEND = os.getenv("ETL_CACHE_STORAGE_BACKEND")
    ETL_CACHE_STORAGE_CONTAINER = os.getenv("ETL_CACHE_STORAGE_CONTAINER")
    ETL_CACHE_STORAGE_LOCAL_PATH = os.getenv("ETL_CACHE_STORAGE_LOCAL_PATH")

    # Embedding cache: reuse chunk+embedding output for identical markdown across
    # workspaces. Blobs share the ETL_CACHE_STORAGE_* backend.
    EMBEDDING_CACHE_ENABLED = (
        os.getenv("EMBEDDING_CACHE_ENABLED", "false").strip().lower() == "true"
    )
    # Bump to invalidate every cached embedding set after a chunker change.
    EMBEDDING_CACHE_CHUNKER_VERSION = int(
        os.getenv("EMBEDDING_CACHE_CHUNKER_VERSION", "1")
    )
    EMBEDDING_CACHE_TTL_DAYS = int(os.getenv("EMBEDDING_CACHE_TTL_DAYS", "90"))
    EMBEDDING_CACHE_MAX_TOTAL_MB = int(
        os.getenv("EMBEDDING_CACHE_MAX_TOTAL_MB", "5120")
    )
    EMBEDDING_CACHE_EVICTION_BATCH = int(
        os.getenv("EMBEDDING_CACHE_EVICTION_BATCH", "500")
    )

    # Incremental re-indexing: on document edits, keep chunk rows whose text is
    # unchanged (reusing their embeddings) and embed only new/changed chunks.
    # Kill switch -- disabling falls back to delete-all + full re-embed.
    CHUNK_RECONCILE_ENABLED = (
        os.getenv("CHUNK_RECONCILE_ENABLED", "true").strip().lower() == "true"
    )
    INDEXING_CHUNK_INSERT_BATCH_SIZE = int(
        os.getenv("INDEXING_CHUNK_INSERT_BATCH_SIZE", "200")
    )

    # Proxy provider selection. Maps to a ProxyProvider implementation registered
    # in app/utils/proxy/registry.py. Add new vendors there and switch via this var.
    PROXY_PROVIDER = os.getenv("PROXY_PROVIDER", "custom")

    # Proxy endpoint(s), shared across all providers — PROXY_PROVIDER selects how
    # they're interpreted, not a different env name. PROXY_URL is a single full
    # http://user:pass@host:port endpoint (used by every provider); e.g. DataImpulse
    # encodes country as a "__cr.<country>" username suffix that its provider parses
    # for geoip-match. PROXY_URLS is a comma-separated pool that the "custom" provider
    # rotates client-side (server-side-rotating gateways ignore it). Leave unset to
    # disable proxying.
    PROXY_URL = os.getenv("PROXY_URL")
    PROXY_URLS = os.getenv("PROXY_URLS")

    # =====================================================================
    # Phase 3d — Captcha solving (reCAPTCHA v2/v3, hCaptcha, v2-Enterprise) via
    # the in-house solver seam (app/utils/captcha/solvers.py).
    # The LAST-resort bypass tier: only fires on the StealthyFetcher browser
    # tier, only when a sitekey is detected, and only when explicitly enabled.
    # Cloudflare Turnstile is already handled free in-framework (03a), NOT here.
    # One app-wide config (mirrors the single PROXY_PROVIDER model) — no
    # per-connector config. Off by default => zero solve attempts, zero cost.
    # Solving may violate a target site's ToS; treat as opt-in/owner-acknowledged
    # and public-data only (no logged-in bypass).
    # =====================================================================
    CAPTCHA_SOLVING_ENABLED = (
        os.getenv("CAPTCHA_SOLVING_ENABLED", "FALSE").upper() == "TRUE"
    )
    # Solver vendor. "capsolver" (AI-native, fastest on reCAPTCHA-Enterprise) and
    # "2captcha" have in-house clients today; anticaptcha / capmonster are added
    # progressively in solvers._PROVIDERS.
    CAPTCHA_SOLVER_PROVIDER = os.getenv("CAPTCHA_SOLVER_PROVIDER", "capsolver")
    CAPTCHA_SOLVER_API_KEY = os.getenv("CAPTCHA_SOLVER_API_KEY")
    # Per-URL solve cap so one hostile page can't burn unbounded solver credit.
    CAPTCHA_MAX_ATTEMPTS_PER_URL = int(os.getenv("CAPTCHA_MAX_ATTEMPTS_PER_URL", "1"))
    # Abort a single solve after this many seconds (solves take 10-60s).
    CAPTCHA_SOLVE_TIMEOUT_S = int(os.getenv("CAPTCHA_SOLVE_TIMEOUT_S", "120"))
    # Default captcha type when detection is ambiguous: v2 | v3 | hcaptcha.
    CAPTCHA_TYPE_DEFAULT = os.getenv("CAPTCHA_TYPE_DEFAULT", "v2")
    # reCAPTCHA v3 tuning (only used for v3 challenges).
    CAPTCHA_V3_MIN_SCORE = float(os.getenv("CAPTCHA_V3_MIN_SCORE", "0.7"))
    CAPTCHA_V3_ACTION = os.getenv("CAPTCHA_V3_ACTION", "verify")

    # =====================================================================
    # Phase 3e — Stealth hardening (Slice A): runtime/config-level levers
    # layered on Scrapling's patchright-Chromium StealthyFetcher tier. All are
    # consumed by the centralized kwargs builder in
    # app/proprietary/web_crawler/stealth.py (proprietary — bypass tuning), which
    # is the single source of truth imported by the crawler AND the 03f harness
    # (no test-vs-prod drift). Defaults preserve today's behavior /
    # introduce no crawl-speed regression. See plans/backend/03e-stealth-hardening.md.
    # =====================================================================
    # Map the active proxy provider's exit region (ProxyProvider.get_location())
    # -> browser locale/timezone so the fingerprint coheres with the proxy exit
    # geo. No exit-IP lookup (zero added latency); unknown/empty region => skip.
    CRAWL_GEOIP_MATCH_ENABLED = (
        os.getenv("CRAWL_GEOIP_MATCH_ENABLED", "FALSE").upper() == "TRUE"
    )
    # Force WebRTC to respect the proxy (prevents real-local-IP leak). Cheap +
    # safe => default TRUE.
    CRAWL_BLOCK_WEBRTC = os.getenv("CRAWL_BLOCK_WEBRTC", "TRUE").upper() == "TRUE"
    # Random canvas noise. An UNSTABLE canvas hash is itself a fingerprint tell,
    # so default FALSE (opt-in + 03f-validated). See 03e §2.
    CRAWL_HIDE_CANVAS = os.getenv("CRAWL_HIDE_CANVAS", "FALSE").upper() == "TRUE"
    # Set a Google referer so the first hit looks like organic arrival.
    CRAWL_GOOGLE_SEARCH_REFERER = (
        os.getenv("CRAWL_GOOGLE_SEARCH_REFERER", "TRUE").upper() == "TRUE"
    )
    # Route DNS via Cloudflare DoH (anti DNS-leak behind proxies). Adds a DNS
    # round-trip => default FALSE to honor the "no speed regression" bar; flip on
    # when leak-safety outweighs the marginal latency.
    CRAWL_DNS_OVER_HTTPS = os.getenv("CRAWL_DNS_OVER_HTTPS", "FALSE").upper() == "TRUE"
    # Promises an Xvfb display so the browser can run headful (TikTok's profile
    # feed is empty to headless Chromium). Off keeps every browser headless.
    CRAWL_HEADED_XVFB_ENABLED = (
        os.getenv("CRAWL_HEADED_XVFB_ENABLED", "FALSE").upper() == "TRUE"
    )

    # Litellm TTS Configuration
    TTS_SERVICE = os.getenv("TTS_SERVICE")
    TTS_SERVICE_API_BASE = os.getenv("TTS_SERVICE_API_BASE")
    TTS_SERVICE_API_KEY = os.getenv("TTS_SERVICE_API_KEY")

    # STT Configuration
    STT_SERVICE = os.getenv("STT_SERVICE")
    STT_SERVICE_API_BASE = os.getenv("STT_SERVICE_API_BASE")
    STT_SERVICE_API_KEY = os.getenv("STT_SERVICE_API_KEY")

    # Video presentation defaults
    VIDEO_PRESENTATION_MAX_SLIDES = int(
        os.getenv("VIDEO_PRESENTATION_MAX_SLIDES", "30")
    )
    VIDEO_PRESENTATION_FPS = int(os.getenv("VIDEO_PRESENTATION_FPS", "30"))
    VIDEO_PRESENTATION_DEFAULT_DURATION_IN_FRAMES = int(
        os.getenv("VIDEO_PRESENTATION_DEFAULT_DURATION_IN_FRAMES", "300")
    )

    # Canonical entity settings
    CANONICAL_EMBEDDING_OUTBOX_FAILURE_THRESHOLD = _env_int(
        "CANONICAL_EMBEDDING_OUTBOX_FAILURE_THRESHOLD", 5
    )

    # Signal detection (Story 21.1)
    SIGNAL_SCAN_MICROS_PER_SIGNAL = max(0, _env_int("SIGNAL_SCAN_MICROS_PER_SIGNAL", 0))
    LEAD_SCORING_MICROS_PER_CALL = max(0, _env_int("LEAD_SCORING_MICROS_PER_CALL", 0))
    CRUNCHBASE_API_KEY = os.getenv("CRUNCHBASE_API_KEY", "")
    NEWSAPI_KEY = os.getenv("NEWSAPI_KEY", "")
    SIGNAL_EXECUTIVE_MOVE_ENABLED = (
        os.getenv("SIGNAL_EXECUTIVE_MOVE_ENABLED", "FALSE").upper() == "TRUE"
    )
    SIGNAL_EVENT_RETENTION_DAYS = max(1, _env_int("SIGNAL_EVENT_RETENTION_DAYS", 90))

    # Contact enrichment (Story 21.3)
    CLEANLIST_API_KEY = os.getenv("CLEANLIST_API_KEY", "")
    BETTERCONTACT_API_KEY = os.getenv("BETTERCONTACT_API_KEY", "")
    CONTACT_ENRICHMENT_MICROS_PER_CONTACT = max(
        0, _env_int("CONTACT_ENRICHMENT_MICROS_PER_CONTACT", 0)
    )
    CONTACT_ENRICHMENT_CACHE_TTL_SECONDS = max(
        1, _env_int("CONTACT_ENRICHMENT_CACHE_TTL_SECONDS", 30 * 24 * 60 * 60)
    )
    CONTACT_ENRICHMENT_PRIMARY_PROVIDER = os.getenv(
        "CONTACT_ENRICHMENT_PRIMARY_PROVIDER", "cleanlist"
    ).strip().lower()
    CONTACT_ENRICHMENT_MAX_CONTACTS_PER_LEAD = max(
        1, _env_int("CONTACT_ENRICHMENT_MAX_CONTACTS_PER_LEAD", 5)
    )
    CONTACT_ENRICHMENT_REQUEST_TIMEOUT_SECONDS = max(
        1, _env_int("CONTACT_ENRICHMENT_REQUEST_TIMEOUT_SECONDS", 30)
    )
    CONTACT_ENRICHMENT_RETRY_ATTEMPTS = max(
        1, _env_int("CONTACT_ENRICHMENT_RETRY_ATTEMPTS", 3)
    )

    # CRM (Story 21.5)
    SALESFORCE_CLIENT_ID = os.getenv("SALESFORCE_CLIENT_ID", "")
    SALESFORCE_CLIENT_SECRET = os.getenv("SALESFORCE_CLIENT_SECRET", "")
    SALESFORCE_REDIRECT_URI = os.getenv("SALESFORCE_REDIRECT_URI", "")
    HUBSPOT_CLIENT_ID = os.getenv("HUBSPOT_CLIENT_ID", "")
    HUBSPOT_CLIENT_SECRET = os.getenv("HUBSPOT_CLIENT_SECRET", "")
    HUBSPOT_REDIRECT_URI = os.getenv("HUBSPOT_REDIRECT_URI", "")
    PIPEDRIVE_CLIENT_ID = os.getenv("PIPEDRIVE_CLIENT_ID", "")
    PIPEDRIVE_CLIENT_SECRET = os.getenv("PIPEDRIVE_CLIENT_SECRET", "")
    PIPEDRIVE_REDIRECT_URI = os.getenv("PIPEDRIVE_REDIRECT_URI", "")
    CRM_SYNC_DEDUP_ENABLED = (
        os.getenv("CRM_SYNC_DEDUP_ENABLED", "TRUE").upper() == "TRUE"
    )
    CRM_SYNC_WRITEBACK_ENABLED = (
        os.getenv("CRM_SYNC_WRITEBACK_ENABLED", "FALSE").upper() == "TRUE"
    )
    CRM_SYNC_BIDIRECTIONAL_ENABLED = (
        os.getenv("CRM_SYNC_BIDIRECTIONAL_ENABLED", "FALSE").upper() == "TRUE"
    )
    CRM_SYNC_BATCH_SIZE = max(1, _env_int("CRM_SYNC_BATCH_SIZE", 50))
    CRM_SYNC_TIMEOUT_SECONDS = max(1, _env_int("CRM_SYNC_TIMEOUT_SECONDS", 30))
    CRM_SYNC_TOKEN_REFRESH_LEEWAY_SECONDS = max(
        0, _env_int("CRM_SYNC_TOKEN_REFRESH_LEEWAY_SECONDS", 300)
    )
    )

    # Validation Checks
    # Check embedding dimension
    if (
        hasattr(embedding_model_instance, "dimension")
        and embedding_model_instance.dimension > 2000
    ):
        raise ValueError(
            f"Embedding dimension for Model: {EMBEDDING_MODEL} "
            f"has {embedding_model_instance.dimension} dimensions, which "
            f"exceeds the maximum of 2000 allowed by PGVector."
        )

    @classmethod
    def get_settings(cls):
        """Get all settings as a dictionary."""
        return {
            key: value
            for key, value in cls.__dict__.items()
            if not key.startswith("_") and not callable(value)
        }


# Create a config instance
config = Config()
