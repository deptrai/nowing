from unittest.mock import AsyncMock, patch

import pytest

from app.db import Connection, Model
from app.services import model_connection_service as mcs


@pytest.mark.asyncio
async def test_test_model_success_asserts_num_retries_and_timeout():
    conn = Connection(
        provider="openai",
        api_key="sk-test-key",
        base_url="https://api.openai.com/v1",
        extra={},
    )
    model = Model(
        model_id="gpt-4o",
        supports_chat=False,
    )

    with patch("litellm.acompletion", new_callable=AsyncMock) as mock_acompletion:
        mock_acompletion.return_value = AsyncMock()

        result = await mcs.test_model(conn, model)

        assert isinstance(result, mcs.VerifyResult)
        assert result.ok is True
        assert result.status == "OK"
        assert model.supports_chat is True

        mock_acompletion.assert_awaited_once()
        called_kwargs = mock_acompletion.await_args.kwargs
        assert called_kwargs["model"] == "openai/gpt-4o"
        assert called_kwargs["messages"] == [{"role": "user", "content": "Hello"}]
        assert called_kwargs["timeout"] == mcs.TEST_TIMEOUT_SECONDS
        assert called_kwargs["num_retries"] == 0
        assert called_kwargs["api_key"] == "sk-test-key"


@pytest.mark.asyncio
async def test_test_model_timeout_mapping():
    conn = Connection(
        provider="openai",
        api_key="sk-test-key",
        base_url="https://api.openai.com/v1",
        extra={},
    )
    model = Model(
        model_id="gpt-4o",
        supports_chat=False,
    )

    with patch(
        "litellm.acompletion",
        new_callable=AsyncMock,
        side_effect=Exception("Request timed out after 15s"),
    ) as mock_acompletion:
        result = await mcs.test_model(conn, model)

        assert isinstance(result, mcs.VerifyResult)
        assert result.ok is False
        assert result.status == "TIMEOUT"
        assert model.supports_chat is False
        mock_acompletion.assert_awaited_once()


@pytest.mark.asyncio
async def test_test_model_auth_failure_mapping():
    conn = Connection(
        provider="openai",
        api_key="sk-invalid-key",
        base_url="https://api.openai.com/v1",
        extra={},
    )
    model = Model(
        model_id="gpt-4o",
        supports_chat=False,
    )

    class AuthError(Exception):
        status_code = 401

    with patch(
        "litellm.acompletion",
        new_callable=AsyncMock,
        side_effect=AuthError("401 Unauthorized"),
    ) as mock_acompletion:
        result = await mcs.test_model(conn, model)

        assert isinstance(result, mcs.VerifyResult)
        assert result.ok is False
        assert result.status == "AUTH_FAILED"
        assert model.supports_chat is False
        mock_acompletion.assert_awaited_once()


@pytest.mark.asyncio
async def test_test_model_generic_error_mapping():
    conn = Connection(
        provider="openai",
        api_key="sk-test-key",
        base_url="https://api.openai.com/v1",
        extra={},
    )
    model = Model(
        model_id="gpt-4o",
        supports_chat=False,
    )

    with patch(
        "litellm.acompletion",
        new_callable=AsyncMock,
        side_effect=Exception("Internal server error"),
    ) as mock_acompletion:
        result = await mcs.test_model(conn, model)

        assert isinstance(result, mcs.VerifyResult)
        assert result.ok is False
        assert result.status == "UNREACHABLE"
        assert "Could not test model 'gpt-4o' on OpenAI" in result.message
        assert model.supports_chat is False
        mock_acompletion.assert_awaited_once()
