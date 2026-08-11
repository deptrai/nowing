"""Unit tests for ``app.services.chainlens.auth``."""

from __future__ import annotations

import base64
import json
import time
import types
import uuid
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException, Request
from starlette.datastructures import Headers

from app.services.chainlens.auth import (
    ChainLensAuthContext,
    ChainLensServiceAuth,
    get_chainlens_auth_header,
)

pytestmark = pytest.mark.unit


def _config(token: str = "service-token", api_key: str = "") -> types.SimpleNamespace:
    return types.SimpleNamespace(
        CHAINLENS_SERVICE_TOKEN=token,
        CHAINLENS_API_KEY=api_key,
    )


@pytest.mark.asyncio
async def test_get_outbound_headers_includes_bearer_and_workspace_headers():
    auth = ChainLensServiceAuth(config_obj=_config())
    headers = auth.get_outbound_headers(workspace_id=42, correlation_id="corr-1")

    assert headers["Authorization"] == "Bearer service-token"
    assert headers["X-Workspace-Id"] == "42"
    assert headers["X-Correlation-Id"] == "corr-1"


def test_get_outbound_headers_generates_correlation_id():
    auth = ChainLensServiceAuth(config_obj=_config())
    headers = auth.get_outbound_headers(workspace_id=1)

    assert "X-Correlation-Id" in headers
    assert uuid.UUID(headers["X-Correlation-Id"])


@pytest.mark.asyncio
async def test_validate_inbound_token_accepts_valid_token_and_workspace():
    auth = ChainLensServiceAuth(config_obj=_config())
    request = MagicMock(spec=Request)
    request.headers = Headers(
        headers={
            "authorization": "Bearer service-token",
            "x-workspace-id": "7",
            "x-correlation-id": "corr-2",
        }
    )

    ctx = auth.validate_inbound_token(request)
    assert ctx == ChainLensAuthContext(
        workspace_id=7,
        correlation_id="corr-2",
        token="service-token",
    )


@pytest.mark.asyncio
async def test_validate_inbound_token_rejects_missing_bearer():
    auth = ChainLensServiceAuth(config_obj=_config())
    request = MagicMock(spec=Request)
    request.headers = Headers(headers={"x-workspace-id": "7"})

    with pytest.raises(HTTPException) as exc_info:
        auth.validate_inbound_token(request)
    assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_validate_inbound_token_rejects_invalid_token():
    auth = ChainLensServiceAuth(config_obj=_config())
    request = MagicMock(spec=Request)
    request.headers = Headers(
        headers={
            "authorization": "Bearer wrong-token",
            "x-workspace-id": "7",
        }
    )

    with pytest.raises(HTTPException) as exc_info:
        auth.validate_inbound_token(request)
    assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_validate_inbound_token_rejects_missing_workspace():
    auth = ChainLensServiceAuth(config_obj=_config())
    request = MagicMock(spec=Request)
    request.headers = Headers(headers={"authorization": "Bearer service-token"})

    with pytest.raises(HTTPException) as exc_info:
        auth.validate_inbound_token(request)
    assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_validate_inbound_token_rejects_non_numeric_workspace():
    auth = ChainLensServiceAuth(config_obj=_config())
    request = MagicMock(spec=Request)
    request.headers = Headers(
        headers={
            "authorization": "Bearer service-token",
            "x-workspace-id": "not-a-number",
        }
    )

    with pytest.raises(HTTPException) as exc_info:
        auth.validate_inbound_token(request)
    assert exc_info.value.status_code == 401


def test_legacy_get_chainlens_auth_header_reuses_service_token():
    fake = _config(token="legacy-token")
    # The legacy helper reads the global config; override the module's copy.
    import app.services.chainlens.auth as auth_mod

    original = auth_mod.config
    auth_mod.config = fake
    try:
        headers = get_chainlens_auth_header()
        assert headers == {"Authorization": "Bearer legacy-token"}
    finally:
        auth_mod.config = original


