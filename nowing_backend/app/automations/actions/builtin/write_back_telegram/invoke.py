"""Execute a ``write_back_telegram`` automation step."""

from __future__ import annotations

from typing import Any

from sqlalchemy import select

from app.db import (
    ExternalChatAccount,
    ExternalChatBinding,
    ExternalChatBindingState,
    ExternalChatPlatform,
)
from app.gateway.accounts import account_token
from app.gateway.telegram.adapter import TelegramAdapter

from ...types import ActionContext
from .params import TelegramActionParams

TELEGRAM = ExternalChatPlatform.TELEGRAM


def _format_account_error(account_id: int, msg: str) -> str:
    return f"Telegram account {account_id}: {msg}"


async def _resolve_telegram_account(
    ctx: ActionContext, params: TelegramActionParams
) -> ExternalChatAccount:
    session = ctx.session

    if params.account_id is not None:
        account = await session.get(ExternalChatAccount, params.account_id)
        if account is None:
            raise ValueError(f"Telegram account {params.account_id} not found")
        if account.platform != TELEGRAM:
            raise ValueError(
                _format_account_error(params.account_id, "not a Telegram account")
            )
        if account.suspended_at is not None:
            raise ValueError(
                _format_account_error(params.account_id, "account is suspended")
            )
        if account.is_system_account:
            return account
        if (
            account.owner_workspace_id != ctx.workspace_id
            and account.owner_user_id != ctx.creator_user_id
        ):
            raise ValueError(
                _format_account_error(
                    params.account_id,
                    "does not belong to this workspace or user",
                )
            )
        return account

    if params.use_system_bot:
        result = await session.execute(
            select(ExternalChatAccount).where(
                ExternalChatAccount.platform == TELEGRAM,
                ExternalChatAccount.is_system_account.is_(True),
                ExternalChatAccount.suspended_at.is_(None),
            )
        )
        account = result.scalars().first()
        if account is None:
            raise ValueError("No system Telegram account configured")
        return account

    raise ValueError("Provide a Telegram account_id or set use_system_bot=true")


async def _resolve_chat_id(
    ctx: ActionContext, account: ExternalChatAccount, params: TelegramActionParams
) -> str:
    if params.chat_id is not None:
        return params.chat_id

    if ctx.creator_user_id is None:
        raise ValueError(
            "chat_id is required; no automation creator to resolve a binding"
        )

    result = await ctx.session.execute(
        select(ExternalChatBinding).where(
            ExternalChatBinding.account_id == account.id,
            ExternalChatBinding.workspace_id == ctx.workspace_id,
            ExternalChatBinding.user_id == ctx.creator_user_id,
            ExternalChatBinding.state == ExternalChatBindingState.BOUND,
            ExternalChatBinding.suspended_at.is_(None),
            ExternalChatBinding.revoked_at.is_(None),
        )
    )
    binding = result.scalars().first()
    if binding is None or not binding.external_peer_id:
        raise ValueError("No Telegram chat bound to this user or workspace")
    return binding.external_peer_id


async def write_back_telegram(
    ctx: ActionContext, params: TelegramActionParams
) -> dict[str, Any]:
    """Send a Telegram message through a workspace or system account."""
    account = await _resolve_telegram_account(ctx, params)
    token = account_token(account)
    if not token:
        raise ValueError(f"Telegram account {account.id} has no usable token")

    chat_id = await _resolve_chat_id(ctx, account, params)
    adapter = TelegramAdapter(token)
    result = await adapter.send_message(
        external_peer_id=chat_id,
        text=params.text,
        parse_mode=params.parse_mode,
        reply_to_message_id=params.reply_to_message_id,
        reply_markup=params.reply_markup,
    )

    return {
        "provider": "telegram",
        "account_id": account.id,
        "chat_id": chat_id,
        "message_id": result.external_message_id,
        "text": params.text,
        "parse_mode": params.parse_mode,
        "reply_markup": params.reply_markup,
        "reply_to_message_id": params.reply_to_message_id,
    }
