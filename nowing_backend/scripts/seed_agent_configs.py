#!/usr/bin/env python3
"""Seed the default BDS AI listing assistant agent config.

Run from `nowing_backend/`:

    ENVIRONMENT=development uv run --active python scripts/seed_agent_configs.py

The script is idempotent: it upserts the agent by (client_id, slug).
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys

from sqlalchemy import select

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(_SCRIPT_DIR)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from app.db import AgentConfig, VerticalClient, async_session_maker  # noqa: E402

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

DEFAULT_CLIENT_ID = "bdsai.vn"
DEFAULT_AGENT_SLUG = "bdsai-listing-assistant"
DEFAULT_NAME = "BDS AI Listing Assistant"

# Default tool allowlist for the BDS AI vertical (property listing, broker research).
DEFAULT_ENABLED_TOOLS = [
    "web_search",
    "batdongsan_scrape",
    "muaban_bds_scrape",
    "vn_bds_scrape",
    "google_maps_search",
]

DEFAULT_SYSTEM_INSTRUCTIONS = (
    "You are a helpful real-estate listing assistant for BDS AI. "
    "You help Vietnamese brokers draft and research property listings. "
    "Use the web and real-estate tools to gather facts; cite sources when available."
)


def _require_dev_environment() -> None:
    env = os.getenv("ENVIRONMENT", "development").lower()
    safe = {"development", "dev", "test", "testing", "local"}
    if env not in safe:
        raise RuntimeError(
            f"refusing to seed in ENVIRONMENT={env!r}. Set ENVIRONMENT to one of {safe} or pass --force."
        )


async def _ensure_vertical_client(session, client_id: str) -> None:
    result = await session.execute(
        select(VerticalClient).where(VerticalClient.client_id == client_id)
    )
    if result.scalar_one_or_none() is None:
        session.add(
            VerticalClient(
                client_id=client_id,
                display_name=f"{client_id} (seeded)",
                is_active=True,
            )
        )
        await session.flush()


async def seed(
    client_id: str = DEFAULT_CLIENT_ID,
    slug: str = DEFAULT_AGENT_SLUG,
    name: str = DEFAULT_NAME,
    force: bool = False,
) -> AgentConfig:
    if not force:
        _require_dev_environment()

    async with async_session_maker() as session:
        await _ensure_vertical_client(session, client_id)

        result = await session.execute(
            select(AgentConfig).where(
                AgentConfig.client_id == client_id,
                AgentConfig.slug == slug,
            )
        )
        agent = result.scalar_one_or_none()

        if agent is None:
            agent = AgentConfig(
                client_id=client_id,
                name=name,
                slug=slug,
                system_instructions=DEFAULT_SYSTEM_INSTRUCTIONS,
                enabled_tools=DEFAULT_ENABLED_TOOLS,
                disabled_tools=[],
                model_name=None,
                citations_enabled=True,
                is_active=True,
            )
            session.add(agent)
            logger.info("Created agent config %s/%s", client_id, slug)
        else:
            agent.system_instructions = (
                agent.system_instructions or DEFAULT_SYSTEM_INSTRUCTIONS
            )
            agent.enabled_tools = agent.enabled_tools or DEFAULT_ENABLED_TOOLS
            agent.is_active = True
            logger.info("Updated agent config %s/%s", client_id, slug)

        await session.commit()
        await session.refresh(agent)
        return agent


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Seed the default BDS AI agent config."
    )
    parser.add_argument("--client-id", default=DEFAULT_CLIENT_ID)
    parser.add_argument("--slug", default=DEFAULT_AGENT_SLUG)
    parser.add_argument("--name", default=DEFAULT_NAME)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    agent = asyncio.run(
        seed(
            client_id=args.client_id,
            slug=args.slug,
            name=args.name,
            force=args.force,
        )
    )
    print(
        f"Seeded agent config: id={agent.id} client_id={agent.client_id} slug={agent.slug}"
    )


if __name__ == "__main__":
    main()
