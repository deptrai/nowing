#!/usr/bin/env python3
"""Seed E2E data for production workspace 15 ("E2E Test Workspace").

Idempotent — every row carries ``source='e2e-seed'`` (or equivalent in
``document_metadata.source``) so re-runs upsert rather than duplicate, and
``teardown_e2e_prod.py`` can clean up without touching real data.

Modes:
- ``--local`` (default): run against local ``DATABASE_URL`` for dev.
- ``--ssh nowing``: pipe this file's contents into the backend container
  via ``ssh nowing 'docker exec -i nowing-backend python -'`` — the script
  reuses the container's env (DATABASE_URL, SECRET_KEY, deps) so it works
  byte-identical to local.
- ``--dry-run``: print intended actions, no commits.
- ``--force``: skip ENVIRONMENT safety check (required on prod since
  ``ENVIRONMENT=production`` would otherwise refuse).

What it seeds (all inside workspace id=15 unless noted):
- Workspace 15: ``web_builder_enabled=True``, ``presentation_studio_enabled=True``.
- User ``e2e-member@nowing.net`` / ``E2ePassword123!`` (Viewer role — non-owner
  read-only; the system has no "Member" role, Viewer is the equivalent).
- 10 ``Lead`` rows, ``source='e2e-seed'``, canary-token company names.
- 5 ``WorkspaceDncRecord``, ``source='e2e-seed'`` (phone + domain + email).
- 1 ``WorkspaceTable`` "E2E Leads Table" (filter preset selects source=e2e-seed).
- 3 ``Document`` rows, ``document_type=FILE``, ``document_metadata.source='e2e-seed'``,
  content embeds ``CANARY_TOKENS`` from ``nowing_web/tests/helpers/canary.ts``.
- 3 ``WorkspaceMcpToolSetting`` rows (slack_send_message, linear_save_issue,
  jira_createJiraIssue) ``enabled=True``.

Run::

    ENVIRONMENT=development uv run --active python scripts/seed_e2e_prod.py --local
    uv run python scripts/seed_e2e_prod.py --ssh nowing --force
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import os
import subprocess
import sys
import uuid
from datetime import UTC, datetime
from pathlib import Path

# Make ``nowing_backend/`` importable when run from repo root or the backend dir.
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(_SCRIPT_DIR)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

WORKSPACE_ID = 15
E2E_MEMBER_EMAIL = "e2e-member@nowing.net"
E2E_MEMBER_PASSWORD = "E2ePassword123!"
E2E_SOURCE_TAG = "e2e-seed"

# Canary tokens — keep in sync with nowing_web/tests/helpers/canary.ts.
CANARY_DRIVE_FILE = "NOWING_E2E_CANARY_TOKEN_DRIVE_001"
CANARY_MANUAL_MD = "E2E-MANUAL-UPLOAD-MD-CANARY-7f3a"
CANARY_MANUAL_PDF = "E2E-MANUAL-UPLOAD-PDF-CANARY-9d2b"

LEAD_COMPANIES = [
    ("E2E Canary Alpha", "alpha.e2e.nowing.net"),
    ("E2E Canary Beta", "beta.e2e.nowing.net"),
    ("E2E Canary Gamma", "gamma.e2e.nowing.net"),
    ("E2E Canary Delta", "delta.e2e.nowing.net"),
    ("E2E Canary Epsilon", "epsilon.e2e.nowing.net"),
    ("E2E Canary Zeta", "zeta.e2e.nowing.net"),
    ("E2E Canary Eta", "eta.e2e.nowing.net"),
    ("E2E Canary Theta", "theta.e2e.nowing.net"),
    ("E2E Canary Iota", "iota.e2e.nowing.net"),
    ("E2E Canary Kappa", "kappa.e2e.nowing.net"),
]

DNC_RECORDS = [
    ("phone", "+84901234567"),
    ("phone", "+84902222222"),
    ("domain", "blocked-competitor.e2e.nowing.net"),
    ("email", "do-not-contact@e2e.nowing.net"),
    ("email", "opt-out@e2e.nowing.net"),
]

MCP_TOOLS = [
    "slack_send_message",
    "linear_save_issue",
    "jira_createJiraIssue",
]

E2E_TABLE_NAME = "E2E Leads Table"


def _env_safe() -> bool:
    env = os.getenv("ENVIRONMENT", "development").lower()
    return env in {"development", "dev", "test", "testing", "local"}


def _require_dev_environment(force: bool) -> None:
    if force:
        return
    if not _env_safe():
        print(
            f"ERROR: refusing to seed E2E data in ENVIRONMENT="
            f"{os.getenv('ENVIRONMENT')!r}. Pass --force to override."
        )
        sys.exit(1)


# ---------------------------------------------------------------------------
# Seed primitives — import lazily so `--ssh` mode can run the same file inside
# the backend container without re-exporting paths.
# ---------------------------------------------------------------------------


def _lead_hmac(workspace_id: int, company_name: str, domain: str | None) -> str:
    key = f"{workspace_id}:{domain or ''}:{company_name.strip().lower()}"
    return hashlib.sha256(key.encode("utf-8")).hexdigest()


def _doc_unique_hash(workspace_id: int, title: str) -> str:
    return hashlib.sha256(
        f"{workspace_id}:{E2E_SOURCE_TAG}:{title}".encode()
    ).hexdigest()


def _doc_content_hash(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


async def _get_or_create_member_user(session, dry_run: bool):
    """Create or fetch the ``e2e-member@nowing.net`` user (Viewer role)."""
    from fastapi_users.password import PasswordHelper
    from sqlalchemy import select

    from app.db import User

    result = await session.execute(select(User).where(User.email == E2E_MEMBER_EMAIL))
    user = result.scalar_one_or_none()
    if user is not None:
        print(f"  user {E2E_MEMBER_EMAIL} exists (id={user.id})")
        return user

    if dry_run:
        print(f"  [dry] would create user {E2E_MEMBER_EMAIL}")
        return None

    helper = PasswordHelper()
    user = User(
        id=uuid.uuid4(),
        email=E2E_MEMBER_EMAIL,
        hashed_password=helper.hash(E2E_MEMBER_PASSWORD),
        is_active=True,
        is_superuser=False,
        is_verified=True,
        display_name="E2E Member",
    )
    session.add(user)
    await session.flush()
    print(f"  created user {E2E_MEMBER_EMAIL} (id={user.id})")
    return user


async def _ensure_viewer_role(session, dry_run: bool) -> int | None:
    """Ensure a Viewer role exists on workspace 15; return role_id."""
    from sqlalchemy import select

    from app.db import WorkspaceRole

    result = await session.execute(
        select(WorkspaceRole).where(
            WorkspaceRole.workspace_id == WORKSPACE_ID,
            WorkspaceRole.name == "Viewer",
        )
    )
    role = result.scalar_one_or_none()
    if role is not None:
        return role.id

    if dry_run:
        print("  [dry] would create Viewer role on ws15")
        return None

    from app.db import get_default_roles_config

    cfg = next(r for r in get_default_roles_config() if r["name"] == "Viewer")
    role = WorkspaceRole(
        name=cfg["name"],
        description=cfg["description"],
        permissions=cfg["permissions"],
        is_default=cfg["is_default"],
        is_system_role=cfg["is_system_role"],
        workspace_id=WORKSPACE_ID,
    )
    session.add(role)
    await session.flush()
    print(f"  created Viewer role id={role.id} on ws{WORKSPACE_ID}")
    return role.id


async def _ensure_membership(session, user, role_id: int, dry_run: bool) -> None:
    from sqlalchemy import select

    from app.db import WorkspaceMembership

    result = await session.execute(
        select(WorkspaceMembership).where(
            WorkspaceMembership.user_id == user.id,
            WorkspaceMembership.workspace_id == WORKSPACE_ID,
        )
    )
    if result.scalar_one_or_none() is not None:
        print(f"  membership {user.email} → ws{WORKSPACE_ID} exists")
        return

    if dry_run:
        print(f"  [dry] would add membership {user.email} → ws{WORKSPACE_ID}")
        return

    session.add(
        WorkspaceMembership(
            user_id=user.id,
            workspace_id=WORKSPACE_ID,
            role_id=role_id,
            is_owner=False,
            joined_at=datetime.now(UTC),
        )
    )
    print(f"  added membership {user.email} → ws{WORKSPACE_ID} role_id={role_id}")


async def _ensure_workspace_flags(session, dry_run: bool) -> None:
    """Force workspace 15 feature flags ON (idempotent UPDATE)."""
    from sqlalchemy import select

    from app.db import Workspace

    result = await session.execute(
        select(Workspace).where(Workspace.id == WORKSPACE_ID)
    )
    ws = result.scalar_one_or_none()
    if ws is None:
        print(
            f"  ERROR: workspace {WORKSPACE_ID} not found — "
            "cannot proceed. Verify prod state."
        )
        sys.exit(2)

    updates: list[str] = []
    if not ws.web_builder_enabled:
        updates.append("web_builder_enabled")
        if not dry_run:
            ws.web_builder_enabled = True
    if not ws.presentation_studio_enabled:
        updates.append("presentation_studio_enabled")
        if not dry_run:
            ws.presentation_studio_enabled = True

    if dry_run:
        print(
            f"  [dry] ws{WORKSPACE_ID} feature flags: would set {updates or '[]'}"
        )
    elif updates:
        print(f"  ws{WORKSPACE_ID} enabled flags: {updates}")
    else:
        print(f"  ws{WORKSPACE_ID} feature flags already enabled")


async def _seed_leads(session, dry_run: bool) -> int:
    """Idempotent insert of 10 Lead rows source='e2e-seed'.

    Uses plain SQL rather than the ORM ``Lead`` entity: older prod schemas lack
    the ``embedding``/``search_vector`` columns that the current model declares,
    and an ORM flush would emit them (plus a ``RETURNING search_vector``) →
    UndefinedColumnError. Writing only the columns that exist keeps the seed
    portable across schema versions.
    """
    from sqlalchemy import text

    exists_sql = text(
        "SELECT id FROM leads WHERE workspace_id = :ws AND value_hmac = :vh LIMIT 1"
    )
    insert_sql = text(
        """
        INSERT INTO leads (
            id, workspace_id, client_id, source, company_name, domain, industry,
            company_size, location, fit_score, intent_score, composite_score,
            status, enriched, value_hmac
        ) VALUES (
            :id, :ws, :client_id, :source, :company_name, :domain, :industry,
            :company_size, :location, :fit_score, :intent_score,
            :composite_score, :status, :enriched, :value_hmac
        )
        """
    )

    base_vals = {
        "ws": WORKSPACE_ID,
        "client_id": "e2e-prod",
        "source": E2E_SOURCE_TAG,
        "industry": "e2e-test",
        "company_size": "11-50",
        "location": "Ho Chi Minh City",
        "fit_score": 0.85,
        "intent_score": 0.75,
        "composite_score": 0.80,
        "status": "new",
        "enriched": False,
    }

    created = 0
    for company, domain in LEAD_COMPANIES:
        hmac = _lead_hmac(WORKSPACE_ID, company, domain)
        exists = await session.execute(exists_sql, {"ws": WORKSPACE_ID, "vh": hmac})
        if exists.first() is not None:
            continue
        if dry_run:
            created += 1
            continue

        await session.execute(
            insert_sql,
            {
                "id": uuid.uuid4(),
                "company_name": company,
                "domain": domain,
                "value_hmac": hmac,
                **base_vals,
            },
        )
        created += 1

    if dry_run:
        print(f"  [dry] would create {created} leads")
    else:
        print(f"  created {created} leads (ws{WORKSPACE_ID})")
    return created


async def _seed_dnc(session, dry_run: bool) -> int:
    """Idempotent insert of WorkspaceDncRecord rows source='e2e-seed'.

    The runtime DNC matcher hashes with keyed HMAC-SHA256 over the *normalized*
    value (E.164 phone, lowercase email, hostname-only domain) — see
    ``app.lead_intelligence.dnc.normalizer.hash_phone_hmac`` and the service at
    ``app/lead_intelligence/dnc/service.py``. Seeding with plain sha256 would
    produce rows the matcher never hits. We reuse the real normalizers here so
    seeded DNC entries actually suppress outbound traffic.
    """
    from sqlalchemy import select

    from app.db import WorkspaceDncRecord
    from app.lead_intelligence.dnc.normalizer import (
        hash_phone_hmac,
        normalize_domain,
        normalize_email,
        normalize_phone_e164,
    )

    def _value_hmac(record_type: str, value: str) -> str:
        if record_type == "phone":
            norm = normalize_phone_e164(value) or value
            return hash_phone_hmac(norm)
        if record_type == "email":
            norm = normalize_email(value) or value
            return hash_phone_hmac(norm)
        if record_type == "domain":
            norm = normalize_domain(value) or value
            return hash_phone_hmac(norm)
        return hash_phone_hmac(value)

    created = 0
    for record_type, value in DNC_RECORDS:
        vh = _value_hmac(record_type, value)
        result = await session.execute(
            select(WorkspaceDncRecord).where(
                WorkspaceDncRecord.workspace_id == WORKSPACE_ID,
                WorkspaceDncRecord.record_type == record_type,
                WorkspaceDncRecord.value_hmac == vh,
            )
        )
        if result.scalar_one_or_none() is not None:
            continue
        if dry_run:
            created += 1
            continue
        session.add(
            WorkspaceDncRecord(
                id=uuid.uuid4(),
                workspace_id=WORKSPACE_ID,
                record_type=record_type,
                value=value,
                value_hmac=vh,
                reason="E2E test opt-out",
                source=E2E_SOURCE_TAG,
            )
        )
        created += 1

    if dry_run:
        print(f"  [dry] would create {created} DNC records")
    else:
        print(f"  created {created} DNC records (ws{WORKSPACE_ID})")
    return created


async def _seed_workspace_table(session, dry_run: bool) -> None:
    """Idempotent insert of the ``E2E Leads Table`` saved view."""
    from sqlalchemy import select

    from app.db import WorkspaceTable

    result = await session.execute(
        select(WorkspaceTable).where(
            WorkspaceTable.workspace_id == WORKSPACE_ID,
            WorkspaceTable.name == E2E_TABLE_NAME,
        )
    )
    if result.scalar_one_or_none() is not None:
        print(f"  workspace table '{E2E_TABLE_NAME}' exists")
        return

    if dry_run:
        print(f"  [dry] would create workspace table '{E2E_TABLE_NAME}'")
        return

    session.add(
        WorkspaceTable(
            id=uuid.uuid4(),
            workspace_id=WORKSPACE_ID,
            name=E2E_TABLE_NAME,
            icon="table",
            filter_preset={"source": [E2E_SOURCE_TAG]},
            columns_config={
                "columns": [
                    "company_name",
                    "domain",
                    "industry",
                    "fit_score",
                    "status",
                ]
            },
        )
    )
    print(f"  created workspace table '{E2E_TABLE_NAME}'")


async def _seed_documents(session, member_user, dry_run: bool) -> int:
    """Idempotent insert of Document rows with canary content."""
    from sqlalchemy import select

    from app.db import Document, DocumentType

    docs = [
        (
            "e2e-canary.txt",
            f"# E2E Canary Document\n\n{CANARY_DRIVE_FILE}\n\n"
            "This file was seeded by seed_e2e_prod.py to prove indexing works "
            "end-to-end against production. Do not edit manually — teardown "
            "removes it via document_metadata.source='e2e-seed'.\n",
        ),
        (
            "e2e-manual-upload.md",
            f"# Manual Upload Canary\n\n{CANARY_MANUAL_MD}\n\n"
            "Markdown seed for the manual-upload spec on prod.\n",
        ),
        (
            "e2e-manual-upload.pdf",
            f"%PDF-E2E\n\n{CANARY_MANUAL_PDF}\n\n"
            "PDF seed for the manual-upload spec on prod (raw text fallback).\n",
        ),
    ]

    created = 0
    for title, content in docs:
        uih = _doc_unique_hash(WORKSPACE_ID, title)
        result = await session.execute(
            select(Document).where(Document.unique_identifier_hash == uih)
        )
        if result.scalar_one_or_none() is not None:
            continue
        if dry_run:
            created += 1
            continue

        session.add(
            Document(
                title=title,
                document_type=DocumentType.FILE,
                content=content,
                content_hash=_doc_content_hash(content),
                unique_identifier_hash=uih,
                workspace_id=WORKSPACE_ID,
                created_by_id=member_user.id if member_user else None,
                document_metadata={"source": E2E_SOURCE_TAG},
                status={"state": "ready"},
            )
        )
        created += 1

    if dry_run:
        print(f"  [dry] would create {created} documents")
    else:
        print(f"  created {created} documents (ws{WORKSPACE_ID})")
    return created


async def _seed_mcp_tool_settings(session, dry_run: bool) -> int:
    """Idempotent insert of WorkspaceMcpToolSetting rows."""
    from sqlalchemy import select

    from app.db import WorkspaceMcpToolSetting

    created = 0
    for tool_name in MCP_TOOLS:
        result = await session.execute(
            select(WorkspaceMcpToolSetting).where(
                WorkspaceMcpToolSetting.workspace_id == WORKSPACE_ID,
                WorkspaceMcpToolSetting.tool_name == tool_name,
            )
        )
        existing = result.scalar_one_or_none()
        if existing is not None:
            if not existing.enabled and not dry_run:
                existing.enabled = True
            continue
        if dry_run:
            created += 1
            continue
        session.add(
            WorkspaceMcpToolSetting(
                workspace_id=WORKSPACE_ID,
                tool_name=tool_name,
                enabled=True,
            )
        )
        created += 1

    if dry_run:
        print(f"  [dry] would create {created} MCP tool settings")
    else:
        print(f"  created {created} MCP tool settings (ws{WORKSPACE_ID})")
    return created


async def seed(dry_run: bool = False) -> None:
    from app.db import async_session_maker

    async with async_session_maker() as session:
        print(f"Seeding E2E data for workspace {WORKSPACE_ID} (dry_run={dry_run})")

        await _ensure_workspace_flags(session, dry_run)

        member_user = await _get_or_create_member_user(session, dry_run)
        viewer_role_id = await _ensure_viewer_role(session, dry_run)
        if member_user is not None and viewer_role_id is not None:
            await _ensure_membership(session, member_user, viewer_role_id, dry_run)

        await _seed_leads(session, dry_run)
        await _seed_dnc(session, dry_run)
        await _seed_workspace_table(session, dry_run)
        await _seed_documents(session, member_user, dry_run)
        await _seed_mcp_tool_settings(session, dry_run)

        if dry_run:
            print("[dry] skipping commit")
            await session.rollback()
        else:
            await session.commit()
            print("Committed.")


# ---------------------------------------------------------------------------
# Entry points
# ---------------------------------------------------------------------------


def _run_ssh(host: str, container: str, dry_run: bool, force: bool) -> int:
    """Pipe this file into the backend container over SSH and execute it."""
    extra = []
    if dry_run:
        extra.append("--dry-run")
    if force:
        extra.append("--force")
    cmd = [
        "ssh",
        host,
        f"docker exec -i {container} python - --local-run "
        + " ".join(extra),
    ]
    with Path(__file__).open("rb") as f:
        result = subprocess.run(cmd, stdin=f, check=False)
    return result.returncode


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Seed E2E test data into workspace 15."
    )
    parser.add_argument(
        "--local",
        action="store_true",
        help="Run against local DATABASE_URL (default when no --ssh).",
    )
    parser.add_argument(
        "--local-run",
        action="store_true",
        help=argparse.SUPPRESS,  # internal flag set by _run_ssh
    )
    parser.add_argument(
        "--ssh",
        metavar="HOST",
        help="Run inside the backend container via SSH (e.g. `--ssh nowing`).",
    )
    parser.add_argument(
        "--container",
        default="nowing-backend",
        help="Docker container name for --ssh mode (default: nowing-backend). "
        "On Swarm the API service is e.g. `nowing-backend-worker-*`; pass the "
        "resolved name via `docker ps`.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print intended actions without committing.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Skip ENVIRONMENT safety check (required on prod).",
    )
    args = parser.parse_args()

    # SSH entrypoint runs the file inside the backend container, which then
    # hits this same `main()` but with --local-run already set.
    if args.ssh and not args.local_run:
        _require_dev_environment(args.force)
        rc = _run_ssh(args.ssh, args.container, args.dry_run, args.force)
        sys.exit(rc)

    # Local path (also reached from inside the container via --local-run).
    _require_dev_environment(args.force)
    asyncio.run(seed(dry_run=args.dry_run))


if __name__ == "__main__":
    main()
