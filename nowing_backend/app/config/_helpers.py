"""Config helper functions and environment readers."""

from __future__ import annotations

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
from dotenv import load_dotenv

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
    except Exception:
        logger.warning("Failed to read global_llm_config.yaml", exc_info=True)
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
        except Exception:
            logger.warning("Failed to decode GLOBAL_LLM_CONFIG_B64", exc_info=True)

    from app.config import BASE_DIR
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
                    logger.warning(
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
        except Exception:
            logger.warning("Failed to score global LLM configs", exc_info=True)

        # Planner LLM is a singleton role. If an operator accidentally
        # marks multiple configs ``is_planner: true``, only the first one
        # is used at runtime — surface the others at startup so the
        # mistake is caught before traffic, not silently buried.
        planner_cfgs = [c for c in configs if c.get("is_planner") is True]
        if len(planner_cfgs) > 1:
            extra_ids = [c.get("id") for c in planner_cfgs[1:]]
            logger.warning("Warning: Multiple global LLM configs marked is_planner=true "
                f"(ids {[c.get('id') for c in planner_cfgs]}); using id "
                f"{planner_cfgs[0].get('id')} and ignoring {extra_ids}")

        return configs
    except Exception:
        logger.warning("Failed to load global LLM configs", exc_info=True)
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
    except Exception:
        logger.warning("Failed to load router settings", exc_info=True)
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
    except Exception:
        logger.warning("Failed to load global image generation configs", exc_info=True)
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
    except Exception:
        logger.warning("Failed to load image generation router settings", exc_info=True)
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
            logger.warning("Warning: openrouter_integration.billing_tier is deprecated; "
                "tier is now derived per model from OpenRouter data "
                "(':free' suffix or zero pricing). Remove this key.")

        if "anonymous_enabled" in settings:
            logger.warning("Warning: openrouter_integration.anonymous_enabled is "
                "deprecated; use anonymous_enabled_paid and/or "
                "anonymous_enabled_free instead. Both new flags have been "
                "seeded from the legacy value for back-compat.")
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
    except Exception:
        logger.warning("Failed to load OpenRouter integration settings", exc_info=True)
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
            from app.config import config
            config.GLOBAL_LLM_CONFIGS.extend(new_configs)
            free_count = sum(1 for c in new_configs if c.get("billing_tier") == "free")
            premium_count = sum(
                1 for c in new_configs if c.get("billing_tier") == "premium"
            )
            logger.info(f"Info: OpenRouter integration added {len(new_configs)} models "
                f"(free={free_count}, premium={premium_count})")
        else:
            logger.info("Info: OpenRouter integration enabled but no models fetched")

        # Image generation emissions reuse the catalogue already cached by
        # ``service.initialize``
        # so we don't make additional network calls here.
        if settings.get("image_generation_enabled"):
            try:
                image_configs = service.get_image_generation_configs()
                if image_configs:
                    from app.config import config
                    config.GLOBAL_IMAGE_GEN_CONFIGS.extend(image_configs)
                    logger.info(f"Info: OpenRouter integration added {len(image_configs)} "
                        f"image-generation models")
            except Exception:
                logger.warning("Failed to inject OpenRouter image-gen configs", exc_info=True)

        # Global catalog refresh is intentionally deferred to the async
        # lifespan so DB-managed GLOBAL rows can be merged.
        pass
    except Exception:
        logger.warning("Failed to initialize OpenRouter integration", exc_info=True)


def materialize_global_configs():
    from app.services.global_model_catalog import materialize_global_model_catalog

    return materialize_global_model_catalog(
        chat_configs=getattr(__import__('app.config', fromlist=['config']).config, 'GLOBAL_LLM_CONFIGS', []),
        image_configs=getattr(__import__('app.config', fromlist=['config']).config, 'GLOBAL_IMAGE_GEN_CONFIGS', []),
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
                    getattr(__import__('app.config', fromlist=['config']).config, 'GLOBAL_LLM_CONFIGS', []),
                    getattr(__import__('app.config', fromlist=['config']).config, 'ROUTER_SETTINGS', []),
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
    except Exception:
        logger.warning("Failed to register LiteLLM pricing", exc_info=True)


def initialize_llm_router():
    """
    Initialize the LLM Router service for Auto mode.
    This should be called during application startup, AFTER
    initialize_openrouter_integration() so dynamic models are included.
    Uses config.GLOBAL_LLM_CONFIGS (in-memory) which includes both
    static YAML configs and dynamic OpenRouter models.
    """
    from app.config import config
    all_configs = config.GLOBAL_LLM_CONFIGS
    # Reuse the router settings already parsed at Config construction instead
    # of re-reading the YAML here.
    router_settings = config.ROUTER_SETTINGS

    if not all_configs:
        logger.info("Info: No global LLM configs found; global Auto pool is unavailable. "
            "Auto can still use enabled BYOK models.")
        return

    try:
        from app.services.llm_router_service import LLMRouterService

        LLMRouterService.initialize(all_configs, router_settings)
        logger.info(f"Info: LLM Router initialized with {len(all_configs)} models "
            f"(strategy: {router_settings.get('routing_strategy', 'usage-based-routing')})")
    except Exception:
        logger.warning("Failed to initialize LLM Router", exc_info=True)


def initialize_image_gen_router():
    """
    Initialize the Image Generation Router service for Auto mode.
    This should be called during application startup.
    """
    image_gen_configs = load_global_image_gen_configs()
    # Reuse the router settings already parsed at Config construction. The
    from app.config import config
    # *configs* list is intentionally re-read from YAML (it must exclude the
    # OpenRouter-injected dynamic models held in config.GLOBAL_IMAGE_GEN_CONFIGS).
    router_settings = config.IMAGE_GEN_ROUTER_SETTINGS

    if not image_gen_configs:
        logger.warning(
            "Info: No global image generation configs found, "
            "Image Generation Auto mode will not be available"
        )
        return

    try:
        from app.services.image_gen_router_service import ImageGenRouterService

        ImageGenRouterService.initialize(image_gen_configs, router_settings)
        logger.info(f"Info: Image Generation Router initialized with {len(image_gen_configs)} models "
            f"(strategy: {router_settings.get('routing_strategy', 'usage-based-routing')})")
    except Exception:
        logger.warning("Failed to initialize Image Generation Router", exc_info=True)


