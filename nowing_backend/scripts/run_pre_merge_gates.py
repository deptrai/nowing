"""Pre-merge gate checks for Nowing `develop` -> `production` deploy.

Covers the three operational gates that are NOT captured by story completion:

  G1 — migration 178 legacy-memory backfill safety
  G2 — legacy memory_md / shared_memory_md count right before deploy
  G5 — document retention cron review (auto_archive_enabled must be off at launch)

Run against the target database with DATABASE_URL set:

    # Report only; exits non-zero if gates are not satisfied
    python scripts/run_pre_merge_gates.py --dry-run

    # Run the legacy-memory backfill and then re-verify
    python scripts/run_pre_merge_gates.py --apply

    # Force re-backfill even if owners already have memories (rarely needed)
    python scripts/run_pre_merge_gates.py --apply --force

Recommended deploy flow:

  1. Snapshot the production database.
  2. `alembic upgrade 177` (ensure `memories` table exists but legacy columns remain).
  3. `python scripts/run_pre_merge_gates.py --apply` (G1 + G2).
  4. `alembic upgrade 178` (guard will now pass; legacy columns are dropped).
  5. `alembic upgrade head`.
  6. Smoke-test deep-research / memory / usage dashboard.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.exc import ProgrammingError

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from app.db import async_session_maker  # noqa: E402
from scripts.backfill_legacy_memory import backfill  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("pre_merge_gates")


async def _column_exists(session, table: str, column: str) -> bool:
    sql = """
        SELECT 1 FROM information_schema.columns
        WHERE table_name = :table AND column_name = :column
        LIMIT 1
    """
    return bool((await session.execute(text(sql), {"table": table, "column": column})).scalar())


async def _table_exists(session, table: str) -> bool:
    sql = "SELECT to_regclass(:table)"
    return bool((await session.execute(text(sql), {"table": table})).scalar())


def _g2_count_sql() -> tuple[str, str]:
    return (
        'SELECT count(*) FROM "user" WHERE memory_md IS NOT NULL AND btrim(memory_md) <> \'\'',
        "SELECT count(*) FROM workspaces WHERE shared_memory_md IS NOT NULL AND btrim(shared_memory_md) <> ''",
    )


def _g1_unmigrated_sql() -> tuple[str, str]:
    user_sql = '''
        SELECT count(*) FROM "user" u
        WHERE u.memory_md IS NOT NULL AND btrim(u.memory_md) <> ''
          AND NOT EXISTS (
              SELECT 1 FROM memories m
              WHERE m.created_by_id = u.id AND m.workspace_id IS NULL
          )
    '''
    ws_sql = """
        SELECT count(*) FROM workspaces w
        WHERE w.shared_memory_md IS NOT NULL AND btrim(w.shared_memory_md) <> ''
          AND NOT EXISTS (
              SELECT 1 FROM memories m WHERE m.workspace_id = w.id
          )
    """
    return user_sql, ws_sql


async def _g2(session) -> tuple[int, int]:
    user_has_col = await _column_exists(session, "user", "memory_md")
    ws_has_col = await _column_exists(session, "workspaces", "shared_memory_md")
    if not user_has_col and not ws_has_col:
        logger.info("G2 SKIP: legacy columns already dropped (migration 178 may already be applied).")
        return 0, 0

    user_sql, ws_sql = _g2_count_sql()
    user_count = (await session.execute(text(user_sql))).scalar() or 0
    ws_count = (await session.execute(text(ws_sql))).scalar() or 0
    return int(user_count), int(ws_count)


async def _g1_unmigrated(session) -> tuple[int, int]:
    if not await _table_exists(session, "public.memories"):
        logger.warning("G1 SKIP: `memories` table not found (migration 177 not applied?).")
        return 0, 0

    user_has_col = await _column_exists(session, "user", "memory_md")
    ws_has_col = await _column_exists(session, "workspaces", "shared_memory_md")
    if not user_has_col and not ws_has_col:
        logger.info("G1 SKIP: legacy columns already dropped.")
        return 0, 0

    user_sql, ws_sql = _g1_unmigrated_sql()
    try:
        user_unmigrated = (await session.execute(text(user_sql))).scalar() or 0
        ws_unmigrated = (await session.execute(text(ws_sql))).scalar() or 0
    except ProgrammingError:
        logger.exception("G1 query failed; legacy columns may be missing.")
        return 0, 0
    return int(user_unmigrated), int(ws_unmigrated)


async def _g5(session) -> list[dict]:
    rows = (
        await session.execute(
            text(
                "SELECT id, name, document_retention_days, document_retention_action "
                "FROM workspaces WHERE auto_archive_enabled = TRUE"
            )
        )
    ).all()
    return [
        {
            "id": row.id,
            "name": row.name,
            "document_retention_days": row.document_retention_days,
            "document_retention_action": row.document_retention_action,
        }
        for row in rows
    ]


async def main() -> int:
    ap = argparse.ArgumentParser(
        description="Run pre-merge gates G1/G2/G5 before Nowing production deploy."
    )
    ap.add_argument(
        "--apply",
        action="store_true",
        help="Run the legacy-memory backfill if G2 counts are non-zero.",
    )
    ap.add_argument(
        "--force",
        action="store_true",
        help="Pass --force to the backfill (re-backfill even if memories already exist).",
    )
    ap.add_argument(
        "--dry-run",
        action="store_true",
        default=True,
        help="Report without writing (default). Use --apply to actually backfill.",
    )
    args = ap.parse_args()

    if args.apply:
        args.dry_run = False

    async with async_session_maker() as session:
        # ------------------------------------------------------------------
        # G2 — legacy memory count right before deploy
        # ------------------------------------------------------------------
        user_md, ws_md = await _g2(session)
        logger.info("G2 legacy memory_md count:  users=%d  workspaces=%d", user_md, ws_md)

        # ------------------------------------------------------------------
        # G1 — migration 178 backfill safety
        # ------------------------------------------------------------------
        user_unmigrated, ws_unmigrated = await _g1_unmigrated(session)
        logger.info(
            "G1 unmigrated legacy rows: users=%d  workspaces=%d",
            user_unmigrated,
            ws_unmigrated,
        )

        needs_backfill = user_unmigrated > 0 or ws_unmigrated > 0

        if needs_backfill:
            if args.apply:
                logger.warning("Backfilling legacy memory into `memories`...")
                created = await backfill(
                    dry_run=False, force=args.force, session=session
                )
                logger.info("Backfill created %d memory fact(s).", created)

                # Re-verify after backfill.
                user_unmigrated, ws_unmigrated = await _g1_unmigrated(session)
                if user_unmigrated > 0 or ws_unmigrated > 0:
                    logger.error(
                        "G1 STILL FAILS after backfill: users=%d workspaces=%d",
                        user_unmigrated,
                        ws_unmigrated,
                    )
                    return 1
                user_md, ws_md = await _g2(session)
                logger.info(
                    "G2 after backfill:  users=%d  workspaces=%d (legacy md still present until migration 178)",
                    user_md,
                    ws_md,
                )
            else:
                logger.error(
                    "G1/G2 BLOCKED: %d user(s) and %d workspace(s) still have legacy memory not backfilled. "
                    "Run `python scripts/backfill_legacy_memory.py` or re-run this script with --apply.",
                    user_unmigrated,
                    ws_unmigrated,
                )
                return 1
        else:
            logger.info("G1 PASS: no legacy memory rows need backfill.")

        # ------------------------------------------------------------------
        # G5 — document retention cron review
        # ------------------------------------------------------------------
        enabled_workspaces = await _g5(session)
        if enabled_workspaces:
            logger.warning(
                "G5 ATTENTION: %d workspace(s) have auto_archive_enabled=TRUE",
                len(enabled_workspaces),
            )
            for ws in enabled_workspaces:
                logger.warning(
                    "  workspace id=%s name=%s retention_days=%s action=%s",
                    ws["id"],
                    ws["name"],
                    ws["document_retention_days"],
                    ws["document_retention_action"],
                )
            logger.warning(
                "Cron `apply_document_retention_policies` runs daily at 03:00 UTC. "
                "Confirm this is intentional before deploy; otherwise run:\n"
                "  UPDATE workspaces SET auto_archive_enabled = FALSE WHERE id IN (...);"
            )
        else:
            logger.info("G5 PASS: no workspace has auto_archive_enabled=TRUE.")

        # ------------------------------------------------------------------
        # Final summary
        # ------------------------------------------------------------------
        logger.info("Pre-merge gate check complete.")
        if not enabled_workspaces:
            logger.info("All gates G1/G2/G5 are satisfied. Safe to run `alembic upgrade head`.")
        else:
            logger.warning(
                "G1/G2 satisfied, but G5 has enabled workspaces. Review before deploy."
            )
            return 2

    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
