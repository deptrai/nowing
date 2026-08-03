"""Capture a fresh Batdongsan.com.vn browser session and save it to the DB.

This is meant for self-host admins who log in with Google OAuth and cannot
share a password. It opens a headed Chromium window on the Batdongsan login
page, waits for the admin to complete OAuth, then captures the full cookie
jar (including HttpOnly cookies) and stores it in the
`ScraperPlatformAccount` record for `batdongsan`.

Usage:
    cd nowing_backend
    PYTHONPATH=. python3 scripts/capture_batdongsan_session.py

The script will print the captured cookies as a Playwright JSON array and
try to update the default `batdongsan` account. If the DB is not available,
just save the printed JSON and paste it into the admin UI.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import sys
from typing import Any

# Allow running without a package install.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from playwright.async_api import async_playwright

from app.db import async_session_maker
from app.services.scraper_platform_account_service import ScraperPlatformAccountService

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

LOGIN_URL = "https://batdongsan.com.vn/dang-nhap"
LISTING_URL = "https://batdongsan.com.vn/ban-nha-rieng-pho-ngoc-khanh-phuong-ngoc-khanh-2/toa-chdv-giang-vo-75m2-7-tang-19-8-ty-17pkk-dong-tien-cho-thue-100tr-th-pr46122640"


def _read_line(prompt: str) -> str:
    try:
        return input(prompt)
    except (EOFError, KeyboardInterrupt):
        return ""


def _extract_access_token(cookies: list[dict[str, Any]]) -> str | None:
    for c in cookies:
        if c.get("name") == "accessToken":
            return c.get("value")
    return None


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Capture Batdongsan session")
    parser.add_argument(
        "--auto",
        action="store_true",
        help="Do not wait for Enter; poll cookies until accessToken appears.",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=300,
        help="Seconds to wait for login in auto mode (default: 300).",
    )
    parser.add_argument(
        "--no-update-db",
        action="store_true",
        help="Only print cookies; do not write to the DB.",
    )
    parser.add_argument(
        "--platform",
        type=str,
        default="batdongsan",
        help="Platform slug to save under (default: batdongsan).",
    )
    parser.add_argument(
        "--cdp",
        type=str,
        default=None,
        help="Connect to an existing Chrome via CDP (e.g. http://localhost:9222).",
    )
    return parser.parse_args(argv)


async def _save_credentials(
    credentials: dict[str, Any], platform: str = "batdongsan"
) -> bool:
    try:
        async with async_session_maker() as session:
            svc = ScraperPlatformAccountService(session)
            account = await svc.get_default(platform)
            if account is None:
                # Create a default account if one does not exist.
                await svc.create(
                    platform=platform,
                    label="captured",
                    is_enabled=True,
                    is_default=True,
                    credentials=credentials,
                )
                logger.info("Created default %s scraper account", platform)
            else:
                await svc.update(account, {"credentials": credentials})
                logger.info("Updated default %s scraper account", platform)
        return True
    except Exception as exc:
        logger.warning("Could not save credentials to DB: %s", exc)
        return False


async def _wait_for_login(context, timeout: int = 300) -> list[dict[str, Any]] | None:
    """Poll cookies until the accessToken appears or we time out."""
    for attempt in range(timeout // 5):
        cookies = await context.cookies()
        if _extract_access_token(cookies):
            logger.info("accessToken detected on attempt %d", attempt + 1)
            return cookies
        await asyncio.sleep(5)
    return None


def _filter_batdongsan_cookies(cookies: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Keep cookies whose domain belongs to batdongsan.com.vn."""
    return [
        c
        for c in cookies
        if c.get("domain", "").endswith(".batdongsan.com.vn")
        or c.get("domain", "") == "batdongsan.com.vn"
    ]


async def _capture_cookies(context, page) -> list[dict[str, Any]]:
    """Navigate to a listing and return the filtered Batdongsan cookie jar."""
    logger.info("Navigating to listing to refresh session cookies")
    await page.goto(LISTING_URL, wait_until="domcontentloaded", timeout=120_000)
    await asyncio.sleep(3)

    cookies = await context.cookies()
    return _filter_batdongsan_cookies(cookies)


async def _open_browser_context(p, args: argparse.Namespace):
    """Launch a fresh Playwright browser or attach to an existing Chrome."""
    if args.cdp:
        logger.info("Connecting to existing Chrome at %s", args.cdp)
        browser = await p.chromium.connect_over_cdp(args.cdp)
        # Reuse the first existing context, or create a new one if none exists.
        contexts = browser.contexts
        context = contexts[0] if contexts else await browser.new_context()
        # Use the first existing page, or create a new tab.
        pages = context.pages
        page = pages[0] if pages else await context.new_page()
        return browser, context, page

    browser = await p.chromium.launch(headless=False, args=["--no-sandbox"])
    context = await browser.new_context(
        locale="vi-VN",
        timezone_id="Asia/Ho_Chi_Minh",
        viewport={"width": 1440, "height": 900},
        user_agent=(
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/128.0.0.0 Safari/537.36"
        ),
    )
    page = await context.new_page()
    return browser, context, page


async def capture(args: argparse.Namespace | None = None) -> int:
    args = args or _parse_args(None)
    async with async_playwright() as p:
        browser, context, page = await _open_browser_context(p, args)

        logger.info("Opening login page: %s", LOGIN_URL)
        await page.goto(LOGIN_URL, wait_until="domcontentloaded", timeout=120_000)

        if args.auto:
            print(
                "A browser window is open. Please log in to Batdongsan. "
                "Cookies will be captured automatically once logged in."
            )
            raw_cookies = await _wait_for_login(context, timeout=args.timeout)
            if raw_cookies is None:
                logger.error("Timeout waiting for login. No accessToken cookie found.")
                await browser.close()
                return 1
            kept = _filter_batdongsan_cookies(raw_cookies)
        else:
            print("\n" + "=" * 60)
            print("1. Log in to Batdongsan with Google in the opened browser.")
            print("2. Optionally open a listing and click 'Hiện số' to refresh the token.")
            print("3. Come back here and press Enter to capture cookies.")
            print("=" * 60)
            _read_line("> Press Enter when you are logged in and on the site...")
            kept = await _capture_cookies(context, page)

        await browser.close()

        if not kept:
            logger.error("No Batdongsan cookies captured. Did you log in?")
            return 1

        access_token = _extract_access_token(kept)
        if not access_token:
            logger.warning(
                "No accessToken cookie found; the session may not be logged in"
            )

        credentials = {
            "cookies": json.dumps(kept, ensure_ascii=False),
            "token": access_token,
        }

        cookie_file = os.path.expanduser("~/batdongsan_cookies.json")
        with open(cookie_file, "w", encoding="utf-8") as f:
            json.dump(kept, f, ensure_ascii=False, indent=2)
        logger.info("Wrote cookies to %s", cookie_file)

        if not args.no_update_db:
            saved = await _save_credentials(credentials, platform=args.platform)
            if saved:
                print("\nSaved to DB. You can now use the scraper.")
            else:
                print("\nCould not save to DB. Copy the cookies above into the admin UI.")
        else:
            print("\nSkipping DB update because --no-update-db was set.")

        print("\n--- Playwright cookie JSON (filtered) ---")
        print(json.dumps(kept, ensure_ascii=False, indent=2))
    return 0


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    return asyncio.run(capture(args))


if __name__ == "__main__":
    sys.exit(main())
