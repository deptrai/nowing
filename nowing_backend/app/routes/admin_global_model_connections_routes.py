"""Platform-admin routes for managing GLOBAL DB-backed model connections.

These routes are intentionally separated from the regular workspace/user
``/model-connections`` namespace.  They require a superuser session and use
``ConnectionScope.GLOBAL`` rows that do not belong to any workspace or user.
"""

from __future__ import annotations

import logging
import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.auth.context import AuthContext
from app.config import config, refresh_global_model_catalog
from app.db import Connection, ConnectionScope, Model, ModelSource, get_async_session
from app.schemas import VerifyConnectionResponse
from app.schemas.admin_global_model_connections import (
    AdminGlobalConnectionCreate,
    AdminGlobalConnectionRead,
    AdminGlobalConnectionUpdate,
    AdminGlobalModelPricing,
    AdminGlobalModelRead,
    AdminGlobalModelsBulkUpdate,
    AdminGlobalModelSelection,
    AdminGlobalModelTest,
    AdminGlobalModelTestPreview,
    AdminGlobalModelUpdate,
)
from app.services.model_connection_service import (
    ModelDiscoveryError,
    derive_capabilities,
    discover_models,
    test_model,
)
from app.users import require_superuser

router = APIRouter(prefix="/admin/global-model-connections")
logger = logging.getLogger(__name__)


# Runtime ID space for managed DB-backed global entries.
# Negative so they live in the same namespace as file-backed global entries,
# and large enough to avoid collision with the file-backed counter that starts
# at -1 and decrements.  Catalog stores the original DB id for admin lookup.
_RUNTIME_ID_OFFSET = 1_000_000_000


def _managed_runtime_id(db_id: int) -> int:
    return -(_RUNTIME_ID_OFFSET + db_id)


def _db_id_from_runtime(runtime_id: int) -> int | None:
    if runtime_id >= 0:
        return None
    db_id = -(runtime_id + _RUNTIME_ID_OFFSET)
    if db_id < 1:
        return None
    return db_id


def _model_pricing(model: Model) -> dict[str, Any]:
    catalog = model.catalog or {}
    return {
        "cost_per_1k_input_tokens": catalog.get("cost_per_1k_input_tokens"),
        "cost_per_1k_output_tokens": catalog.get("cost_per_1k_output_tokens"),
        "rpm": catalog.get("rpm"),
        "tpm": catalog.get("tpm"),
        "quality_score": catalog.get("quality_score"),
        "auto_pin_tier": catalog.get("auto_pin_tier"),
        "router_pool_eligible": catalog.get("router_pool_eligible", True),
        "base_model": catalog.get("base_model"),
    }


def _admin_model_read(model: Model) -> AdminGlobalModelRead:
    pricing = _model_pricing(model)
    # ponytail: preview/discover routes build unsaved Model objects; id is None.
    # Fall back to 0 so the response still validates as AdminGlobalModelRead.
    return AdminGlobalModelRead(
        id=model.id or 0,
        connection_id=model.connection_id or 0,
        model_id=model.model_id,
        display_name=model.display_name,
        source="managed",
        can_edit=model.id is not None,
        can_delete=model.id is not None,
        supports_chat=model.supports_chat,
        max_input_tokens=model.max_input_tokens,
        supports_image_input=model.supports_image_input,
        supports_tools=model.supports_tools,
        supports_image_generation=model.supports_image_generation,
        capabilities_override=model.capabilities_override or {},
        enabled=model.enabled,
        billing_tier=model.billing_tier,
        base_model=pricing.get("base_model"),
        catalog={k: v for k, v in (model.catalog or {}).items() if k != "api_key"},
        cost_per_1k_input_tokens=pricing.get("cost_per_1k_input_tokens"),
        cost_per_1k_output_tokens=pricing.get("cost_per_1k_output_tokens"),
        rpm=pricing.get("rpm"),
        tpm=pricing.get("tpm"),
        quality_score=pricing.get("quality_score"),
        auto_pin_tier=pricing.get("auto_pin_tier"),
        created_at=model.created_at,
    )


def _admin_connection_read(conn: Connection) -> AdminGlobalConnectionRead:
    return AdminGlobalConnectionRead(
        id=conn.id,
        provider=conn.provider,
        base_url=conn.base_url,
        api_key=None,
        extra=conn.extra or {},
        scope=conn.scope,
        workspace_id=conn.workspace_id,
        user_id=conn.user_id,
        enabled=conn.enabled,
        has_api_key=bool(conn.api_key),
        source="managed",
        can_edit=True,
        can_delete=True,
        models=[_admin_model_read(model) for model in conn.models],
        created_at=conn.created_at,
    )


