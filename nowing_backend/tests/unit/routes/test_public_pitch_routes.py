"""Route-level contract tests for the pitch beacon endpoint (Story 37.6/AD-120).

The beacon must never leak lead existence or reject payloads: malformed,
oversized, crawler, and unknown-lead beacons all return 204.  The endpoint is
called via ``__wrapped__`` to bypass the slowapi decorator (rate limiting is
covered by deployment config, not unit tests).
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.routes.public_pitch_routes import pitch_beacon
from app.schemas.pitch import PitchBeaconPayload

CHROME_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36"
)


def _request(
    body: bytes = b"{}",
    ua: str = CHROME_UA,
    content_length: str | None = None,
):
    headers: dict[str, str] = {"user-agent": ua}
    if content_length is not None:
        headers["content-length"] = content_length
    request = MagicMock()
    request.headers = headers
    request.body = AsyncMock(return_value=body)
    return request


def _session(lead=None):
    """AsyncSession stand-in; ``get`` returns ``lead`` (None = unknown lead)."""
    session = AsyncMock()
    session.add = MagicMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = None
    session.execute = AsyncMock(return_value=result)
    session.get = AsyncMock(return_value=lead)
    return session


def _redis():
    redis = MagicMock()
    redis.get = AsyncMock(return_value=None)
    redis.set = AsyncMock(return_value=None)
    redis.delete = AsyncMock()
    return redis


async def _call(request, session=None, redis=None):
    return await pitch_beacon.__wrapped__(
        request=request,
        workspace_ref="42",
        lead_id=uuid4(),
        session=session or _session(),
        redis_client=redis or _redis(),
    )


@pytest.mark.unit
class TestBeaconNoLeakContract:
    """AD-120: well-formed requests always answer 204 — never 404/422."""

    @pytest.mark.asyncio
    async def test_crawler_ua_returns_204_without_touching_db_or_body(self):
        request = _request(ua="facebookexternalhit/1.1")
        session = _session()
        response = await _call(request, session=session)
        assert response.status_code == 204
        request.body.assert_not_called()
        session.execute.assert_not_called()
        session.get.assert_not_called()

    @pytest.mark.asyncio
    async def test_oversized_content_length_returns_204_without_reading(self):
        request = _request(content_length=str(1024 * 1024))
        response = await _call(request)
        assert response.status_code == 204
        request.body.assert_not_called()

    @pytest.mark.asyncio
    async def test_malformed_body_returns_204(self):
        response = await _call(_request(body=b"this is not json"))
        assert response.status_code == 204

    @pytest.mark.asyncio
    async def test_non_object_json_returns_204(self):
        response = await _call(_request(body=b'"just a string"'))
        assert response.status_code == 204

    @pytest.mark.asyncio
    async def test_unknown_lead_returns_204(self):
        session = _session(lead=None)
        body = json.dumps({"dwell_seconds": 10, "event": "open"}).encode()
        response = await _call(_request(body=body), session=session)
        assert response.status_code == 204

    @pytest.mark.asyncio
    async def test_unknown_workspace_slug_returns_204(self):
        session = _session()  # scalar_one_or_none → None for the slug lookup
        body = json.dumps({"dwell_seconds": 10, "event": "open"}).encode()
        request = _request(body=body)
        response = await pitch_beacon.__wrapped__(
            request=request,
            workspace_ref="no-such-slug",
            lead_id=uuid4(),
            session=session,
            redis_client=_redis(),
        )
        assert response.status_code == 204
        session.get.assert_not_called()


@pytest.mark.unit
class TestBeaconPayloadShape:
    """The payload model accepts the exact JSON the frontend send() emits."""

    def test_frontend_shape(self):
        payload = PitchBeaconPayload.model_validate(
            {
                "dwell_seconds": 12.3,
                "sections_viewed": ["hero", "roi"],
                "device_type": "mobile",
                "session_id": "s-1716000000-abc123",
                "event": "open",
            }
        )
        assert payload.dwell_seconds == 12.3
        assert payload.sections_viewed == ["hero", "roi"]
        assert payload.event == "open"

    def test_event_is_constrained(self):
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            PitchBeaconPayload.model_validate({"event": "bogus"})

    def test_minimal_body_valid(self):
        payload = PitchBeaconPayload.model_validate({})
        assert payload.dwell_seconds == 0.0
        assert payload.sections_viewed == []


@pytest.mark.unit
class TestPitchMetaRoute:
    """Story 37.5: /meta returns generated portal content + opt-out path."""

    async def test_meta_returns_generated_content(self):
        from types import SimpleNamespace

        from app.db import Lead
        from app.routes.public_pitch_routes import get_pitch_meta

        lead = SimpleNamespace(
            id=uuid4(),
            workspace_id=42,
            company_name="Acme Corp",
            industry="Logistics",
            location="TP.HCM",
            domain="acme.vn",
            consent_status="opted_in",
        )
        workspace = SimpleNamespace(id=42, name="Nowing WS")
        session = _session()
        session.get = AsyncMock(
            side_effect=lambda model, _ident: (
                lead if model is Lead else workspace
            )
        )
        content = {
            "headline": "Headline for Acme",
            "exec_summary": "Summary",
            "exec_cards": [
                {"tone": "red", "title": "Thực trạng", "body": "b1"},
                {"tone": "yellow", "title": "Khoảng trống", "body": "b2"},
                {"tone": "green", "title": "Giải pháp", "body": "b3"},
            ],
            "logo_url": None,
            "roi": None,
        }
        with patch(
            "app.services.pitch_portal.get_portal_content",
            new=AsyncMock(return_value=content),
        ):
            response = await get_pitch_meta.__wrapped__(
                request=MagicMock(),
                workspace_ref="42",
                lead_id=lead.id,
                session=session,
                redis_client=_redis(),
            )

        assert response.headline == "Headline for Acme"
        assert len(response.exec_cards) == 3
        assert response.exec_cards[0].title == "Thực trạng"
        assert response.opt_out_path == f"/pitch/42/{lead.id}/opt-out"
        assert response.company_name == "Acme Corp"

    async def test_meta_404s_for_withdrawn_lead(self):
        """A withdrawn lead's portal must stop serving even with warm cache."""
        from types import SimpleNamespace

        from fastapi import HTTPException

        from app.routes.public_pitch_routes import get_pitch_meta

        lead = SimpleNamespace(
            id=uuid4(), workspace_id=42, consent_status="withdrawn"
        )
        session = _session()
        session.get = AsyncMock(side_effect=lambda model, _ident: lead)
        with patch(
            "app.services.pitch_portal.get_portal_content", new=AsyncMock()
        ) as mock_content, pytest.raises(HTTPException) as exc:
            await get_pitch_meta.__wrapped__(
                request=MagicMock(),
                workspace_ref="42",
                lead_id=lead.id,
                session=session,
                redis_client=_redis(),
            )
        assert exc.value.status_code == 404
        mock_content.assert_not_awaited()


