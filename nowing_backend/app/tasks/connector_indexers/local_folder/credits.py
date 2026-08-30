"""Local folder ETL credit estimation helpers."""

from __future__ import annotations

import os

from app.services.etl_credit_service import EtlCreditService


def _estimate_pages_safe(etl_credit_service: EtlCreditService, file_path: str) -> int:
    """Estimate page count with a file-size fallback."""
    try:
        return etl_credit_service.estimate_pages_before_processing(file_path)
    except Exception:
        file_size = os.path.getsize(file_path)
        return max(1, file_size // (80 * 1024))


async def _check_credits_or_skip(
    etl_credit_service: EtlCreditService,
    user_id: str,
    file_path: str,
    page_multiplier: int = 1,
) -> tuple[int, int]:
    """Estimate pages and check credit; raises InsufficientCreditsError if unaffordable.

    Returns (estimated_pages, billable_pages).
    """
    estimated = _estimate_pages_safe(etl_credit_service, file_path)
    billable = estimated * page_multiplier
    await etl_credit_service.check_credits(user_id, billable)
    return estimated, billable


def _compute_final_pages(
    etl_credit_service: EtlCreditService,
    estimated_pages: int,
    content_length: int,
) -> int:
    """Return the final page count as max(estimated, actual)."""
    actual = etl_credit_service.estimate_pages_from_content_length(content_length)
    return max(estimated_pages, actual)