def _apply_model_facts(model: Model, facts: dict[str, Any]) -> None:
    model.supports_chat = facts.get("supports_chat")
    model.max_input_tokens = facts.get("max_input_tokens")
    model.supports_image_input = facts.get("supports_image_input")
    model.supports_tools = facts.get("supports_tools")
    model.supports_image_generation = facts.get("supports_image_generation")


def _complete_selection_facts(
    conn: Connection, selection: AdminGlobalModelSelection
) -> dict[str, Any]:
    facts = selection.model_dump()
    derived = derive_capabilities(conn, selection.model_id.strip(), selection.metadata)
    for key, value in derived.items():
        if facts.get(key) is None:
            facts[key] = value
    return facts


def _selection_to_model(
    conn: Connection, selection: AdminGlobalModelSelection
) -> Model:
    model = Model(
        connection_id=conn.id,
        model_id=selection.model_id.strip(),
        display_name=selection.display_name,
        source=ModelSource.MANUAL,
        capabilities_override={},
        enabled=selection.enabled,
        catalog={},
        billing_tier=selection.billing_tier or "free",
    )
    _apply_model_facts(model, _complete_selection_facts(conn, selection))
    if selection.base_model:
        model.catalog = model.catalog or {}
        model.catalog["base_model"] = selection.base_model
    return model


def _pricing_to_catalog(model: Model, pricing: AdminGlobalModelPricing | None) -> None:
    if not pricing:
        return
    catalog = model.catalog or {}
    if pricing.cost_per_1k_input_tokens is not None:
        catalog["cost_per_1k_input_tokens"] = pricing.cost_per_1k_input_tokens
    if pricing.cost_per_1k_output_tokens is not None:
        catalog["cost_per_1k_output_tokens"] = pricing.cost_per_1k_output_tokens
    if pricing.rpm is not None:
        catalog["rpm"] = pricing.rpm
    if pricing.tpm is not None:
        catalog["tpm"] = pricing.tpm
    if pricing.quality_score is not None:
        catalog["quality_score"] = pricing.quality_score
    if pricing.auto_pin_tier is not None:
        catalog["auto_pin_tier"] = pricing.auto_pin_tier
    catalog["router_pool_eligible"] = pricing.router_pool_eligible
    # ponytail: stored as per-1k in catalog; registration normalizes to per-token.
    if pricing.cost_per_1k_input_tokens is not None:
        catalog["input_cost_per_token"] = pricing.cost_per_1k_input_tokens / 1000.0
    if pricing.cost_per_1k_output_tokens is not None:
        catalog["output_cost_per_token"] = pricing.cost_per_1k_output_tokens / 1000.0
    catalog["admin_source"] = "managed"
    if model.id is not None:
        catalog["db_model_id"] = model.id
    if model.connection_id is not None:
        catalog["db_connection_id"] = model.connection_id
    model.catalog = catalog


def _file_model_read(
    model: dict[str, Any], source: str = "file"
) -> AdminGlobalModelRead:
    catalog = model.get("catalog") or {}
    return AdminGlobalModelRead(
        id=model["id"],
        connection_id=model["connection_id"],
        model_id=model["model_id"],
        display_name=model.get("display_name"),
        source=source,
        can_edit=False,
        can_delete=False,
        supports_chat=model.get("supports_chat"),
        max_input_tokens=model.get("max_input_tokens"),
        supports_image_input=model.get("supports_image_input"),
        supports_tools=model.get("supports_tools"),
        supports_image_generation=model.get("supports_image_generation"),
        capabilities_override=model.get("capabilities_override") or {},
        enabled=model.get("enabled", True),
        billing_tier=model.get("billing_tier"),
        base_model=catalog.get("base_model"),
        catalog={k: v for k, v in catalog.items() if k != "api_key"},
        cost_per_1k_input_tokens=catalog.get("cost_per_1k_input_tokens"),
        cost_per_1k_output_tokens=catalog.get("cost_per_1k_output_tokens"),
        rpm=catalog.get("rpm"),
        tpm=catalog.get("tpm"),
        quality_score=catalog.get("quality_score"),
        auto_pin_tier=catalog.get("auto_pin_tier"),
    )


