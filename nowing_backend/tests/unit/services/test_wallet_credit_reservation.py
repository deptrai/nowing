"""Unit tests for 2-phase credit locking in wallet_credit (Story 33.3)."""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.etl_credit_service import InsufficientCreditsError
from app.services.wallet_credit import (
    commit_reserved_credit,
    release_credit,
    reserve_credit,
)

pytestmark = [pytest.mark.unit]


class TestWalletCreditReservation:
    """Test reserve, release, and commit operations."""

    @pytest.mark.asyncio
    async def test_reserve_credit_success(self):
        """reserve_credit increases reserved balance when available."""
        session = AsyncMock()
        user = MagicMock()
        user.credit_micros_balance = 5_000_000
        user.credit_micros_reserved = 1_000_000

        result_mock = MagicMock()
        result_mock.unique.return_value.scalar_one_or_none.return_value = user
        session.execute.return_value = result_mock

        new_reserved = await reserve_credit(session, uuid.uuid4(), 2_000_000)

        assert user.credit_micros_reserved == 3_000_000
        assert new_reserved == 3_000_000
        session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_reserve_credit_insufficient_raises(self):
        """reserve_credit raises InsufficientCreditsError when spendable < needed."""
        session = AsyncMock()
        user = MagicMock()
        user.credit_micros_balance = 3_000_000
        user.credit_micros_reserved = 2_500_000  # only 500k available

        result_mock = MagicMock()
        result_mock.unique.return_value.scalar_one_or_none.return_value = user
        session.execute.return_value = result_mock

        with pytest.raises(InsufficientCreditsError, match="Insufficient credits to reserve"):
            await reserve_credit(session, uuid.uuid4(), 1_000_000)

    @pytest.mark.asyncio
    async def test_release_credit_decreases_reserved(self):
        """release_credit decreases reserved balance without touching balance."""
        session = AsyncMock()
        user = MagicMock()
        user.credit_micros_balance = 5_000_000
        user.credit_micros_reserved = 2_000_000

        result_mock = MagicMock()
        result_mock.unique.return_value.scalar_one_or_none.return_value = user
        session.execute.return_value = result_mock

        new_reserved = await release_credit(session, uuid.uuid4(), 1_500_000)

        assert user.credit_micros_reserved == 500_000
        assert user.credit_micros_balance == 5_000_000  # balance unchanged
        assert new_reserved == 500_000
        session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_release_credit_clamps_at_zero(self):
        """release_credit does not go below zero."""
        session = AsyncMock()
        user = MagicMock()
        user.credit_micros_balance = 5_000_000
        user.credit_micros_reserved = 500_000

        result_mock = MagicMock()
        result_mock.unique.return_value.scalar_one_or_none.return_value = user
        session.execute.return_value = result_mock

        new_reserved = await release_credit(session, uuid.uuid4(), 1_000_000)

        assert user.credit_micros_reserved == 0
        assert new_reserved == 0

    @pytest.mark.asyncio
    async def test_commit_reserved_credit_deducts_both(self):
        """commit_reserved_credit deducts from both balance and reserved."""
        session = AsyncMock()
        user = MagicMock()
        user.credit_micros_balance = 5_000_000
        user.credit_micros_reserved = 1_500_000

        result_mock = MagicMock()
        result_mock.unique.return_value.scalar_one_or_none.return_value = user
        session.execute.return_value = result_mock

        new_balance = await commit_reserved_credit(session, uuid.uuid4(), 1_500_000)

        assert user.credit_micros_balance == 3_500_000
        assert user.credit_micros_reserved == 0
        assert new_balance == 3_500_000
        session.commit.assert_called_once()
