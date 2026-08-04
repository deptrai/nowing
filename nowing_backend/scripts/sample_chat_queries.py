#!/usr/bin/env python3
"""CLI for sampling production chat queries for the chat/regression benchmark.

Run from ``nowing_backend/``:

    ENVIRONMENT=development uv run --active python scripts/sample_chat_queries.py \
        --pat "nw_pat_..." --days 30 --max-queries 100 --output /tmp/sampled.jsonl

The script authenticates the PAT, verifies the owner is a platform superuser,
reads from ``NewChatMessage`` via a read-only path, and writes a JSONL dataset
that ``nowing_evals ingest chat regression --dataset`` can consume.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from pathlib import Path

# Allow `python scripts/sample_chat_queries.py` from the repo root or nowing_backend.
_SCRIPT_DIR = Path(__file__).resolve().parent
_PROJECT_ROOT = _SCRIPT_DIR.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

import asyncio  # noqa: E402

from app.admin.chat_query_sampler import sample_chat_queries  # noqa: E402
from app.config import config  # noqa: E402
from app.db import async_session_maker  # noqa: E402
from app.utils.pat import resolve_pat  # noqa: E402

logger = logging.getLogger(__name__)


def _get_salt(args: argparse.Namespace) -> str:
    salt = args.salt or os.getenv("QUERY_SAMPLER_SALT")
    if not salt:
        print(
            "ERROR: QUERY_SAMPLER_SALT is required (pass --salt or set env).",
            file=sys.stderr,
        )
        sys.exit(1)
    return salt


def _get_pat(args: argparse.Namespace) -> str:
    token = args.pat or os.getenv("QUERY_SAMPLER_PAT")
    if not token:
        print(
            "ERROR: a personal access token is required (pass --pat or set QUERY_SAMPLER_PAT).",
            file=sys.stderr,
        )
        sys.exit(1)
    return token


async def _main(args: argparse.Namespace) -> None:
    salt = _get_salt(args)
    token = _get_pat(args)

    if not args.output and not args.dry_run:
        print("ERROR: --output is required unless --dry-run is set.", file=sys.stderr)
        sys.exit(1)

    async with async_session_maker() as session:
        pat = await resolve_pat(session, token)
        if pat is None:
            print("ERROR: invalid or expired personal access token.", file=sys.stderr)
            sys.exit(1)
        if not pat.user.is_superuser:
            print(
                "ERROR: this action requires a platform admin token.",
                file=sys.stderr,
            )
            sys.exit(1)

        rows = await sample_chat_queries(
            session,
            days=args.days,
            max_queries=args.max_queries,
            salt=salt,
            dry_run=args.dry_run,
        )

    if args.dry_run:
        print(f"Dry run: would sample {len(rows)} queries.")
        return

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")

    print(f"Wrote {len(rows)} sampled queries to {output_path}")
    if args.output and config.DATABASE_URL and "localhost" not in config.DATABASE_URL:
        logger.warning(
            "Confirm this run used a read-replica or sanitized backup, not the primary DB."
        )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Sample production chat queries for the chat/regression benchmark."
    )
    parser.add_argument(
        "--pat",
        help="Admin personal access token (or set QUERY_SAMPLER_PAT).",
    )
    parser.add_argument(
        "--salt",
        help="Workspace hashing salt (or set QUERY_SAMPLER_SALT).",
    )
    parser.add_argument(
        "--days",
        type=int,
        default=30,
        help="Only sample messages from the last N days (default: 30).",
    )
    parser.add_argument(
        "--max-queries",
        type=int,
        default=100,
        help="Maximum number of queries to sample (default: 100).",
    )
    parser.add_argument(
        "--output",
        help="Path to write the JSONL dataset.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Run the query and report the count without writing a file.",
    )
    args = parser.parse_args()
    asyncio.run(_main(args))


if __name__ == "__main__":
    main()
