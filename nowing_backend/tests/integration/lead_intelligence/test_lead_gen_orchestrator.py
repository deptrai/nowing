"""Red-phase integration tests for LeadGenOrchestrator DB persistence and Zero publication (Story 21.15)."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import User, Workspace

# Target module to be implemented in Story 21.15:
# from app.lead_intelligence.services.lead_gen_orchestrator import LeadGenOrchestrator
# from app.db import Lead

pytestmark = [pytest.mark.integration]


class TestLeadGenOrchestratorIntegration:
    """Integration tests for LeadGenOrchestrator with database and zero-cache pipeline."""

    @pytest.mark.asyncio
    async def test_orchestrator_persists_leads_to_postgresql(
        self,
        db_session: AsyncSession,
        db_workspace: Workspace,
        db_user: User,
    ) -> None:
        """Should execute orchestrator and persist deduplicated leads directly into DB."""
        from app.db import Lead
        from app.lead_intelligence.adapters.base import NormalizedLead
        from app.lead_intelligence.services.lead_gen_orchestrator import (
            LeadGenOrchestrator,
        )

        orchestrator = LeadGenOrchestrator()
        table_id = str(uuid4())

        mock_leads = [
            NormalizedLead(
                source_name="batdongsan",
                source_id="bds_integ_01",
                title="Bán nhà mặt phố Hoàn Kiếm",
                primary_phone="0911223344",
                contact_name="Nguyễn Văn A",
                price=30000000000,
                city="Hà Nội",
                confidence_score=85.0,
                sources=["batdongsan"],
            ),
            NormalizedLead(
                source_name="chotot",
                source_id="ct_integ_02",
                title="Bán căn hộ Ba Đình",
                primary_phone="0988776655",
                contact_name="Trần Thị B",
                price=5000000000,
                city="Hà Nội",
                confidence_score=80.0,
                sources=["chotot"],
            ),
        ]

        with patch.object(
            orchestrator,
            "_execute_adapter_searches",
            AsyncMock(return_value=mock_leads),
        ):
            result = await orchestrator.execute_and_persist(
                session=db_session,
                workspace_id=db_workspace.id,
                query="Tìm nhà đất trung tâm Hà Nội",
                table_id=table_id,
                user_id=db_user.id,
            )

            assert result.total_deduplicated == 2
            assert result.status == "completed"

            # Query database to verify rows were created in PostgreSQL
            stmt = select(Lead).where(
                Lead.workspace_id == db_workspace.id,
                Lead.table_id == table_id,
            )
            rows = (await db_session.execute(stmt)).scalars().all()
            assert len(rows) == 2
            phones = [r.phone for r in rows if r.phone]
            assert "0911223344" in phones
            assert "0988776655" in phones

    @pytest.mark.asyncio
    async def test_atomic_upsert_on_duplicate_conflict(
        self,
        db_session: AsyncSession,
        db_workspace: Workspace,
        db_user: User,
    ) -> None:
        """Repeated ingestion of the same phone number should update existing row without unique constraint crash."""
        from app.db import Lead
        from app.lead_intelligence.adapters.base import NormalizedLead
        from app.lead_intelligence.services.lead_gen_orchestrator import (
            LeadGenOrchestrator,
        )

        orchestrator = LeadGenOrchestrator()
        table_id = str(uuid4())

        initial_lead = NormalizedLead(
            source_name="batdongsan",
            source_id="bds_repeat_1",
            title="Bán nhà Hoàng Mai",
            primary_phone="0977112233",
            price=4000000000,
            confidence_score=70.0,
            sources=["batdongsan"],
        )
        updated_lead = NormalizedLead(
            source_name="chotot",
            source_id="ct_repeat_2",
            title="Bán nhà Hoàng Mai chính chủ giá tốt",
            primary_phone="0977112233",
            contact_name="Lê Văn C",
            price=3900000000,
            confidence_score=85.0,
            sources=["batdongsan", "chotot"],
        )

        with patch.object(
            orchestrator,
            "_execute_adapter_searches",
            AsyncMock(return_value=[initial_lead]),
        ):
            await orchestrator.execute_and_persist(
                session=db_session,
                workspace_id=db_workspace.id,
                query="Tìm nhà Hoàng Mai lần 1",
                table_id=table_id,
                user_id=db_user.id,
            )

        with patch.object(
            orchestrator,
            "_execute_adapter_searches",
            AsyncMock(return_value=[updated_lead]),
        ):
            # Second run with same phone
            await orchestrator.execute_and_persist(
                session=db_session,
                workspace_id=db_workspace.id,
                query="Tìm nhà Hoàng Mai lần 2",
                table_id=table_id,
                user_id=db_user.id,
            )

        stmt = select(Lead).where(
            Lead.workspace_id == db_workspace.id,
            Lead.phone == "0977112233",
        )
        rows = (await db_session.execute(stmt)).scalars().all()
        # Must be exactly 1 row (deduplicated / upserted)
        assert len(rows) == 1
        assert rows[0].contact_name == "Lê Văn C"
        assert rows[0].confidence_score >= 85.0

    @pytest.mark.asyncio
    async def test_workspace_isolation(
        self,
        db_session: AsyncSession,
        db_workspace: Workspace,
        db_user: User,
    ) -> None:
        """Workspace 1 leads must never be queryable or overwritten by Workspace 2."""
        from app.db import Lead
        from app.lead_intelligence.adapters.base import NormalizedLead
        from app.lead_intelligence.services.lead_gen_orchestrator import (
            LeadGenOrchestrator,
        )

        orchestrator = LeadGenOrchestrator()
        other_workspace_id = db_workspace.id + 999
        table_id = str(uuid4())

        lead_ws1 = NormalizedLead(
            source_name="topcv",
            source_id="topcv_isolated",
            title="Tuyển dụng IT",
            company_name="Công Ty WS1",
            primary_phone="0919998877",
            confidence_score=80.0,
            sources=["topcv"],
        )

        with patch.object(
            orchestrator,
            "_execute_adapter_searches",
            AsyncMock(return_value=[lead_ws1]),
        ):
            await orchestrator.execute_and_persist(
                session=db_session,
                workspace_id=db_workspace.id,
                query="Tìm IT WS1",
                table_id=table_id,
                user_id=db_user.id,
            )

        # Query other workspace
        stmt = select(Lead).where(
            Lead.workspace_id == other_workspace_id,
            Lead.phone == "0919998877",
        )
        rows_other = (await db_session.execute(stmt)).scalars().all()
        assert len(rows_other) == 0
