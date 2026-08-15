"""Promo Code & Voucher Management Service (Story 21.7 / AC-5).

Handles promo code creation, validation, row-level locking concurrency protection,
and atomic wallet credit additions.
"""

from __future__ import annotations

import logging
import re
from datetime import UTC, datetime
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import (
    PromoCode,
    PromoCodeRedemption,
    User,
)
from app.schemas.promo_code import (
    PromoCodeClaimResponse,
    PromoCodeCreateRequest,
)

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


class PromoCodeError(Exception):
    """Base exception for promo code errors."""


class PromoCodeNotFoundError(PromoCodeError):
    """Promo code not found or inactive."""


class PromoCodeExpiredError(PromoCodeError):
    """Promo code has expired."""


class PromoCodeExhaustedError(PromoCodeError):
    """Promo code has reached max uses."""


class PromoCodeAlreadyRedeemedError(PromoCodeError):
    """User has already claimed this promo code."""


class PromoCodeAlreadyExistsError(PromoCodeError):
    """Promo code with this code string already exists."""


class PromoCodeService:
    """Service for validating and redeeming promo codes."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    def normalize_code(self, raw_code: str) -> str:
        """Strip whitespace, unicode control characters, and convert to uppercase."""
        cleaned = re.sub(r"[\u200B-\u200D\uFEFF\u00A0\s]+", "", raw_code)
        return cleaned.upper()

    async def has_user_redeemed(self, user_id: UUID, promo_code_id: UUID) -> bool:
        """Check if user has previously redeemed this code."""
        stmt = select(PromoCodeRedemption).where(
            PromoCodeRedemption.user_id == user_id,
            PromoCodeRedemption.promo_code_id == promo_code_id,
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none() is not None

    async def claim_promo_code(
        self, user: User, code_input: str
    ) -> PromoCodeClaimResponse:
        """Atomically claim a promo code and credit the user's wallet."""
        normalized = self.normalize_code(code_input)

        # 1. Fetch promo code with FOR UPDATE lock to prevent race conditions
        stmt = select(PromoCode).where(PromoCode.code == normalized).with_for_update()
        result = await self.session.execute(stmt)
        promo = result.scalar_one_or_none()

        if not promo or not promo.is_active:
            logger.warning(
                "Promo code not found or inactive: %s (User %s)", normalized, user.id
            )
            raise PromoCodeNotFoundError(
                f"Mã khuyến mãi '{normalized}' không tồn tại hoặc đã bị vô hiệu hóa."
            )

        # 2. Check expiration (Timezone-aware UTC)
        now = datetime.now(UTC)
        expires_at_utc = (
            promo.expires_at.replace(tzinfo=UTC)
            if promo.expires_at and promo.expires_at.tzinfo is None
            else promo.expires_at
        )
        if expires_at_utc and expires_at_utc < now:
            logger.warning("Promo code expired: %s (User %s)", normalized, user.id)
            raise PromoCodeExpiredError(
                f"Mã khuyến mãi '{normalized}' đã hết hạn sử dụng."
            )

        # 3. Check usage limit
        if promo.max_uses is not None and promo.uses_count >= promo.max_uses:
            logger.warning("Promo code exhausted: %s (User %s)", normalized, user.id)
            raise PromoCodeExhaustedError(
                f"Mã khuyến mãi '{normalized}' đã hết lượt sử dụng."
            )

        # 4. Check if user already redeemed
        if await self.has_user_redeemed(user.id, promo.id):
            logger.warning(
                "User %s already redeemed promo code %s", user.id, normalized
            )
            raise PromoCodeAlreadyRedeemedError(
                f"Bạn đã sử dụng mã khuyến mãi '{normalized}' trước đó rồi."
            )

        # 5. Apply redemption
        promo.uses_count += 1

        redemption = PromoCodeRedemption(
            id=uuid4(),
            user_id=user.id,
            promo_code_id=promo.id,
            credit_micros_granted=promo.credit_micros_granted,
            redeemed_at=now,
        )
        self.session.add(redemption)

        # 6. Lock and refresh user row in the current session to prevent Lost Updates
        user_stmt = select(User).where(User.id == user.id).with_for_update()
        user_res = await self.session.execute(user_stmt)
        db_user = user_res.scalar_one_or_none()

        if db_user:
            db_user.credit_micros_balance = (
                db_user.credit_micros_balance or 0
            ) + promo.credit_micros_granted
            new_balance = db_user.credit_micros_balance
        else:
            user.credit_micros_balance = (
                user.credit_micros_balance or 0
            ) + promo.credit_micros_granted
            new_balance = user.credit_micros_balance

        try:
            await self.session.commit()
        except IntegrityError as e:
            await self.session.rollback()
            raise PromoCodeAlreadyRedeemedError(
                f"Bạn đã sử dụng mã khuyến mãi '{normalized}' trước đó rồi."
            ) from e

        logger.info(
            "Successfully claimed promo code %s for User %s (+%d micros, new balance %d)",
            normalized,
            user.id,
            promo.credit_micros_granted,
            new_balance,
        )

        return PromoCodeClaimResponse(
            code=promo.code,
            credit_micros_granted=promo.credit_micros_granted,
            new_balance_micros=new_balance,
            message="Nhận mã khuyến mãi thành công! Số dư credit đã được cập nhật.",
        )

    async def create_promo_code(
        self,
        request: PromoCodeCreateRequest,
        created_by_user_id: UUID | None = None,
    ) -> PromoCode:
        """Create a new promo code (Admin only)."""
        normalized = self.normalize_code(request.code)

        existing_stmt = select(PromoCode).where(PromoCode.code == normalized)
        existing = await self.session.execute(existing_stmt)
        if existing.scalar_one_or_none():
            raise PromoCodeAlreadyExistsError(
                f"Mã khuyến mãi '{normalized}' đã tồn tại trong hệ thống."
            )

        promo = PromoCode(
            id=uuid4(),
            code=normalized,
            credit_micros_granted=request.credit_micros_granted,
            max_uses=request.max_uses,
            uses_count=0,
            expires_at=request.expires_at,
            is_active=request.is_active,
            created_by_user_id=created_by_user_id,
        )
        self.session.add(promo)
        try:
            await self.session.commit()
        except IntegrityError as e:
            await self.session.rollback()
            raise PromoCodeAlreadyExistsError(
                f"Mã khuyến mãi '{normalized}' đã tồn tại trong hệ thống."
            ) from e

        return promo
