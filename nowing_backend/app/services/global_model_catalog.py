"""Materialize server-owned GLOBAL YAML configs and DB-managed rows as virtual connections/models."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.services.model_resolver import native_connection_from_config

if TYPE_CHECKING:
    from app.db import Connection, Model


def _base_model(config: dict[str, Any]) -> str | None:
    litellm_params = config.get("litellm_params") or {}
    if isinstance(litellm_params, dict):
        return litellm_params.get("base_model")
    return None


def _connection_key(conn: dict[str, Any]) -> tuple[Any, ...]:
    # Deliberately includes api_key because two operator-owned credentials for
    # the same provider/base can have different quota/rate limits upstream.
    return (
        conn.get("provider"),
        conn.get("base_url"),
        conn.get("api_key"),
        _freeze(conn.get("extra") or {}),
    )


def _freeze(value: Any) -> Any:
    if isinstance(value, dict):
        return tuple(sorted((key, _freeze(val)) for key, val in value.items()))
    if isinstance(value, list):
        return tuple(_freeze(item) for item in value)
    return value


def _catalog_metadata(config: dict[str, Any]) -> dict[str, Any]:
    return {
        "billing_tier": config.get("billing_tier", "free"),
        "quota_reserve_tokens": config.get("quota_reserve_tokens"),
        "rpm": config.get("rpm"),
        "tpm": config.get("tpm"),
        "anonymous_enabled": config.get("anonymous_enabled", False),
        "seo_enabled": config.get("seo_enabled", False),
        "seo_slug": config.get("seo_slug"),
        "input_cost_per_token": (config.get("litellm_params") or {}).get(
            "input_cost_per_token"
        )
        if isinstance(config.get("litellm_params"), dict)
        else None,
        "output_cost_per_token": (config.get("litellm_params") or {}).get(
            "output_cost_per_token"
        )
        if isinstance(config.get("litellm_params"), dict)
        else None,
        "is_planner": config.get("is_planner", False),
        "base_model": _base_model(config),
        "router_pool_eligible": config.get("router_pool_eligible", True),
    }


# Runtime ID space for managed DB-backed global entries.
# File-backed IDs count down from -1; managed IDs are far away to avoid collision.
_RUNTIME_ID_OFFSET = 1_000_000_000


def _managed_runtime_id(db_id: int) -> int:
    return -(_RUNTIME_ID_OFFSET + db_id)


def _model_catalog_for_runtime(model: Model) -> dict[str, Any]:
    """Build a catalog dict for the merged global catalog.

    Includes the DB id for admin lookup and per-token pricing for LiteLLM.
    """
    catalog = dict(model.catalog or {})
    catalog["db_model_id"] = model.id
    catalog["db_connection_id"] = model.connection_id
    catalog["admin_source"] = "managed"
    catalog.setdefault("router_pool_eligible", True)
    # Add per-1k fields for consumers that expect them.
    catalog["cost_per_1k_input_tokens"] = catalog.get("cost_per_1k_input_tokens")
    catalog["cost_per_1k_output_tokens"] = catalog.get("cost_per_1k_output_tokens")
    return catalog


def _connection_to_runtime(conn: Connection) -> dict[str, Any]:
    return {
        "id": _managed_runtime_id(conn.id),
        "provider": conn.provider,
        "base_url": conn.base_url,
        "api_key": conn.api_key,
        "extra": conn.extra or {},
        "scope": "GLOBAL",
        "enabled": conn.enabled,
        "source": "managed",
        "can_edit": True,
        "can_delete": True,
    }


def _model_to_runtime(
    conn: Connection, model: Model, connection_runtime_id: int
) -> dict[str, Any]:
    capabilities_override = model.capabilities_override or {}
    # Derive role from what the admin set; default to chat.
    role = "image_gen" if model.supports_image_generation else "chat"
    return {
        "id": _managed_runtime_id(model.id),
        "connection_id": connection_runtime_id,
        "model_id": model.model_id,
        "display_name": model.display_name or model.model_id,
        "source": "MANUAL",  # runtime code expects MANUAL/DISCOVERED.
        "supports_chat": model.supports_chat,
        "max_input_tokens": model.max_input_tokens,
        "supports_image_input": model.supports_image_input,
        "supports_tools": model.supports_tools,
        "supports_image_generation": model.supports_image_generation,
        "capabilities_override": capabilities_override,
        "enabled": model.enabled and conn.enabled,
        "billing_tier": model.billing_tier or "free",
        "catalog": _model_catalog_for_runtime(model),
        "role": role,
    }


async def _merge_db_global_models(
    connections: list[dict[str, Any]],
    models: list[dict[str, Any]],
    session: AsyncSession | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Append enabled DB-backed GLOBAL rows to the in-memory catalog."""
    from app.db import Connection, ConnectionScope, async_session_maker

    own_session = session is None
    if own_session:
        # ponytail: creating a one-off session for sync call-sites.
        session = async_session_maker()
    try:
        result = await session.execute(
            select(Connection)
            .options(selectinload(Connection.models))
            .where(
                Connection.scope == ConnectionScope.GLOBAL,
                Connection.workspace_id.is_(None),
                Connection.user_id.is_(None),
            )
            .order_by(Connection.id)
        )
        db_connections = list(result.scalars().all())

        for conn in db_connections:
            if not conn.enabled:
                continue
            conn_runtime_id = _managed_runtime_id(conn.id)
            connections.append(_connection_to_runtime(conn))
            for model in conn.models:
                if not model.enabled:
                    continue
                models.append(_model_to_runtime(conn, model, conn_runtime_id))

        if own_session:
            await session.commit()
        return connections, models
    except Exception:
        if own_session:
            await session.rollback()
        raise
    finally:
        if own_session:
            await session.close()


