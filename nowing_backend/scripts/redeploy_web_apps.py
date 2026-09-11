"""Force-redeploy published web-builder apps (Story 31.1 rollout reconcile).

Apps published before Story 31.1 keep their old flat limits (512m / shared
dokploy-network) until force-redeployed. This script iterates WorkspaceApp
rows where ``status='published'`` and ``container_id IS NOT NULL`` and calls
``WebAppDeployService().deploy_app(..., force=True)`` with a fresh session
per app, sequentially (deploys already serialize per-app via deploy locks).

    uv run python scripts/redeploy_web_apps.py           # dry-run (default)
    uv run python scripts/redeploy_web_apps.py --apply   # actually redeploy

Note: free-tier apps drop 512m -> 256m memory on redeploy — watch for OOM
(OOMKilled=true surfaces in the deploy_failed error message).
"""

from __future__ import annotations

import argparse
import asyncio
import logging

from sqlalchemy import select

from app.db import WorkspaceApp, async_session_maker
from app.services.web_builder.deploy_service import WebAppDeployService

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s"
)
logger = logging.getLogger("redeploy_web_apps")


async def main(apply: bool) -> int:
    async with async_session_maker() as session:
        rows = (
            await session.execute(
                select(WorkspaceApp.id, WorkspaceApp.workspace_id).where(
                    WorkspaceApp.status == "published",
                    WorkspaceApp.container_id.is_not(None),
                )
            )
        ).all()
    logger.info("Found %d published apps with live containers", len(rows))

    if not apply:
        for app_id, workspace_id in rows:
            logger.info(
                "[dry-run] would redeploy app_id=%s workspace_id=%s",
                app_id,
                workspace_id,
            )
        return 0

    service = WebAppDeployService()
    failures = 0
    for app_id, workspace_id in rows:
        async with async_session_maker() as session:
            try:
                out = await service.deploy_app(
                    app_id=app_id,
                    workspace_id=workspace_id,
                    force=True,
                    session=session,
                )
                logger.info(
                    "app_id=%s -> %s (%s)", app_id, out.status, out.message
                )
                if out.status != "published":
                    failures += 1
            except Exception as exc:
                failures += 1
                logger.error("app_id=%s redeploy raised: %s", app_id, exc)
    logger.info(
        "Done: %d redeployed, %d failed", len(rows) - failures, failures
    )
    return 1 if failures else 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--apply",
        action="store_true",
        help="perform the redeploys (default is dry-run)",
    )
    args = parser.parse_args()
    raise SystemExit(asyncio.run(main(apply=args.apply)))
