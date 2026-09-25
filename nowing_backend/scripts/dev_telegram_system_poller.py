"""Dev-only: long-poll the SHARED Telegram bot account locally.

The BYO supervisor in app lifespan skips ``is_system_account=True`` rows, so
the shared bot's /start pairing messages are never consumed without a public
webhook. Run this while developing to get inbound updates for the system
account through the same inbox path (inbox_worker in the app process then
handles pairing, commands, etc.).

Safe: uses the same advisory lock + dedupe keys as production. Stop with
Ctrl+C; the account's ``cursor_state.last_update_id`` persists progress.

Usage: .venv/bin/python scripts/dev_telegram_system_poller.py
"""

import asyncio
import logging

from sqlalchemy import select

from app.config import config
from app.db import ExternalChatAccount, ExternalChatPlatform, async_session_maker
from app.gateway.accounts import account_token
from app.gateway.runner import _run_telegram_account

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("dev_telegram_system_poller")


async def main() -> None:
    if not config.TELEGRAM_SHARED_BOT_TOKEN:
        raise SystemExit("TELEGRAM_SHARED_BOT_TOKEN is not set")
    async with async_session_maker() as session:
        account = (
            await session.execute(
                select(ExternalChatAccount).where(
                    ExternalChatAccount.platform == ExternalChatPlatform.TELEGRAM,
                    ExternalChatAccount.is_system_account.is_(True),
                )
            )
        ).scalars().first()
        if account is None:
            raise SystemExit("No system Telegram account row — POST /bindings/start first")
        token = account_token(account)
        account_id = int(account.id)
    if not token:
        raise SystemExit("System account has no usable token")
    logger.info("Long-polling system Telegram account id=%s (@%s)", account_id, account.bot_username)
    await _run_telegram_account(account_id, token)


if __name__ == "__main__":
    asyncio.run(main())
