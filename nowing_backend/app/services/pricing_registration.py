"""
Pricing registration with LiteLLM.

Many models reach our LiteLLM callback without LiteLLM knowing their
per-token cost — namely:

* The ~300 dynamic OpenRouter deployments (their pricing only lives on
  OpenRouter's ``/api/v1/models`` payload, never in LiteLLM's published
  pricing table).
* Static YAML deployments whose ``base_model`` name is operator-defined
  (e.g. custom Azure deployment names like ``gpt-5.4``) and therefore
  not in LiteLLM's table either.

Without registration, ``kwargs["response_cost"]`` is 0 for those calls
and the user gets billed nothing — a fail-safe but wrong answer for a
cost-based credit system. This module runs once at startup, after the
OpenRouter integration has fetched its catalogue, and registers each
known model's pricing with ``litellm.register_model()`` under multiple
plausible alias keys (LiteLLM's cost lookup may use any of them
depending on whether the call went through the Router, ChatLiteLLM,
or a direct ``acompletion``).

Operators who run a custom Azure deployment whose ``base_model`` name
isn't in LiteLLM's table can declare per-token pricing inline in
``global_llm_config.yaml`` via ``input_cost_per_token`` and
``output_cost_per_token`` (USD per token, e.g. ``0.000002``). Without
that declaration the model's calls debit 0 — never overbilled.
"""

from __future__ import annotations

import logging
from typing import Any

import litellm

from app.services.provider_registry import spec_for

logger = logging.getLogger(__name__)


def _safe_float(value: Any) -> float:
    """Return ``float(value)`` if it parses to a positive number, else 0.0."""
    if value is None:
        return 0.0
    try:
        f = float(value)
    except (TypeError, ValueError):
        return 0.0
    return f if f > 0 else 0.0


def _alias_set_for_openrouter(model_id: str) -> list[str]:
    """Return the alias keys to register an OpenRouter model under.

    LiteLLM's cost-callback lookup key varies by call path:
    - Router with ``model="openrouter/X"`` → kwargs["model"] is
      typically ``openrouter/X``.
    - LiteLLM's own provider routing may strip the prefix and pass the
      bare ``X`` to the cost-table lookup.
    Registering under both keeps the lookup hermetic regardless of
    which path the call took.
    """
    aliases = [f"openrouter/{model_id}", model_id]
    return list(dict.fromkeys(a for a in aliases if a))


def _alias_set_for_yaml(provider: str, model_name: str, base_model: str) -> list[str]:
    """Return the alias keys to register a static YAML deployment under.

    Same reasoning as the OpenRouter set: cover the bare ``base_model``,
    the ``<provider>/<model>`` form LiteLLM Router constructs, and the
    bare ``model_name`` because callbacks sometimes see whichever was
    configured first.
    """
    provider_lower = (provider or "").lower()
    aliases: list[str] = []
    if base_model:
        aliases.append(base_model)
    if provider_lower and base_model:
        aliases.append(f"{provider_lower}/{base_model}")
    if model_name and model_name != base_model:
        aliases.append(model_name)
    if provider_lower and model_name and model_name != base_model:
        aliases.append(f"{provider_lower}/{model_name}")
    # Azure deployments often surface as "azure/<name>"; normalise the
    # ``azure_openai`` provider slug to the LiteLLM-canonical ``azure``.
    if provider_lower == "azure_openai":
        if base_model:
            aliases.append(f"azure/{base_model}")
        if model_name and model_name != base_model:
            aliases.append(f"azure/{model_name}")
    return list(dict.fromkeys(a for a in aliases if a))


def _register(
    aliases: list[str],
    *,
    input_cost: float,
    output_cost: float,
    provider: str,
    mode: str = "chat",
) -> int:
    """Register a single pricing entry under every alias in ``aliases``.

    Returns the count of aliases successfully registered.
    """
    payload: dict[str, dict[str, Any]] = {}
    for alias in aliases:
        payload[alias] = {
            "input_cost_per_token": input_cost,
            "output_cost_per_token": output_cost,
            "litellm_provider": provider,
            "mode": mode,
        }
    if not payload:
        return 0
    try:
        litellm.register_model(payload)
    except Exception as exc:
        logger.warning(
            "[PricingRegistration] register_model failed for aliases=%s: %s",
            aliases,
            exc,
        )
        return 0
    return len(payload)


