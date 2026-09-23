"""Unit tests: Zalo Co-pilot overlay context (Story 37.4 / AD-118).

Covers the pure/deterministic parts of
``GET /api/v1/workspaces/{id}/leads/copilot-context``:

1. ``_build_zalo_pitch_copy`` — the two drawer tabs (`Ngắn gọn` / `Kèm link
   Pitch`) with and without contact name / portal URL.
2. ``_decrypt_contact_field`` — plaintext passthrough + corrupt ciphertext
   fallback (must never break the drawer).
3. ``_verify_clipper_auth`` — PAT scope gating reused by the read endpoint.
4. ``ZaloCopilotContextResponse`` — response contract for the extension.
"""

from __future__ import annotations

import base64
import os
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import FastAPI, HTTPException
from httpx import ASGITransport, AsyncClient

import app.lead_intelligence.dnc.service as dnc_service_module
from app.auth.context import AuthContext
from app.db import get_async_session
from app.redis_client import get_redis_client
from app.routes import router as crud_router
from app.routes.lead_clipper_routes import (
    CLIPPER_REQUIRED_SCOPE,
    ZaloCopilotContextResponse,
    _build_zalo_pitch_copy,
    _decrypt_contact_field,
    _verify_clipper_auth,
)
from app.users import get_auth_context

pytestmark = pytest.mark.unit


def _make_lead(**overrides) -> SimpleNamespace:
    base = {
        "id": uuid4(),
        "workspace_id": 1,
        "company_name": "Công ty TNHH ABC",
        "industry": "Bất động sản",
        "location": "Hồ Chí Minh",
        "domain": "abc.vn",
        "status": "new",
        "intent_score": 0.8,
    }
    base.update(overrides)
    return SimpleNamespace(**base)


class TestZaloPitchCopy:
    """AC-2: deterministic copy for `Ngắn gọn` / `Kèm link Pitch` tabs."""

    def test_short_pitch_contains_company_and_greeting(self):
        lead = _make_lead()
        short, _ = _build_zalo_pitch_copy(lead, "Minh", None)
        assert "Chào anh/chị Minh" in short
        assert "Công ty TNHH ABC" in short
        assert "Bất động sản" in short

    def test_greeting_falls_back_without_contact_name(self):
        lead = _make_lead()
        short, _ = _build_zalo_pitch_copy(lead, None, None)
        assert short.startswith("Chào anh/chị,")

    def test_with_link_tab_appends_portal_url(self):
        lead = _make_lead()
        portal = "https://pitch.nowing.ai/acme/abc-123"
        short, with_link = _build_zalo_pitch_copy(lead, None, portal)
        assert with_link != short
        assert with_link.startswith(short)
        assert portal in with_link

    def test_with_link_falls_back_to_short_without_portal(self):
        lead = _make_lead()
        short, with_link = _build_zalo_pitch_copy(lead, None, None)
        assert with_link == short

    def test_missing_company_uses_safe_fallback(self):
        lead = _make_lead(company_name=None, industry=None)
        short, _ = _build_zalo_pitch_copy(lead, None, None)
        assert "doanh nghiệp mình" in short
        assert "lĩnh vực" not in short

    def test_pii_fields_are_sanitized(self):
        lead = _make_lead(company_name="<script>alert(1)</script>" * 30)
        short, _ = _build_zalo_pitch_copy(lead, "<img src=x>", None)
        assert "<script>" not in short
        assert "<img" not in short


class TestDecryptContactField:
    def test_plaintext_passthrough(self):
        assert _decrypt_contact_field("Nguyen Van A") == "Nguyen Van A"

    def test_empty_values(self):
        assert _decrypt_contact_field(None) is None
        assert _decrypt_contact_field("") is None

    def test_corrupt_ciphertext_returns_none(self):
        # Base64-decodable + long → is_encrypted() is True, but Fernet
        # decryption fails → must return None, not raise.
        bogus = base64.urlsafe_b64encode(b"\x80" + os.urandom(60)).decode()
        from app.services.pii.verified_contact_encryption import (
            VerifiedContactEncryption,
        )

        enc = VerifiedContactEncryption()
        assert enc.is_encrypted(bogus) is True
        assert _decrypt_contact_field(bogus) is None


