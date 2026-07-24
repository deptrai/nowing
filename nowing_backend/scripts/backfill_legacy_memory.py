"""Backfill legacy markdown memory into the structured `memories` table.

Story 3-10b (G1.1). Reads the pre-pivot markdown columns `"user".memory_md`
and `workspaces.shared_memory_md` (raw SQL — the develop ORM no longer maps
them), parses them into facts, and inserts them via ``MemoryRepository`` so
each fact gets a real embedding.

WHEN TO RUN: during a develop->production deploy, AFTER migration 177 (the
`memories` table must exist) and BEFORE migration 178 (which drops the legacy
columns; its own guard will refuse to run until this backfill is done).

    python scripts/backfill_legacy_memory.py            # apply
    python scripts/backfill_legacy_memory.py --dry-run  # report only, no writes
    python scripts/backfill_legacy_memory.py --force    # re-run even if owner already has memories

Idempotent: near-duplicate facts are de-duplicated by MemoryRepository
(cosine < 0.08 + content match); by default owners that already have memories
are skipped so re-runs are safe.
"""

from __future__ import annotations

import argparse
import asyncio
import contextlib
import logging
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import async_session_maker
from app.services.memory.parser import parse_memory_markdown_to_facts
from app.services.memory.repository import MemoryRepository

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("backfill_legacy_memory")


async def _preconditions_ok(session) -> bool:
    """Verify the DB is at the right migration window (memories exists, legacy
    columns still present)."""
    memories_tbl = (
        await session.execute(text("SELECT to_regclass('public.memories')"))
    ).scalar()
    if memories_tbl is None:
        logger.error(
            "`memories` table not found — apply migration 177 before backfilling. Aborting."
        )
        return False

    user_col = (
        await session.execute(
            text(
                "SELECT count(*) FROM information_schema.columns "
                "WHERE table_name='user' AND column_name='memory_md'"
            )
        )
    ).scalar()
    ws_col = (
        await session.execute(
            text(
                "SELECT count(*) FROM information_schema.columns "
                "WHERE table_name='workspaces' AND column_name='shared_memory_md'"
            )
        )
    ).scalar()
    if not user_col and not ws_col:
        logger.info(
            "Legacy columns already dropped (migration 178 applied?) — nothing to backfill."
        )
        return False
    return True


async def _owner_has_user_memory(session, user_id: UUID) -> bool:
    return bool(
        (
            await session.execute(
                text(
                    "SELECT 1 FROM memories WHERE workspace_id IS NULL "
                    "AND created_by_id = :uid LIMIT 1"
                ),
                {"uid": str(user_id)},
            )
        ).scalar()
    )


async def _owner_has_ws_memory(session, workspace_id: int) -> bool:
    return bool(
        (
            await session.execute(
                text("SELECT 1 FROM memories WHERE workspace_id = :wid LIMIT 1"),
                {"wid": workspace_id},
            )
        ).scalar()
    )


async def backfill(
    *, dry_run: bool, force: bool, session: AsyncSession | None = None
) -> int:
    """Backfill legacy markdown memory into ``memories``.

    When ``session`` is None (production / CLI) a session is opened and closed
    via ``async_session_maker``. Tests inject their harness session so the
    backfill runs inside the same transaction as the fixtures; ``nullcontext``
    yields it without closing it (the caller owns its lifecycle).
    """
    created = 0
    session_cm = (
        async_session_maker() if session is None else contextlib.nullcontext(session)
    )
    async with session_cm as session:
        if not await _preconditions_ok(session):
            return 0
        repo = MemoryRepository(session)

        # --- Users (personal memory: workspace_id = NULL) ---
        user_rows = (
            await session.execute(
                text(
                    'SELECT id, memory_md FROM "user" '
                    "WHERE memory_md IS NOT NULL AND btrim(memory_md) <> ''"
                )
            )
        ).all()
        logger.info("Users with non-empty memory_md: %d", len(user_rows))
        for uid, md in user_rows:
            user_id = UUID(str(uid))
            facts = parse_memory_markdown_to_facts(md)
            if not facts:
                logger.info("  user=%s: 0 parseable facts, skip", user_id)
                continue
            if (
                not force
                and not dry_run
                and await _owner_has_user_memory(session, user_id)
            ):
                logger.info(
                    "  user=%s: already has memories, skip (use --force to override)",
                    user_id,
                )
                continue
            logger.info(
                "  user=%s: %d fact(s)%s",
                user_id,
                len(facts),
                " [dry-run]" if dry_run else "",
            )
            if dry_run:
                created += len(facts)
                continue
            for fact in facts:
                await repo.create_memory(
                    workspace_id=None,
                    content=fact.content,
                    type=fact.type,
                    source_type="manual",
                    tags=fact.tags,
                    created_by_id=user_id,
                    commit=False,
                )
                created += 1
            await session.commit()

        # --- Workspaces (team memory) ---
        ws_rows = (
            await session.execute(
                text(
                    "SELECT id, shared_memory_md FROM workspaces "
                    "WHERE shared_memory_md IS NOT NULL AND btrim(shared_memory_md) <> ''"
                )
            )
        ).all()
        logger.info("Workspaces with non-empty shared_memory_md: %d", len(ws_rows))
        for wid, md in ws_rows:
            workspace_id = int(wid)
            facts = parse_memory_markdown_to_facts(md)
            if not facts:
                logger.info("  workspace=%s: 0 parseable facts, skip", workspace_id)
                continue
            if (
                not force
                and not dry_run
                and await _owner_has_ws_memory(session, workspace_id)
            ):
                logger.info(
                    "  workspace=%s: already has memories, skip (use --force to override)",
                    workspace_id,
                )
                continue
            logger.info(
                "  workspace=%s: %d fact(s)%s",
                workspace_id,
                len(facts),
                " [dry-run]" if dry_run else "",
            )
            if dry_run:
                created += len(facts)
                continue
            for fact in facts:
                await repo.create_memory(
                    workspace_id=workspace_id,
                    content=fact.content,
                    type=fact.type,
                    source_type="manual",
                    tags=fact.tags,
                    created_by_id=None,
                    commit=False,
                )
                created += 1
            await session.commit()

    logger.info(
        "%s: %d memory fact(s) %s.",
        "DRY-RUN" if dry_run else "DONE",
        created,
        "would be created" if dry_run else "created",
    )
    return created


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Backfill legacy markdown memory into `memories`."
    )
    ap.add_argument(
        "--dry-run", action="store_true", help="Report counts without writing."
    )
    ap.add_argument(
        "--force",
        action="store_true",
        help="Backfill even if the owner already has memories.",
    )
    args = ap.parse_args()
    asyncio.run(backfill(dry_run=args.dry_run, force=args.force))


if __name__ == "__main__":
    main()