def _source_for_config(config: dict[str, Any]) -> str:
    """Distinguish static YAML files from dynamic OpenRouter configs."""
    if (
        config.get("is_openrouter")
        or str(config.get("provider")).lower() == "openrouter"
    ):
        return "config"
    return "file"


def materialize_global_model_catalog(
    *,
    chat_configs: list[dict[str, Any]],
    image_configs: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    connections: list[dict[str, Any]] = []
    models: list[dict[str, Any]] = []
    connection_id_by_key: dict[tuple[Any, ...], int] = {}
    next_connection_id = -1

    def add_config(config: dict[str, Any], role: str) -> None:
        nonlocal next_connection_id
        if not config.get("id") or not config.get("model_name"):
            return
        source = _source_for_config(config)
        conn = native_connection_from_config(config)
        conn["scope"] = "GLOBAL"
        conn["enabled"] = True
        conn["source"] = source
        conn["can_edit"] = False
        conn["can_delete"] = False
        key = _connection_key(conn)
        connection_id = connection_id_by_key.get(key)
        if connection_id is None:
            connection_id = next_connection_id
            next_connection_id -= 1
            connection_id_by_key[key] = connection_id
            connections.append(
                {
                    "id": connection_id,
                    **conn,
                }
            )

        catalog = _catalog_metadata(config)
        catalog["admin_source"] = source
        model_id = int(config["id"])
        models.append(
            {
                "id": model_id,
                "connection_id": connection_id,
                "model_id": config["model_name"],
                "display_name": config.get("name") or config["model_name"],
                "source": "MANUAL",
                "supports_chat": role == "chat",
                "max_input_tokens": config.get("max_input_tokens"),
                "supports_image_input": (
                    role == "chat" and bool(config.get("supports_image_input"))
                ),
                "supports_tools": bool(config.get("supports_tools", False)),
                "supports_image_generation": role == "image_gen",
                "capabilities_override": {},
                "enabled": True,
                "billing_tier": config.get("billing_tier", "free"),
                "catalog": catalog,
                "role": role,
            }
        )

    for cfg in chat_configs:
        if cfg.get("is_auto_mode"):
            continue
        add_config(cfg, "chat")
    for cfg in image_configs:
        if cfg.get("is_auto_mode"):
            continue
        add_config(cfg, "image_gen")

    # Each virtual connection is server-only. Callers that serialize these
    # must strip api_key before returning data to clients.
    return connections, models


async def refresh_global_model_catalog(
    session: AsyncSession | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Rebuild the in-memory global catalog from YAML/env, OpenRouter, and DB.

    This is the single post-mutation refresh point. Callers must hold any
    required locks before calling.
    """
    from app.config import config

    connections, models = materialize_global_model_catalog(
        chat_configs=getattr(config, "GLOBAL_LLM_CONFIGS", []),
        image_configs=getattr(config, "GLOBAL_IMAGE_GEN_CONFIGS", []),
    )
    connections, models = await _merge_db_global_models(connections, models, session)
    config.GLOBAL_CONNECTIONS = connections
    config.GLOBAL_MODELS = models
    return connections, models


__all__ = [
    "materialize_global_model_catalog",
    "refresh_global_model_catalog",
]