class TestCopilotAuth:
    """AC-1/AC-4: read endpoint reuses clipper PAT gating."""

    @staticmethod
    def _pat_auth(scopes=None, workspace_id=1):
        pat = SimpleNamespace(
            id=1,
            workspace_id=workspace_id,
            scopes=scopes if scopes is not None else [CLIPPER_REQUIRED_SCOPE],
            is_valid=True,
        )
        return AuthContext.pat_auth(SimpleNamespace(id=uuid4()), pat)

    async def test_pat_with_clipper_scope_passes(self):
        await _verify_clipper_auth(self._pat_auth(), 1, session=None)

    async def test_pat_missing_scope_raises_403(self):
        with pytest.raises(HTTPException) as exc:
            await _verify_clipper_auth(
                self._pat_auth(scopes=["agent_chat:thread:create"]),
                1,
                session=None,
            )
        assert exc.value.status_code == 403

    async def test_pat_wrong_workspace_raises_403(self):
        with pytest.raises(HTTPException) as exc:
            await _verify_clipper_auth(
                self._pat_auth(workspace_id=10), 20, session=None
            )
        assert exc.value.status_code == 403


class TestCopilotResponseContract:
    def test_unmatched_response_shape(self):
        res = ZaloCopilotContextResponse(matched=False)
        assert res.matched is False
        assert res.dnc_blocked is False
        assert res.lead is None
        assert res.signals == []
        assert res.pitch_short is None

    def test_dnc_blocked_surfaced_without_lead_match(self):
        """AC-4: DNC banner must render even when no lead matched."""
        res = ZaloCopilotContextResponse(
            matched=False,
            phone_e164="+84901234567",
            dnc_blocked=True,
            dnc_reason="Phone number is registered on Workspace DNC blacklist",
        )
        assert res.dnc_blocked is True
        assert res.matched is False


# ---------------------------------------------------------------------------
# Route-level test: catches the /leads/{lead_id} shadowing regression.
# ---------------------------------------------------------------------------


class _FakeScalars:
    def __init__(self, rows: list):
        self._rows = rows

    def all(self):
        return self._rows

    def first(self):
        return self._rows[0] if self._rows else None


class _FakeResult:
    def __init__(self, rows: list | None = None):
        self._rows = rows or []

    def scalars(self):
        return _FakeScalars(self._rows)


class _FakeSession:
    """Minimal AsyncSession stand-in: every query returns empty results."""

    async def execute(self, _stmt):
        return _FakeResult()

    async def get(self, _model, _pk):
        return None


@pytest.fixture
def copilot_app(monkeypatch):
    """Bare FastAPI app mounting the real aggregate router — preserves route
    registration order, so GET /leads/{lead_id} shadowing would surface as
    the 422 this test asserts against."""
    monkeypatch.setattr(dnc_service_module, "get_redis", lambda: None)

    pat = SimpleNamespace(
        id=1,
        workspace_id=1,
        scopes=[CLIPPER_REQUIRED_SCOPE],
        is_valid=True,
    )
    auth = AuthContext.pat_auth(SimpleNamespace(id=uuid4()), pat)

    test_app = FastAPI()
    test_app.include_router(crud_router, prefix="/api/v1")
    test_app.dependency_overrides[get_auth_context] = lambda: auth
    test_app.dependency_overrides[get_async_session] = lambda: _FakeSession()
    test_app.dependency_overrides[get_redis_client] = lambda: None
    return test_app


class TestCopilotRouteLevel:
    async def test_copilot_context_not_shadowed_by_lead_id_route(
        self, copilot_app
    ):
        """GET /leads/copilot-context must reach the clipper router, not
        /leads/{lead_id} (which would 422 on UUID parsing)."""
        async with AsyncClient(
            transport=ASGITransport(app=copilot_app), base_url="http://test"
        ) as client:
            resp = await client.get(
                "/api/v1/workspaces/1/leads/copilot-context",
                params={"phone": "0912345678"},
            )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["matched"] is False
        assert body["phone_e164"] == "+84912345678"
        assert body["dnc_blocked"] is False
