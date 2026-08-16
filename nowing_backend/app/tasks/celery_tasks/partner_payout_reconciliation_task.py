"""Celery task for auto-reconciling in-flight partner payouts (Story 23.3 / INV-23.11)."""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.celery_app import celery_app
from app.config import config
from app.db import PartnerPayout
from app.services.partner_payout_service import PartnerPayoutService
from app.services.vietqr_payout_client import VietQRPayoutClient
from app.tasks.celery_tasks import get_celery_session_maker, run_async_celery_task

logger = logging.getLogger(__name__)


@celery_app.task(name="reconcile_pending_partner_payouts")
def reconcile_pending_partner_payouts_task():
    """Recover and reconcile in-flight payouts stuck in 'processing' state."""
    return run_async_celery_task(_reconcile_pending_partner_payouts)


async def _reconcile_pending_partner_payouts() -> None:
    """Query Napas / VietQR gateway for all payouts stuck in 'processing' status."""
    lookback_minutes = getattr(
        config, "PARTNER_PAYOUT_RECONCILIATION_LOOKBACK_MINUTES", 5
    )
    cutoff = datetime.now(UTC) - timedelta(minutes=lookback_minutes)

    client = VietQRPayoutClient(
        client_id=getattr(config, "VIETQR_CLIENT_ID", "") or "",
        api_key=getattr(config, "VIETQR_API_KEY", "") or "",
        webhook_secret=getattr(config, "VIETQR_WEBHOOK_SECRET", "") or "",
    )

    session_maker = get_celery_session_maker()
    async with session_maker() as db_session:
        stuck_payout_ids = (
            (
                await db_session.execute(
                    select(PartnerPayout.id)
                    .where(
                        PartnerPayout.status == "processing",
                        PartnerPayout.tx_reference.is_not(None),
                        PartnerPayout.updated_at <= cutoff,
                    )
                    .order_by(PartnerPayout.updated_at.asc())
                    .limit(50)
                )
            )
            .scalars()
            .all()
        )

        if not stuck_payout_ids:
            return

        logger.info(
            "Found %d in-flight payouts to reconcile against VietQR/Napas gateway",
            len(stuck_payout_ids),
        )

        for payout_id in stuck_payout_ids:
            async with session_maker() as item_session:
                try:
                    stmt = (
                        select(PartnerPayout)
                        .options(selectinload(PartnerPayout.partner))
                        .where(PartnerPayout.id == payout_id)
                        .with_for_update()
                    )
                    payout_res = await item_session.execute(stmt)
                    payout = payout_res.scalar_one_or_none()
                    if not payout or payout.status != "processing":
                        continue

                    await PartnerPayoutService.reconcile_payout_status(
                        session=item_session,
                        payout=payout,
                        client=client,
                    )
                    await item_session.commit()
                except Exception as e:
                    logger.error(
                        "Failed to auto-reconcile payout %s: %s",
                        payout_id,
                        e,
                        exc_info=True,
                    )
                    await item_session.rollback()