@pytest.mark.unit
class TestPitchOptOutRoute:
    """Story 37.5 / AC-4: self-serve opt-out never leaks lead existence."""

    async def _call_opt_out(self, session=None, ua=CHROME_UA, headers=None):
        from app.routes.public_pitch_routes import pitch_opt_out

        request = _request()
        request.headers = {"user-agent": ua, **(headers or {})}
        request.client = MagicMock()
        request.client.host = "1.2.3.4"
        return await pitch_opt_out.__wrapped__(
            request=request,
            workspace_ref="42",
            lead_id=uuid4(),
            session=session or _session(),
            redis_client=_redis(),
        )

    @pytest.mark.asyncio
    async def test_unknown_lead_still_200_ok(self):
        response = await self._call_opt_out(session=_session(lead=None))
        assert response == {"status": "ok"}

    @pytest.mark.asyncio
    async def test_crawler_ua_short_circuits(self):
        session = _session()
        response = await self._call_opt_out(
            session=session, ua="facebookexternalhit/1.1"
        )
        assert response == {"status": "ok"}
        session.get.assert_not_called()

    @pytest.mark.asyncio
    async def test_valid_lead_processes_and_commits(self):
        from types import SimpleNamespace

        lead = SimpleNamespace(id=uuid4(), workspace_id=42)
        session = _session(lead=lead)
        redis = _redis()
        request = _request()
        request.headers = {
            "user-agent": CHROME_UA,
            "x-forwarded-for": "9.9.9.9, 10.0.0.1",
        }
        request.client = MagicMock()
        request.client.host = "1.2.3.4"

        from app.routes.public_pitch_routes import pitch_opt_out

        with patch(
            "app.services.pitch_portal.process_pitch_opt_out",
            new=AsyncMock(return_value=2),
        ) as mock_process:
            response = await pitch_opt_out.__wrapped__(
                request=request,
                workspace_ref="42",
                lead_id=uuid4(),
                session=session,
                redis_client=redis,
            )
        assert response == {"status": "ok"}
        mock_process.assert_awaited_once()
        args, kwargs = mock_process.await_args
        assert args[0] is session
        assert args[1] is redis
        # First XFF hop wins — the prospect IP, not the ingress edge IP.
        assert kwargs["ip_address"] == "9.9.9.9"
        session.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_processing_error_still_generic_ok(self):
        from types import SimpleNamespace

        lead = SimpleNamespace(id=uuid4(), workspace_id=42)
        session = _session(lead=lead)
        with patch(
            "app.services.pitch_portal.process_pitch_opt_out",
            new=AsyncMock(side_effect=RuntimeError("boom")),
        ):
            response = await self._call_opt_out(session=session)
        assert response == {"status": "ok"}
        session.rollback.assert_awaited_once()


