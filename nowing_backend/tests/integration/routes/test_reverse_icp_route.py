"""Red-phase integration tests for Reverse-ICP Route (Story 21.10)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.auth.context import AuthContext
from app.users import get_auth_context

pytestmark = pytest.mark.integration


MOCK_REVERSE_ICP_RESPONSE = {
    "company_name": "Vinhomes",
    "domain": "vinhomes.vn",
    "value_proposition": "Chủ đầu tư bất động sản số 1 Việt Nam.",
    "industry": "Bất động sản cao cấp",
    "target_buyer_personas": [
        {
            "title": "Nhà đầu tư cá nhân",
            "industry": "Bất động sản",
            "company_size": "Cá nhân",
            "pain_points": ["Thiếu nguồn hàng sạch"],
            "buying_triggers": ["Mở bán dự án mới"],
        }
    ],
    "suggested_search_queries": ["Mua biệt thự Vinhomes"],
    "negative_keywords": ["nhà trọ"],
    "filter_presets": {
        "platforms": ["batdongsan"],
        "intent": "BÁN",
        "target_industries": ["Bất động sản"],
        "locations": ["Hà Nội"],
        "company_size_range": None,
    },
    "chat_starter_prompts": ["Tìm 10 bài đăng bán biệt thự Vinhomes"],
    "raw_metadata": {"crawl_latency_ms": 250},
}


@pytest.fixture
def test_app() -> FastAPI:
    """Create test FastAPI application with mounted leads router."""
    from app.routes.leads_routes import router as leads_router

    app = FastAPI()
    app.include_router(leads_router, prefix="/api/v1")
    return app


@pytest.fixture
def mock_auth() -> AuthContext:
    """Create mock authenticated user context."""
    user = MagicMock()
    user.id = uuid4()
    user.email = "test@nowing.net"
    user.is_active = True
    user.credit_micros_balance = 5000000

    return AuthContext.session(user=user)


class TestReverseIcpRoute:
    """Test POST /api/v1/workspaces/{workspace_id}/leads/reverse-icp endpoint."""

    def test_reverse_icp_requires_workspace_permission(
        self, test_app: FastAPI, mock_auth: AuthContext
    ) -> None:
        """Should return 403 Forbidden if user lacks WORKSPACE_READ permission."""
        from fastapi import HTTPException

        import app.routes.leads_routes as leads_routes

        with patch.object(
            leads_routes,
            "check_permission",
            AsyncMock(side_effect=HTTPException(status_code=403, detail="Permission denied")),
        ):
            test_app.dependency_overrides[get_auth_context] = lambda: mock_auth
            client = TestClient(test_app)

            response = client.post(
                "/api/v1/workspaces/1/leads/reverse-icp",
                json={"url": "https://vinhomes.vn"},
            )
            assert response.status_code == 403

    def test_reverse_icp_rejects_ssrf_and_invalid_urls(
        self, test_app: FastAPI, mock_auth: AuthContext
    ) -> None:
        """Should return 400 Bad Request on SSRF target or malformed URL."""
        import app.routes.leads_routes as leads_routes

        with patch.object(leads_routes, "check_permission", AsyncMock(return_value=True)):
            test_app.dependency_overrides[get_auth_context] = lambda: mock_auth
            client = TestClient(test_app)

            # SSRF internal loopback
            response = client.post(
                "/api/v1/workspaces/1/leads/reverse-icp",
                json={"url": "http://127.0.0.1:8000/admin"},
            )
            assert response.status_code == 400

    def test_reverse_icp_success_returns_structured_response(
        self, test_app: FastAPI, mock_auth: AuthContext
    ) -> None:
        """Should execute analysis, track usage, and return 200 OK with ReverseIcpResponse."""
        import app.routes.leads_routes as leads_routes

        mock_service = MagicMock()
        mock_service.analyze_url = AsyncMock(return_value=MOCK_REVERSE_ICP_RESPONSE)

        with patch.object(leads_routes, "check_permission", AsyncMock(return_value=True)), patch(
            "app.lead_intelligence.reverse_icp.ReverseIcpService", return_value=mock_service
        ):
            test_app.dependency_overrides[get_auth_context] = lambda: mock_auth
            client = TestClient(test_app)

            response = client.post(
                "/api/v1/workspaces/1/leads/reverse-icp",
                json={"url": "https://vinhomes.vn", "custom_instructions": "Tập trung vào phân khu The Crown"},
            )
            assert response.status_code == 200
            data = response.json()
            assert data["company_name"] == "Vinhomes"
            assert data["industry"] == "Bất động sản cao cấp"
            assert len(data["target_buyer_personas"]) == 1
            assert data["filter_presets"]["intent"] == "BÁN"