def _file_connection_read(conn: dict[str, Any]) -> AdminGlobalConnectionRead:
    models_by_id = {
        int(m.get("id")): m
        for m in config.GLOBAL_MODELS
        if m.get("connection_id") == conn.get("id")
    }
    source = conn.get("source", "file")
    return AdminGlobalConnectionRead(
        id=conn["id"],
        provider=conn["provider"],
        base_url=conn.get("base_url"),
        api_key=None,
        extra=conn.get("extra") or {},
        scope=conn.get("scope", "GLOBAL"),
        workspace_id=None,
        user_id=None,
        enabled=conn.get("enabled", True),
        has_api_key=bool(conn.get("api_key")),
        source=source,
        can_edit=False,
        can_delete=False,
        models=[_file_model_read(m, source=source) for m in models_by_id.values()],
    )


async def _load_managed_connection(
    session: AsyncSession, connection_id: int
) -> Connection:
    result = await session.execute(
        select(Connection)
        .options(selectinload(Connection.models))
        .where(
            Connection.id == connection_id,
            Connection.scope == ConnectionScope.GLOBAL,
            Connection.workspace_id.is_(None),
            Connection.user_id.is_(None),
        )
    )
    conn = result.scalars().first()
    if not conn:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Connection not found",
        )
    return conn


async def _list_managed_connections(session: AsyncSession) -> list[Connection]:
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
    return list(result.scalars().all())


def _log_admin_action(
    user_id: uuid.UUID,
    action: str,
    source: str,
    connection_id: int | None = None,
    model_id: int | None = None,
    provider: str | None = None,
    model_name: str | None = None,
    success: bool = True,
    refresh_outcome: str | None = None,
) -> None:
    logger.info(
        "[admin-global-model] actor=%s action=%s source=%s connection_id=%s model_id=%s "
        "provider=%s model_name=%s success=%s refresh=%s",
        user_id,
        action,
        source,
        connection_id,
        model_id,
        provider,
        model_name,
        success,
        refresh_outcome or "-",
    )


@router.get("", response_model=list[AdminGlobalConnectionRead])
async def list_global_model_connections(
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(require_superuser),
):
    managed = [
        _admin_connection_read(c) for c in await _list_managed_connections(session)
    ]
    # GLOBAL_CONNECTIONS also contains DB-managed entries after refresh;
    # only serialize file-backed (YAML/env/OpenRouter) rows here.
    file_backed = [
        _file_connection_read(c)
        for c in config.GLOBAL_CONNECTIONS
        if c.get("source") in ("file", "config")
    ]
    return managed + file_backed


@router.post("", response_model=AdminGlobalConnectionRead, status_code=201)
async def create_global_model_connection(
    data: AdminGlobalConnectionCreate,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(require_superuser),
):
    if not data.models:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least one model is required",
        )

    conn = Connection(
        provider=data.provider,
        base_url=data.base_url,
        api_key=data.api_key,
        extra=data.extra or {},
        scope=ConnectionScope.GLOBAL,
        enabled=data.enabled,
        workspace_id=None,
        user_id=None,
    )
    session.add(conn)
    await session.flush()

    seen_model_ids: set[str] = set()
    added_models: list[Model] = []
    for selection in data.models:
        model_id = selection.model_id.strip()
        if not model_id or model_id in seen_model_ids:
            continue
        seen_model_ids.add(model_id)
        model = _selection_to_model(conn, selection)
        _pricing_to_catalog(model, selection.pricing)
        session.add(model)
        added_models.append(model)

    if added_models:
        await session.flush()
        for model in added_models:
            catalog = model.catalog or {}
            catalog["db_model_id"] = model.id
            catalog["db_connection_id"] = conn.id
            model.catalog = catalog

    try:
        await session.commit()
        await refresh_global_model_catalog(session, rebuild_routers=True)
    except Exception as exc:
        await session.rollback()
        _log_admin_action(
            auth.user.id,
            "create",
            "managed",
            connection_id=conn.id,
            provider=data.provider,
            success=False,
            refresh_outcome=str(exc),
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Refresh failed after create: {exc}",
        ) from exc

    _log_admin_action(
        auth.user.id,
        "create",
        "managed",
        connection_id=conn.id,
        provider=data.provider,
        success=True,
        refresh_outcome="ok",
    )
    conn = await _load_managed_connection(session, conn.id)
    return _admin_connection_read(conn)


