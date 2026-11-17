#!/usr/bin/env python3
"""Remove every ``source='e2e-seed'`` row from workspace 15.

Idempotent — running twice is a no-op. Deletes data seeded by
``seed_e2e_prod.py``:

- ``leads`` WHERE ``source='e2e-seed'`` AND ``workspace_id=15``
- ``documents`` WHERE ``document_metadata->>'source'='e2e-seed'`` AND ``workspace_id=15``
- ``workspace_dnc_records`` WHERE ``source='e2e-seed'`` AND ``workspace_id=15``
- ``workspace_tables`` WHERE ``name='E2E Leads Table'`` AND ``workspace_id=15``
- ``workspace_mcp_tool_settings`` for the seeded tool names on workspace 15

What it does NOT delete (deliberate — these are not seed rows):
- The ``e2e-member@nowing.net`` user itself.
- The ``Viewer`` role + its ``WorkspaceMembership`` on ws 15.
- Workspace 15's feature flag values (left ON — cheap to flip manually).

Modes + flags match ``seed_e2e_prod.py``: ``--local``, ``--ssh HOST``,
``--dry-run``, ``--force``.
"""

from __future__ import annotations

import argparse
import asyncio
import os
import subprocess
import sys

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(_SCRIPT_DIR)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

WORKSPACE_ID = 15
E2E_SOURCE_TAG = "e2e-seed"
E2E_TABLE_NAME = "E2E Leads Table"
MCP_TOOLS = [
    "slack_send_message",
    "linear_save_issue",
    "jira_createJiraIssue",
]


def _env_safe() -> bool:
    env = os.getenv("ENVIRONMENT", "development").lower()
    return env in {"development", "dev", "test", "testing", "local"}


def _require_dev_environment(force: bool) -> None:
    if force:
        return
    if not _env_safe():
        print(
            f"ERROR: refusing to teardown E2E data in ENVIRONMENT="
            f"{os.getenv('ENVIRONMENT')!r}. Pass --force to override."
        )
        sys.exit(1)


async def teardown(dry_run: bool = False) -> None:
    from sqlalchemy import delete, select

    from app.db import (
        Document,
        Lead,
        WorkspaceDncRecord,
        WorkspaceMcpToolSetting,
        WorkspaceTable,
        async_session_maker,
    )

    async with async_session_maker() as session:
        print(
            f"Tearing down E2E data for workspace {WORKSPACE_ID} "
            f"(dry_run={dry_run})"
        )

        # --- leads ---
        stmt = (
            delete(Lead)
            .where(Lead.workspace_id == WORKSPACE_ID)
            .where(Lead.source == E2E_SOURCE_TAG)
            .execution_options(synchronize_session=False)
        )
        if dry_run:
            cnt = (
                await session.execute(
                    select(Lead).where(
                        Lead.workspace_id == WORKSPACE_ID,
                        Lead.source == E2E_SOURCE_TAG,
                    )
                )
            ).scalars().all()
            print(f"  [dry] would delete {len(cnt)} leads")
        else:
            result = await session.execute(stmt)
            print(f"  deleted {result.rowcount} leads")

        # --- documents (metadata JSONB) ---
        docs_query = select(Document).where(
            Document.workspace_id == WORKSPACE_ID,
            Document.document_metadata["source"].astext == E2E_SOURCE_TAG,
        )
        docs = (await session.execute(docs_query)).scalars().all()
        if dry_run:
            print(f"  [dry] would delete {len(docs)} documents")
        else:
            for doc in docs:
                await session.delete(doc)
            print(f"  deleted {len(docs)} documents")

        # --- workspace_dnc_records ---
        dnc_query = select(WorkspaceDncRecord).where(
            WorkspaceDncRecord.workspace_id == WORKSPACE_ID,
            WorkspaceDncRecord.source == E2E_SOURCE_TAG,
        )
        dncs = (await session.execute(dnc_query)).scalars().all()
        if dry_run:
            print(f"  [dry] would delete {len(dncs)} DNC records")
        else:
            for rec in dncs:
                await session.delete(rec)
            print(f"  deleted {len(dncs)} DNC records")

        # --- workspace_tables ---
        wt_query = select(WorkspaceTable).where(
            WorkspaceTable.workspace_id == WORKSPACE_ID,
            WorkspaceTable.name == E2E_TABLE_NAME,
        )
        wts = (await session.execute(wt_query)).scalars().all()
        if dry_run:
            print(f"  [dry] would delete {len(wts)} workspace tables")
        else:
            for t in wts:
                await session.delete(t)
            print(f"  deleted {len(wts)} workspace tables")

        # --- workspace_mcp_tool_settings ---
        mcp_query = select(WorkspaceMcpToolSetting).where(
            WorkspaceMcpToolSetting.workspace_id == WORKSPACE_ID,
            WorkspaceMcpToolSetting.tool_name.in_(MCP_TOOLS),
        )
        mcps = (await session.execute(mcp_query)).scalars().all()
        if dry_run:
            print(f"  [dry] would delete {len(mcps)} MCP tool settings")
        else:
            for m in mcps:
                await session.delete(m)
            print(f"  deleted {len(mcps)} MCP tool settings")

        if dry_run:
            print("[dry] skipping commit")
            await session.rollback()
        else:
            await session.commit()
            print("Committed.")


def _run_ssh(host: str, dry_run: bool, force: bool) -> int:
    extra = []
    if dry_run:
        extra.append("--dry-run")
    if force:
        extra.append("--force")
    cmd = [
        "ssh",
        host,
        "docker exec -i nowing-backend python - --local-run "
        + " ".join(extra),
    ]
    with open(__file__, "rb") as f:
        result = subprocess.run(cmd, stdin=f, check=False)
    return result.returncode


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Remove E2E seed data from workspace 15."
    )
    parser.add_argument(
        "--local",
        action="store_true",
        help="Run against local DATABASE_URL (default when no --ssh).",
    )
    parser.add_argument(
        "--local-run",
        action="store_true",
        help=argparse.SUPPRESS,
    )
    parser.add_argument(
        "--ssh",
        metavar="HOST",
        help="Run inside the backend container via SSH.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print intended actions without committing.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Skip ENVIRONMENT safety check.",
    )
    args = parser.parse_args()

    if args.ssh and not args.local_run:
        _require_dev_environment(args.force)
        rc = _run_ssh(args.ssh, args.dry_run, args.force)
        sys.exit(rc)

    _require_dev_environment(args.force)
    asyncio.run(teardown(dry_run=args.dry_run))


if __name__ == "__main__":
    main()
