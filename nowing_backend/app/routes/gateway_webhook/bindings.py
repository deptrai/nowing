"""Messaging gateway routes."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.context import AuthContext
from app.config import config
from app.db import (
    ExternalChatAccount,
    ExternalChatAccountMode,
    ExternalChatBinding,
    ExternalChatBindingState,
    ExternalChatPlatform,
    Permission,
    WorkspaceMembership,
    get_async_session,
)
from app.dependencies.auth import (
    RequirePermissionFromEntity,
    RequireWorkspaceAccessFromBody,
)
from app.gateway.accounts import (
    get_or_create_system_telegram_account,
    get_or_create_system_whatsapp_account,
)
from app.gateway.bindings import resume_binding, revoke_binding
from app.gateway.pairing import generate_pairing_code, pairing_expires_at
from app.gateway.registry import resolve_platform_bundle
from app.services.auto_reply_agent import pause_auto_reply
from app.users import get_auth_context

from ._helpers import (
    _active_whatsapp_account_mode,
    _is_inactive_whatsapp_account,
    _telegram_gateway_enabled,
)

logger = logging.getLogger(__name__)
router = APIRouter()


class StartBindingRequest(BaseModel):
    platform: ExternalChatPlatform = ExternalChatPlatform.TELEGRAM
    workspace_id: int


class StartBindingResponse(BaseModel):
    binding_id: int
    code: str
    deep_link: str
    expires_at: datetime


class UpdateBindingWorkspaceRequest(BaseModel):
    workspace_id: int


class UpdateAccountWorkspaceRequest(BaseModel):
    workspace_id: int


class SendBindingMessageRequest(BaseModel):
    text: str


@router.post("/bindings/start", response_model=StartBindingResponse)
async def start_binding(
    body: StartBindingRequest,
    auth: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_async_session),
    _membership: WorkspaceMembership = Depends(
        RequireWorkspaceAccessFromBody()
    ),
) -> StartBindingResponse:
    user = auth.user
    code = generate_pairing_code()
    if body.platform == ExternalChatPlatform.TELEGRAM:
        if not _telegram_gateway_enabled():
            raise HTTPException(status_code=400, detail="Telegram gateway is disabled")
        account = await get_or_create_system_telegram_account(session)
        username = account.bot_username or config.TELEGRAM_SHARED_BOT_USERNAME
        if not username:
            raise HTTPException(
                status_code=500,
                detail="Telegram bot username is not configured",
            )
        deep_link = f"https://t.me/{username}?start={code}"
    elif body.platform == ExternalChatPlatform.WHATSAPP:
        if config.GATEWAY_WHATSAPP_INTAKE_MODE != "cloud":
            raise HTTPException(
                status_code=400,
                detail="WhatsApp /start pairing requires GATEWAY_WHATSAPP_INTAKE_MODE=cloud",
            )
        account = await get_or_create_system_whatsapp_account(session)
        phone = config.WHATSAPP_SHARED_DISPLAY_PHONE_NUMBER
        if not phone:
            raise HTTPException(
                status_code=500,
                detail="WHATSAPP_SHARED_DISPLAY_PHONE_NUMBER is not configured",
            )
        normalized_phone = "".join(ch for ch in phone if ch.isdigit())
        if not normalized_phone:
            raise HTTPException(
                status_code=500,
                detail="WHATSAPP_SHARED_DISPLAY_PHONE_NUMBER must contain digits",
            )
        deep_link = f"https://wa.me/{normalized_phone}?text={quote(f'/start {code}')}"
    else:
        raise HTTPException(status_code=400, detail="Unsupported platform")

    expires_at = pairing_expires_at()
    binding = ExternalChatBinding(
        account_id=account.id,
        user_id=user.id,
        workspace_id=body.workspace_id,
        state=ExternalChatBindingState.PENDING,
        pairing_code=code,
        pairing_code_expires_at=expires_at,
    )
    session.add(binding)
    await session.commit()
    await session.refresh(binding)

    return StartBindingResponse(
        binding_id=binding.id,
        code=code,
        deep_link=deep_link,
        expires_at=expires_at,
    )


@router.get("/bindings")
async def list_bindings(
    auth: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_async_session),
) -> list[dict[str, Any]]:
    user = auth.user
    result = await session.execute(
        select(ExternalChatBinding, ExternalChatAccount)
        .join(
            ExternalChatAccount,
            ExternalChatBinding.account_id == ExternalChatAccount.id,
        )
        .where(ExternalChatBinding.user_id == user.id)
    )
    return [
        {
            "id": binding.id,
            "platform": account.platform.value,
            "state": binding.state.value,
            "workspace_id": binding.workspace_id,
            "external_display_name": binding.external_display_name,
            "external_username": binding.external_username,
            "external_metadata": binding.external_metadata,
            "suspended_reason": binding.suspended_reason,
        }
        for binding, account in result.all()
    ]


@router.get("/connections")
async def list_connections(
    platform: ExternalChatPlatform | None = None,
    auth: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_async_session),
) -> list[dict[str, Any]]:
    user = auth.user
    active_whatsapp_mode = _active_whatsapp_account_mode()
    if platform == ExternalChatPlatform.WHATSAPP and active_whatsapp_mode is None:
        return []
    if platform == ExternalChatPlatform.TELEGRAM and not _telegram_gateway_enabled():
        return []

    filters = [
        ExternalChatBinding.user_id == user.id,
        ExternalChatBinding.state.in_(
            [ExternalChatBindingState.BOUND, ExternalChatBindingState.SUSPENDED]
        ),
    ]
    if platform is not None:
        filters.append(ExternalChatAccount.platform == platform)
        if (
            platform == ExternalChatPlatform.WHATSAPP
            and active_whatsapp_mode is not None
        ):
            filters.append(ExternalChatAccount.mode == active_whatsapp_mode)
    else:
        if not _telegram_gateway_enabled():
            filters.append(
                ExternalChatAccount.platform != ExternalChatPlatform.TELEGRAM
            )
        if active_whatsapp_mode is None:
            filters.append(
                ExternalChatAccount.platform != ExternalChatPlatform.WHATSAPP
            )
        else:
            filters.append(
                or_(
                    ExternalChatAccount.platform != ExternalChatPlatform.WHATSAPP,
                    ExternalChatAccount.mode == active_whatsapp_mode,
                )
            )

    result = await session.execute(
        select(ExternalChatBinding, ExternalChatAccount)
        .join(
            ExternalChatAccount,
            ExternalChatBinding.account_id == ExternalChatAccount.id,
        )
        .where(*filters)
    )

    connections: list[dict[str, Any]] = []
    baileys_account_ids: set[int] = set()
    for binding, account in result.all():
        binding_metadata = binding.external_metadata or {}
        kind = str(binding_metadata.get("kind") or "")
        if kind in {"slack_thread", "discord_thread"}:
            continue

        account_state = account.cursor_state or {}
        workspace_name = None
        workspace_id = None
        route_type = "binding"
        connection_id = binding.id
        workspace_id = binding.workspace_id
        display_name = binding.external_display_name or binding.external_username
        if account.platform == ExternalChatPlatform.SLACK:
            workspace_name = account_state.get("team_name")
            workspace_id = account_state.get("team_id")
        elif account.platform == ExternalChatPlatform.DISCORD:
            workspace_name = account_state.get("guild_name")
            workspace_id = account_state.get("guild_id")
        elif account.platform == ExternalChatPlatform.WHATSAPP:
            workspace_name = account_state.get("display_phone_number")
            workspace_id = account_state.get("phone_number_id")
            if account.mode == ExternalChatAccountMode.SELF_HOST_BYO:
                if int(account.id) in baileys_account_ids:
                    continue
                baileys_account_ids.add(int(account.id))
                route_type = "account"
                connection_id = account.id
                workspace_id = account.owner_workspace_id or binding.workspace_id
                display_name = "WhatsApp Bridge"

        connections.append(
            {
                "id": connection_id,
                "account_id": account.id,
                "route_type": route_type,
                "platform": account.platform.value,
                "mode": account.mode.value,
                "state": binding.state.value,
                "workspace_id": workspace_id,
                "display_name": display_name or workspace_name,
                "external_username": (
                    None
                    if account.mode == ExternalChatAccountMode.SELF_HOST_BYO
                    else binding.external_username
                ),
                "workspace_name": workspace_name,
                "health_status": account.health_status.value,
                "suspended_reason": binding.suspended_reason,
            }
        )

    if active_whatsapp_mode == ExternalChatAccountMode.SELF_HOST_BYO and (
        platform is None or platform == ExternalChatPlatform.WHATSAPP
    ):
        account_result = await session.execute(
            select(ExternalChatAccount).where(
                ExternalChatAccount.owner_user_id == user.id,
                ExternalChatAccount.platform == ExternalChatPlatform.WHATSAPP,
                ExternalChatAccount.mode == ExternalChatAccountMode.SELF_HOST_BYO,
                ExternalChatAccount.owner_workspace_id.is_not(None),
            )
        )
        for account in account_result.scalars():
            if int(account.id) in baileys_account_ids:
                continue
            account_state = account.cursor_state or {}
            connections.append(
                {
                    "id": account.id,
                    "account_id": account.id,
                    "route_type": "account",
                    "platform": account.platform.value,
                    "mode": account.mode.value,
                    "state": "bound",
                    "workspace_id": account.owner_workspace_id,
                    "display_name": "WhatsApp Bridge",
                    "external_username": None,
                    "workspace_name": account_state.get("display_phone_number"),
                    "health_status": account.health_status.value,
                    "suspended_reason": account.suspended_reason,
                }
            )

    return connections


@router.get("/platforms")
async def list_platforms(
    auth: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_async_session),
) -> list[dict[str, Any]]:
    user = auth.user
    result = await session.execute(
        select(ExternalChatAccount).where(
            (ExternalChatAccount.owner_user_id == user.id)
            | (ExternalChatAccount.is_system_account.is_(True))
        )
    )
    return [
        {
            "id": account.id,
            "platform": account.platform.value,
            "mode": account.mode.value,
            "bot_username": account.bot_username,
            "health_status": account.health_status.value,
            "last_health_check_at": account.last_health_check_at,
        }
        for account in result.scalars()
    ]


@router.patch("/bindings/{binding_id}/workspace")
async def update_binding_workspace(
    binding_id: int,
    body: UpdateBindingWorkspaceRequest,
    auth: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_async_session),
    _membership: WorkspaceMembership = Depends(
        RequireWorkspaceAccessFromBody()
    ),
) -> dict[str, bool]:
    user = auth.user
    binding = await session.get(ExternalChatBinding, binding_id)
    if binding is None or binding.user_id != user.id:
        raise HTTPException(status_code=404, detail="Binding not found")
    if binding.state not in {
        ExternalChatBindingState.BOUND,
        ExternalChatBindingState.SUSPENDED,
    }:
        raise HTTPException(
            status_code=400, detail="Only active bindings can be routed"
        )
    account = await session.get(ExternalChatAccount, binding.account_id)
    if account is None or _is_inactive_whatsapp_account(account):
        raise HTTPException(status_code=404, detail="Binding not found")

    if binding.workspace_id != body.workspace_id:
        binding.workspace_id = body.workspace_id
        binding.new_chat_thread_id = None
    binding.updated_at = datetime.now(UTC)
    await session.commit()
    return {"ok": True}


@router.patch("/accounts/{account_id}/workspace")
async def update_gateway_account_workspace(
    account_id: int,
    body: UpdateAccountWorkspaceRequest,
    auth: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_async_session),
    _membership: WorkspaceMembership = Depends(
        RequireWorkspaceAccessFromBody()
    ),
) -> dict[str, bool]:
    user = auth.user
    account = await session.get(ExternalChatAccount, account_id)
    if (
        account is None
        or account.owner_user_id != user.id
        or account.platform != ExternalChatPlatform.WHATSAPP
        or account.mode != ExternalChatAccountMode.SELF_HOST_BYO
        or _is_inactive_whatsapp_account(account)
    ):
        raise HTTPException(status_code=404, detail="Gateway account not found")

    account.owner_workspace_id = body.workspace_id
    account.updated_at = datetime.now(UTC)

    result = await session.execute(
        select(ExternalChatBinding).where(
            ExternalChatBinding.account_id == account.id,
            ExternalChatBinding.user_id == user.id,
            ExternalChatBinding.state.in_(
                [ExternalChatBindingState.BOUND, ExternalChatBindingState.SUSPENDED]
            ),
        )
    )
    for binding in result.scalars():
        binding.workspace_id = body.workspace_id
        binding.new_chat_thread_id = None
        binding.updated_at = datetime.now(UTC)

    await session.commit()
    return {"ok": True}


@router.delete("/bindings/{binding_id}")
async def delete_binding(
    binding_id: int,
    auth: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_async_session),
) -> dict[str, bool]:
    user = auth.user
    binding = await session.get(ExternalChatBinding, binding_id)
    if binding is None or binding.user_id != user.id:
        raise HTTPException(status_code=404, detail="Binding not found")
    account = await session.get(ExternalChatAccount, binding.account_id)
    if account is None or _is_inactive_whatsapp_account(account):
        raise HTTPException(status_code=404, detail="Binding not found")
    revoke_binding(binding)
    await session.commit()
    return {"ok": True}


@router.delete("/accounts/{account_id}")
async def delete_gateway_account(
    account_id: int,
    auth: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_async_session),
) -> dict[str, bool]:
    user = auth.user
    account = await session.get(ExternalChatAccount, account_id)
    if (
        account is None
        or account.owner_user_id != user.id
        or account.platform != ExternalChatPlatform.WHATSAPP
        or account.mode != ExternalChatAccountMode.SELF_HOST_BYO
        or _is_inactive_whatsapp_account(account)
    ):
        raise HTTPException(status_code=404, detail="Gateway account not found")

    result = await session.execute(
        select(ExternalChatBinding).where(
            ExternalChatBinding.account_id == account.id,
            ExternalChatBinding.user_id == user.id,
            ExternalChatBinding.state.in_(
                [ExternalChatBindingState.BOUND, ExternalChatBindingState.SUSPENDED]
            ),
        )
    )
    for binding in result.scalars():
        revoke_binding(binding)

    account.owner_workspace_id = None
    account.suspended_at = datetime.now(UTC)
    account.suspended_reason = "disconnected"
    account.updated_at = datetime.now(UTC)
    await session.commit()
    return {"ok": True}


@router.post("/bindings/{binding_id}/resume")
async def resume_external_chat_binding(
    binding_id: int,
    auth: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_async_session),
) -> dict[str, bool]:
    user = auth.user
    binding = await session.get(ExternalChatBinding, binding_id)
    if binding is None or binding.user_id != user.id:
        raise HTTPException(status_code=404, detail="Binding not found")
    account = await session.get(ExternalChatAccount, binding.account_id)
    if account is None or _is_inactive_whatsapp_account(account):
        raise HTTPException(status_code=404, detail="Binding not found")
    resume_binding(binding)
    binding.updated_at = datetime.now(UTC)
    await session.commit()
    return {"ok": True}


@router.post("/bindings/{binding_id}/send")
async def send_message_to_binding(
    binding_id: int,
    body: SendBindingMessageRequest,
    auth: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_async_session),
    _membership: WorkspaceMembership = Depends(
        RequirePermissionFromEntity(
            "ExternalChatBinding",
            "binding_id",
            Permission.LEADS_WRITE.value,
            "You don't have permission to send messages in this workspace",
        )
    ),
) -> dict[str, Any]:
    """Allow a workspace member to send a message to an external chat thread.

    Marks the thread as human-controlled and pauses AI auto-reply for 24h (AC-4).
    """
    binding = await session.get(ExternalChatBinding, binding_id)
    if binding is None:
        raise HTTPException(status_code=404, detail="Binding not found")

    account = await session.get(ExternalChatAccount, binding.account_id)
    if account is None or _is_inactive_whatsapp_account(account):
        raise HTTPException(status_code=404, detail="Binding account not found")

    bundle = resolve_platform_bundle(account)
    target_peer = binding.external_peer_id
    if not target_peer:
        raise HTTPException(
            status_code=400,
            detail="Binding has no external peer to send to",
        )

    try:
        result = await bundle.adapter.send_message(
            external_peer_id=target_peer,
            text=body.text,
        )
    except Exception as exc:  # upstream failure → surface as typed HTTP error
        logger.error("Failed to send message via binding %s: %s", binding_id, exc)
        raise HTTPException(
            status_code=502,
            detail=f"Failed to send message: {exc}",
        ) from exc

    # Human-in-the-loop: pause auto-reply for this thread for 24h.
    await pause_auto_reply(str(binding.id))

    return {
        "ok": True,
        "external_message_id": result.external_message_id,
        "auto_reply_paused": True,
    }