def test_cost_dollars_to_micros_rounds_half_up():
    assert ChainLensServiceAuth.cost_dollars_to_micros(0.000123456) == 123
    assert ChainLensServiceAuth.cost_dollars_to_micros(0.0001235) == 124
    assert ChainLensServiceAuth.cost_dollars_to_micros(1.0) == 1_000_000


def test_token_rotation_cycles_tokens_on_401():
    auth = ChainLensServiceAuth(tokens=["first", "second"])
    assert auth.current_token == "first"
    rotated = auth.rotate()
    assert rotated == "second"
    assert auth.current_token == "second"


def test_token_rotation_is_noop_with_single_token():
    auth = ChainLensServiceAuth(tokens=["only"])
    assert auth.rotate() is None
    assert auth.current_token == "only"


def test_preemptive_rotation_when_jwt_expires_within_30_days():
    exp = int(time.time()) + 60  # expires in 1 minute
    payload = {"exp": exp}
    jwt_payload = (
        base64.urlsafe_b64encode(b"header").rstrip(b"=")
        + b"."
        + base64.urlsafe_b64encode(json.dumps(payload).encode()).rstrip(b"=")
        + b"."
        + base64.urlsafe_b64encode(b"sig").rstrip(b"=")
    )
    first = jwt_payload.decode()
    auth = ChainLensServiceAuth(tokens=[first, "second"])
    rotated = auth.rotate_if_expiring()
    assert rotated == "second"
    assert auth.current_token == "second"


@pytest.mark.asyncio
async def test_validate_inbound_token_rejects_zero_workspace():
    auth = ChainLensServiceAuth(config_obj=_config())
    request = MagicMock(spec=Request)
    request.headers = Headers(
        headers={
            "Authorization": "Bearer service-token",
            "X-Workspace-Id": "0",
        }
    )

    with pytest.raises(HTTPException) as exc_info:
        auth.validate_inbound_token(request)
    assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_validate_inbound_token_rejects_negative_workspace():
    auth = ChainLensServiceAuth(config_obj=_config())
    request = MagicMock(spec=Request)
    request.headers = Headers(
        headers={
            "Authorization": "Bearer service-token",
            "X-Workspace-Id": "-7",
        }
    )

    with pytest.raises(HTTPException) as exc_info:
        auth.validate_inbound_token(request)
    assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_validate_inbound_token_accepts_missing_correlation_id():
    auth = ChainLensServiceAuth(config_obj=_config())
    request = MagicMock(spec=Request)
    request.headers = Headers(
        headers={
            "Authorization": "Bearer service-token",
            "X-Workspace-Id": "7",
        }
    )

    ctx = auth.validate_inbound_token(request)
    assert ctx.correlation_id is None
    assert ctx.workspace_id == 7


@pytest.mark.asyncio
async def test_validate_inbound_token_accepts_lowercase_bearer():
    auth = ChainLensServiceAuth(config_obj=_config())
    request = MagicMock(spec=Request)
    request.headers = Headers(
        headers={
            "authorization": "bearer service-token",
            "x-workspace-id": "7",
        }
    )

    ctx = auth.validate_inbound_token(request)
    assert ctx.token == "service-token"


def test_load_tokens_strips_whitespace_and_deduplicates():
    auth = ChainLensServiceAuth(config_obj=_config(token=" token1 , token1 , token2 "))
    assert auth._tokens == ["token1", "token2"]


def test_load_tokens_falls_back_to_api_key():
    auth = ChainLensServiceAuth(config_obj=_config(token="", api_key="legacy-key"))
    assert auth._tokens == ["legacy-key"]


def test_cost_dollars_to_micros_rejects_negative():
    with pytest.raises(ValueError, match="non-negative"):
        ChainLensServiceAuth.cost_dollars_to_micros(-0.01)


def test_cost_dollars_to_micros_rejects_non_finite():
    with pytest.raises(ValueError, match="finite"):
        ChainLensServiceAuth.cost_dollars_to_micros(float("nan"))


def test_cost_dollars_to_micros_rejects_unreasonable_value():
    with pytest.raises(ValueError, match="reasonable"):
        ChainLensServiceAuth.cost_dollars_to_micros(1_000_001.0)