@pytest.mark.unit
class TestPitchFavicon:
    """Favicon proxy — validates domain, never open-proxies (review 37.5)."""

    async def test_invalid_domain_404(self):
        from app.routes.public_pitch_routes import pitch_favicon

        response = await pitch_favicon.__wrapped__(
            request=MagicMock(), domain="not a domain!!", redis_client=None
        )
        assert response.status_code == 404

    async def test_upstream_error_404(self):
        from app.routes.public_pitch_routes import pitch_favicon

        upstream = MagicMock(status_code=500, content=b"")
        client = AsyncMock()
        client.get = AsyncMock(return_value=upstream)
        client.__aenter__ = AsyncMock(return_value=client)
        client.__aexit__ = AsyncMock(return_value=None)
        with patch("httpx.AsyncClient", return_value=client):
            response = await pitch_favicon.__wrapped__(
                request=MagicMock(), domain="acme.vn", redis_client=None
            )
        assert response.status_code == 404

    async def test_success_proxies_image_and_caches(self):
        from app.routes.public_pitch_routes import pitch_favicon

        upstream = MagicMock(
            status_code=200,
            content=b"\x89PNG fake",
            headers={"content-type": "image/png"},
        )
        client = AsyncMock()
        client.get = AsyncMock(return_value=upstream)
        client.__aenter__ = AsyncMock(return_value=client)
        client.__aexit__ = AsyncMock(return_value=None)
        redis = _redis()
        redis.get = AsyncMock(return_value=None)
        with patch("httpx.AsyncClient", return_value=client):
            response = await pitch_favicon.__wrapped__(
                request=MagicMock(), domain="acme.vn", redis_client=redis
            )
        assert response.status_code == 200
        assert response.body == b"\x89PNG fake"
        # Upstream hit is Google only — the viewer's domain never becomes a URL.
        call = client.get.await_args
        assert call.args[0] == "https://www.google.com/s2/favicons"
        assert call.kwargs["params"]["domain"] == "acme.vn"
        redis.set.assert_awaited_once()

    async def test_non_image_content_type_rejected(self):
        from app.routes.public_pitch_routes import pitch_favicon

        upstream = MagicMock(
            status_code=200,
            content=b"<html>nope</html>",
            headers={"content-type": "text/html"},
        )
        client = AsyncMock()
        client.get = AsyncMock(return_value=upstream)
        client.__aenter__ = AsyncMock(return_value=client)
        client.__aexit__ = AsyncMock(return_value=None)
        with patch("httpx.AsyncClient", return_value=client):
            response = await pitch_favicon.__wrapped__(
                request=MagicMock(), domain="acme.vn", redis_client=None
            )
        assert response.status_code == 404