def _register_chat_shape_configs(
    configs: list[dict],
    *,
    or_pricing: dict[str, dict[str, str]],
    label: str,
    mode: str = "chat",
) -> tuple[int, int, int, list[str]]:
    """Common loop that registers per-token pricing for a list of token-shaped
    configs (chat, vision, or image-generation — all use ``input_cost_per_token`` /
    ``output_cost_per_token``; the ``mode`` distinguishes the LiteLLM cost map
    entry).

    Returns ``(registered_models, registered_aliases, skipped, sample_keys)``.
    """
    registered_models = 0
    registered_aliases = 0
    skipped_no_pricing = 0
    sample_keys: list[str] = []

    for cfg in configs:
        provider = str(cfg.get("provider") or cfg.get("litellm_provider") or "").lower()
        model_name = str(cfg.get("model_name") or "").strip()
        litellm_params = cfg.get("litellm_params") or {}
        base_model = str(litellm_params.get("base_model") or model_name).strip()

        if provider == "openrouter":
            # OpenRouter raw pricing is only trustworthy for chat/vision models
            # where prompt/completion are per-token. Image-gen models on
            # OpenRouter are billed per-image via response_cost, so we only
            # register them when the operator declares per-token pricing inline.
            entry = or_pricing.get(model_name) if mode != "image_generation" else None
            if entry:
                input_cost = _safe_float(entry.get("prompt"))
                output_cost = _safe_float(entry.get("completion"))
            else:
                # Some dynamically materialized configs can carry pricing
                # inline when the raw OpenRouter cache has no matching entry.
                input_cost = _safe_float(cfg.get("input_cost_per_token"))
                output_cost = _safe_float(cfg.get("output_cost_per_token"))
            if input_cost == 0.0 and output_cost == 0.0:
                skipped_no_pricing += 1
                continue
            aliases = _alias_set_for_openrouter(model_name)
            litellm_provider = spec_for("openrouter").litellm_prefix or "openrouter"
            count = _register(
                aliases,
                input_cost=input_cost,
                output_cost=output_cost,
                provider=litellm_provider,
                mode=mode,
            )
            if count > 0:
                registered_models += 1
                registered_aliases += count
                if len(sample_keys) < 6:
                    sample_keys.extend(aliases[:2])
            continue

        input_cost = _safe_float(
            cfg.get("input_cost_per_token")
            or litellm_params.get("input_cost_per_token")
        )
        output_cost = _safe_float(
            cfg.get("output_cost_per_token")
            or litellm_params.get("output_cost_per_token")
        )
        if input_cost == 0.0 and output_cost == 0.0:
            skipped_no_pricing += 1
            continue
        aliases = _alias_set_for_yaml(provider, model_name, base_model)
        litellm_provider = spec_for(provider).litellm_prefix or provider or "openai"
        count = _register(
            aliases,
            input_cost=input_cost,
            output_cost=output_cost,
            provider=litellm_provider,
            mode=mode,
        )
        if count > 0:
            registered_models += 1
            registered_aliases += count
            if len(sample_keys) < 6:
                sample_keys.extend(aliases[:2])

    logger.info(
        "[PricingRegistration:%s] registered pricing for %d models (%d aliases); "
        "%d configs had no pricing data; sample registered keys=%s",
        label,
        registered_models,
        registered_aliases,
        skipped_no_pricing,
        sample_keys,
    )
    return registered_models, registered_aliases, skipped_no_pricing, sample_keys


def register_pricing_from_global_configs() -> None:
    """Register pricing for every known LLM deployment with LiteLLM.

    Walks ``config.GLOBAL_LLM_CONFIGS`` (chat/vision) and
    ``config.GLOBAL_IMAGE_GEN_CONFIGS`` (image generation) and registers
    per-token pricing for every config that declares it, so calls in every
    mode can resolve cost from the registered LiteLLM cost map:

    1. ``OPENROUTER``: pulls the cached raw pricing from
       ``OpenRouterIntegrationService`` (populated during its own
       startup fetch) and converts the per-token strings to floats. For
       configs that carry pricing inline (``input_cost_per_token`` /
       ``output_cost_per_token`` set on the cfg itself) we fall back to
       those values when the OR cache misses the model.
    2. Anything else: looks for operator-declared
       ``input_cost_per_token`` / ``output_cost_per_token`` on the YAML
       config block (top-level or nested under ``litellm_params``).

    Image-generation models are registered with ``mode="image_generation"``
    when they declare per-token pricing. Calls without a resolvable pair of
    costs are skipped, not registered with zeros — operators who forget
    pricing get a "$0 debit" warning in ``TokenTrackingCallback`` rather
    than silently overwriting any pricing LiteLLM might know natively.
    """
    from app.config import config as app_config

    chat_configs: list[dict] = list(getattr(app_config, "GLOBAL_LLM_CONFIGS", []) or [])
    image_configs: list[dict] = list(
        getattr(app_config, "GLOBAL_IMAGE_GEN_CONFIGS", []) or []
    )
    if not chat_configs and not image_configs:
        logger.info("[PricingRegistration] no global configs to register")
        return

    or_pricing: dict[str, dict[str, str]] = {}
    try:
        from app.services.openrouter_integration_service import (
            OpenRouterIntegrationService,
        )

        if OpenRouterIntegrationService.is_initialized():
            or_pricing = OpenRouterIntegrationService.get_instance().get_raw_pricing()
    except Exception as exc:
        logger.debug(
            "[PricingRegistration] OpenRouter pricing not available yet: %s", exc
        )

    if chat_configs:
        _register_chat_shape_configs(chat_configs, or_pricing=or_pricing, label="chat")
    if image_configs:
        _register_chat_shape_configs(
            image_configs,
            or_pricing=or_pricing,
            label="image",
            mode="image_generation",
        )