@router.put("/{connection_id}", response_model=AdminGlobalConnectionRead)
async def update_global_model_connection(
    connection_id: int,
    data: AdminGlobalConnectionUpdate,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(require_superuser),
):
    conn = await _load_managed_connection(session, connection_id)

    update_data = data.model_dump(exclude_unset=True)
    if "api_key" in update_data and update_data["api_key"] is None:
        # Empty string normalises to None for an explicit clear.
        conn.api_key = None
        del update_data["api_key"]

    for key, value in update_data.items():
        if key == "api_key" and value is not None:
            value = value or None
        if value is not None:
            setattr(conn, key, value)

    try:
        await session.commit()
        await refresh_global_model_catalog(session, rebuild_routers=True)
    except Exception as exc:
        await session.rollback()
        _log_admin_action(
            auth.user.id,
            "update",
            "managed",
            connection_id=connection_id,
            provider=conn.provider,
            success=False,
            refresh_outcome=str(exc),
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Refresh failed after update: {exc}",
        ) from exc

    _log_admin_action(
        auth.user.id,
        "update",
        "managed",
        connection_id=connection_id,
        provider=conn.provider,
        success=True,
        refresh_outcome="ok",
    )
    conn = await _load_managed_connection(session, connection_id)
    return _admin_connection_read(conn)


@router.delete("/{connection_id}", status_code=204)
async def delete_global_model_connection(
    connection_id: int,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(require_superuser),
):
    conn = await _load_managed_connection(session, connection_id)
    await session.delete(conn)
    try:
        await session.commit()
        await refresh_global_model_catalog(session, rebuild_routers=True)
    except Exception as exc:
        await session.rollback()
        _log_admin_action(
            auth.user.id,
            "delete",
            "managed",
            connection_id=connection_id,
            provider=conn.provider,
            success=False,
            refresh_outcome=str(exc),
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Refresh failed after delete: {exc}",
        ) from exc

    _log_admin_action(
        auth.user.id,
        "delete",
        "managed",
        connection_id=connection_id,
        provider=conn.provider,
        success=True,
        refresh_outcome="ok",
    )
    return None


@router.post("/discover-preview", response_model=list[AdminGlobalModelRead])
async def preview_global_connection_models(
    data: AdminGlobalConnectionCreate,
    auth: AuthContext = Depends(require_superuser),
):
    draft = Connection(
        provider=data.provider,
        base_url=data.base_url,
        api_key=data.api_key,
        extra=data.extra or {},
        scope=ConnectionScope.GLOBAL,
        enabled=data.enabled,
    )
    try:
        discovered = await discover_models(draft)
    except ModelDiscoveryError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    models: list[AdminGlobalModelRead] = []
    for item in discovered:
        facts = _complete_selection_facts(
            draft,
            AdminGlobalModelSelection(
                model_id=item["model_id"],
                display_name=item.get("display_name"),
                supports_chat=item.get("supports_chat", True),
                max_input_tokens=item.get("max_input_tokens"),
                supports_image_input=item.get("supports_image_input"),
                supports_tools=item.get("supports_tools"),
                supports_image_generation=item.get("supports_image_generation"),
                enabled=True,
                metadata=item.get("metadata") or item.get("catalog") or {},
            ),
        )
        model = Model(
            connection_id=draft.id,
            model_id=item["model_id"],
            display_name=item.get("display_name"),
            source=ModelSource.DISCOVERED,
            enabled=True,
        )
        _apply_model_facts(model, facts)
        models.append(_admin_model_read(model))
    return models


@router.post("/test-preview", response_model=VerifyConnectionResponse)
async def test_preview_global_model(
    data: AdminGlobalModelTestPreview,
    auth: AuthContext = Depends(require_superuser),
):
    model_id = data.model_id.strip()
    if not model_id:
        raise HTTPException(status_code=400, detail="model_id is required")

    draft = Connection(
        provider=data.provider,
        base_url=data.base_url,
        api_key=data.api_key,
        extra=data.extra or {},
        scope=ConnectionScope.GLOBAL,
        enabled=data.enabled,
    )
    model = Model(
        connection_id=0,
        model_id=model_id,
        source=ModelSource.MANUAL,
        enabled=True,
        capabilities_override={},
        catalog={},
    )
    result = await test_model(draft, model)
    return VerifyConnectionResponse(
        status=result.status, ok=result.ok, message=result.message
    )


