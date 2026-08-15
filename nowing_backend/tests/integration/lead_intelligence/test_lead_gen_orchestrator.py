"""Integration tests for LeadGenOrchestrator DB persistence and VerifiedContact pipeline (Story 21.15)."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import User, Workspace

pytestmark = [pytest.mark.integration]


class TestLeadGenOrchestratorIntegration:
    """Integration tests for LeadGenOrchestrator with database and verified contacts."""

    @pytest.mark.asyncio
    async def test_orchestrator_persists_leads_to_postgresql(
        self,
        db_session: AsyncSession,
        db_workspace: Workspace,
        db_user: User,
    ) -> None:
        """Should execute orchestrator and persist deduplicated leads and contacts directly into DB."""
        from app.db import Lead, VerifiedContact, WorkspaceTable
        from app.lead_intelligence.adapters.base import NormalizedLead
        from app.lead_intelligence.services.lead_gen_orchestrator import (
            LeadGenOrchestrator,
        )

        orchestrator = LeadGenOrchestrator()
        table_uuid = uuid4()
        ws_table = WorkspaceTable(
            id=table_uuid,
            workspace_id=db_workspace.id,
            name="Default Leads Table",
        )
        db_session.add(ws_table)
        await db_session.flush()
        table_id = str(table_uuid)

        mock_leads = [
            NormalizedLead(
                source_name="batdongsan",
                source_id="bds_integ_01",
                title="Bán nhà mặt phố Hoàn Kiếm",
                company_name="Vinhomes Central",
                canonical_domain="vinhomes.vn",
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
                company_name="Đất Xanh Miền Bắc",
                canonical_domain="datxanh.com.vn",
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
            "execute_multi_source_lead_gen",
            AsyncMock(
                return_value=AsyncMock(
                    status="completed",
                    total_discovered=2,
                    total_deduplicated=2,
                    leads=mock_leads,
                    degraded_sources=[],
                    table_id=table_id,
                )
            ),
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

            # Query database to verify Lead rows were created
            stmt = select(Lead).where(
                Lead.workspace_id == db_workspace.id,
                Lead.table_id == UUID(table_id),
            )
            rows = (await db_session.execute(stmt)).scalars().all()
            assert len(rows) == 2

            # Query VerifiedContact rows
            contact_stmt = select(VerifiedContact).where(
                VerifiedContact.workspace_id == db_workspace.id,
            )
            contacts = (await db_session.execute(contact_stmt)).scalars().all()
            phones = [c.phone for c in contacts if c.phone]
            assert "0911223344" in phones
            assert "0988776655" in phones

    @pytest.mark.asyncio
    async def test_atomic_upsert_on_duplicate_conflict(
        self,
        db_session: AsyncSession,
        db_workspace: Workspace,
        db_user: User,
    ) -> None:
        """Repeated ingestion of the same entity should update existing row without unique constraint crash."""
        from app.db import Lead, WorkspaceTable
        from app.lead_intelligence.adapters.base import NormalizedLead
        from app.lead_intelligence.services.lead_gen_orchestrator import (
            LeadGenOrchestrator,
        )

        orchestrator = LeadGenOrchestrator()
        table_uuid = uuid4()
        ws_table = WorkspaceTable(
            id=table_uuid,
            workspace_id=db_workspace.id,
            name="Upsert Leads Table",
        )
        db_session.add(ws_table)
        await db_session.flush()
        table_id = str(table_uuid)

        initial_lead = NormalizedLead(
            source_name="batdongsan",
            source_id="bds_repeat_1",
            title="Bán nhà Hoàng Mai",
            company_name="Công Ty BĐS Hoàng Mai",
            canonical_domain="bds-hoangmai.vn",
            primary_phone="0977112233",
            confidence_score=70.0,
            sources=["batdongsan"],
        )
        updated_lead = NormalizedLead(
            source_name="chotot",
            source_id="ct_repeat_2",
            title="Bán nhà Hoàng Mai chính chủ giá tốt",
            company_name="Công Ty BĐS Hoàng Mai",
            canonical_domain="bds-hoangmai.vn",
            primary_phone="0977112233",
            contact_name="Lê Văn C",
            confidence_score=85.0,
            sources=["batdongsan", "chotot"],
        )

        with patch.object(
            orchestrator,
            "execute_multi_source_lead_gen",
            AsyncMock(
                return_value=AsyncMock(
                    status="completed",
                    total_discovered=1,
                    total_deduplicated=1,
                    leads=[initial_lead],
                    degraded_sources=[],
                    table_id=table_id,
                )
            ),
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
            "execute_multi_source_lead_gen",
            AsyncMock(
                return_value=AsyncMock(
                    status="completed",
                    total_discovered=1,
                    total_deduplicated=1,
                    leads=[updated_lead],
                    degraded_sources=[],
                    table_id=table_id,
                )
            ),
        ):
            # Second run with same company/domain
            await orchestrator.execute_and_persist(
                session=db_session,
                workspace_id=db_workspace.id,
                query="Tìm nhà Hoàng Mai lần 2",
                table_id=table_id,
                user_id=db_user.id,
            )

        stmt = select(Lead).where(
            Lead.workspace_id == db_workspace.id,
            Lead.domain == "bds-hoangmai.vn",
        )
        rows = (await db_session.execute(stmt)).scalars().all()
        # Must be exactly 1 row (deduplicated / upserted)
        assert len(rows) == 1
        assert rows[0].fit_score >= 85.0

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
            canonical_domain="ws1-company.com",
            primary_phone="0919998877",
            confidence_score=80.0,
            sources=["topcv"],
        )

        with patch.object(
            orchestrator,
            "execute_multi_source_lead_gen",
            AsyncMock(
                return_value=AsyncMock(
                    status="completed",
                    total_discovered=1,
                    total_deduplicated=1,
                    leads=[lead_ws1],
                    degraded_sources=[],
                    table_id=table_id,
                )
            ),
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
            Lead.domain == "ws1-company.com",
        )
        rows_other = (await db_session.execute(stmt)).scalars().all()
        assert len(rows_other) == 0
