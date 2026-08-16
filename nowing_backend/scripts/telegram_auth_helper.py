#!/usr/bin/env python3
"""Interactive CLI helper for onboarding Telegram phone accounts into encrypted StringSession pool (Story 22.2)."""

from __future__ import annotations

import argparse
import asyncio
import getpass
import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from telethon import TelegramClient
from telethon.errors import SessionPasswordNeededError
from telethon.sessions import StringSession

from app.db import async_session_maker
from app.proprietary.platforms.telegram.client import parse_proxy_url
from app.services.scraper_platform_account_service import ScraperPlatformAccountService


async def main() -> None:
    parser = argparse.ArgumentParser(
        description="Onboard Telegram phone account into Nowing encrypted session pool"
    )
    parser.add_argument(
        "--phone", help="Phone number with country code (e.g. +84988123456)"
    )
    parser.add_argument(
        "--api-id", type=int, help="Telegram API ID from my.telegram.org"
    )
    parser.add_argument("--api-hash", help="Telegram API Hash from my.telegram.org")
    parser.add_argument(
        "--proxy", help="SOCKS5 proxy URL (e.g. socks5h://user:pass@host:port)"
    )
    parser.add_argument("--label", help="Optional label for the account")
    args = parser.parse_args()

    print("=" * 60)
    print("Nowing Telegram Scraper Account Onboarding")
    print("=" * 60)

    phone = args.phone or input("Enter phone number (+84...): ").strip()
    api_id = args.api_id or int(input("Enter API ID: ").strip())
    api_hash = args.api_hash or input("Enter API Hash: ").strip()
    proxy_url = (
        args.proxy
        or input("Enter Proxy URL (optional, press Enter to skip): ").strip()
        or None
    )
    label = (
        args.label
        or input(f"Enter Label (default: Telegram {phone}): ").strip()
        or f"Telegram ({phone})"
    )

    proxy_config = parse_proxy_url(proxy_url) if proxy_url else None

    print(f"\n[1/3] Connecting to Telegram MTProto servers for {phone}...")
    client = TelegramClient(
        StringSession(),
        api_id,
        api_hash,
        proxy=proxy_config,
    )
    await client.connect()

    try:
        print(f"[2/3] Requesting login OTP code for {phone}...")
        sent_code = await client.send_code_request(phone)
        phone_code_hash = getattr(sent_code, "phone_code_hash", None)

        code = input("Enter OTP code received on Telegram / SMS: ").strip()

        try:
            user = await client.sign_in(
                phone=phone, code=code, phone_code_hash=phone_code_hash
            )
        except SessionPasswordNeededError:
            print("2FA Cloud Password is required for this account.")
            password = getpass.getpass("Enter 2FA Cloud Password: ")
            user = await client.sign_in(password=password)

        final_session_string = client.session.save()
        username = getattr(user, "username", None) or f"user_{getattr(user, 'id', '')}"
        print(f"\n[3/3] Authenticated successfully as @{username}!")

        # Save to database
        credentials = {
            "api_id": api_id,
            "api_hash": api_hash,
            "session_string": final_session_string,
            "phone": phone,
        }
        if proxy_url:
            credentials["proxy_url"] = proxy_url

        async with async_session_maker() as session:
            svc = ScraperPlatformAccountService(session)
            account = await svc.create(
                platform="telegram",
                label=label,
                is_enabled=True,
                is_default=False,
                credentials=credentials,
            )
            print(
                f"\n✅ Successfully saved to ScraperPlatformAccount (ID: {account.id})"
            )
            print(
                "Session string encrypted and stored in database. Zero disk files created (AD-1)."
            )

    finally:
        await client.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
