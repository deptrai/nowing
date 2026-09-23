"""Route-level contract tests for the pitch beacon endpoint (Story 37.6/AD-120).

The beacon must never leak lead existence or reject payloads: malformed,
oversized, crawler, and unknown-lead beacons all return 204.  The endpoint is
called via ``__wrapped__`` to bypass the slowapi decorator (rate limiting is
covered by deployment config, not unit tests).
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock
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