@router.post("/{connection_id}/test", response_model=VerifyConnectionResponse)
async def test_saved_global_model(
    connection_id: int,
    body: AdminGlobalModelTest,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(require_superuser),
):
    conn = await _load_managed_connection(session, connection_id)
    model_id = body.model_id.strip()
    model = next((m for m in conn.models if m.model_id == model_id), None)
    if not model:
        raise HTTPException(status_code=404, detail="Model not found on connection")
    result = await test_model(conn, model)
    _log_admin_action(
        auth.user.id,
        "test",
        "managed",
        connection_id=connection_id,
        model_id=model.id,
        provider=conn.provider,
        model_name=model.model_id,
        success=result.ok,
    )
    return VerifyConnectionResponse(
        status=result.status, ok=result.ok, message=result.message
    )


@router.post("/{connection_id}/discover", response_model=list[AdminGlobalModelRead])
async def discover_saved_global_models(
    connection_id: int,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(require_superuser),
):
    conn = await _load_managed_connection(session, connection_id)
    try:
        discovered = await discover_models(conn)
    except ModelDiscoveryError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    models: list[AdminGlobalModelRead] = []
    for item in discovered:
        facts = _complete_selection_facts(
            conn,
            AdminGlobalModelSelection(
                model_id=item["model_id"],
                display_name=item.get("display_name"),
                supports_chat=item.get("supports_chat", True),
                max_input_tokens=item.get("max_input_tokens"),
                supports_image_input=item.get("supports_image_input"),
                supports_tools=item.get("supports_tools"),
                supports_image_generation=item.get("supports_image_generation"),
                enabled=True,
                metadata=item.get("metadata") or item.get("catalog") or {},
            ),
        )
        model = Model(
            connection_id=conn.id,
            model_id=item["model_id"],
            display_name=item.get("display_name"),
            source=ModelSource.DISCOVERED,
            enabled=True,
        )
        _apply_model_facts(model, facts)
        models.append(_admin_model_read(model))
    return models


@router.put("/models/{model_id}", response_model=AdminGlobalModelRead)
async def update_global_model(
    model_id: int,
    data: AdminGlobalModelUpdate,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(require_superuser),
):
    result = await session.execute(
        select(Model)
        .options(selectinload(Model.connection))
        .join(Connection)
        .where(
            Model.id == model_id,
            Connection.scope == ConnectionScope.GLOBAL,
            Connection.workspace_id.is_(None),
            Connection.user_id.is_(None),
        )
    )
    model = result.scalar_one_or_none()
    if not model:
        raise HTTPException(status_code=404, detail="Model not found")

    update_data = data.model_dump(exclude_unset=True)
    pricing = update_data.pop("pricing", None)
    base_model = update_data.pop("base_model", None)
    billing_tier = update_data.pop("billing_tier", None)
    if billing_tier is not None:
        model.billing_tier = billing_tier or "free"
    if base_model is not None:
        catalog = model.catalog or {}
        if base_model:
            catalog["base_model"] = base_model
        else:
            catalog.pop("base_model", None)
        model.catalog = catalog
    for key, value in update_data.items():
        if value is not None:
            setattr(model, key, value)
    if pricing:
        _pricing_to_catalog(model, data.pricing)

    provider = model.connection.provider if model.connection else None
    try:
        await session.commit()
        await refresh_global_model_catalog(session, rebuild_routers=True)
    except Exception as exc:
        await session.rollback()
        _log_admin_action(
            auth.user.id,
            "update_model",
            "managed",
            connection_id=model.connection_id,
            model_id=model.id,
            provider=provider,
            model_name=model.model_id,
            success=False,
            refresh_outcome=str(exc),
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Refresh failed after model update: {exc}",
        ) from exc

    _log_admin_action(
        auth.user.id,
        "update_model",
        "managed",
        connection_id=model.connection_id,
        model_id=model.id,
        provider=provider,
        model_name=model.model_id,
        success=True,
        refresh_outcome="ok",
    )
    return _admin_model_read(model)


@router.patch("/{connection_id}/models", response_model=AdminGlobalConnectionRead)
async def bulk_update_global_models(
    connection_id: int,
    data: AdminGlobalModelsBulkUpdate,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(require_superuser),
):
    conn = await _load_managed_connection(session, connection_id)
    for model in conn.models:
        if model.id in data.model_ids:
            model.enabled = data.enabled

    try:
        await session.commit()
        await refresh_global_model_catalog(session, rebuild_routers=True)
    except Exception as exc:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Refresh failed after bulk update: {exc}",
        ) from exc

    conn = await _load_managed_connection(session, connection_id)
    return _admin_connection_read(conn)
