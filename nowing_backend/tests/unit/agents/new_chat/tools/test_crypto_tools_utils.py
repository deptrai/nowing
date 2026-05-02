import asyncio
from unittest.mock import AsyncMock, patch
import pytest
from app.agents.new_chat.tools.utils import crypto_tool_decorator

pytestmark = pytest.mark.unit

@pytest.mark.asyncio
async def test_decorator_calls_wrapped_function_on_success():
    """Decorator calls the tool and records success."""
    mock_func = AsyncMock(return_value={"data": "ok"})
    decorated = crypto_tool_decorator("test_source")(mock_func)
    
    with patch("app.agents.new_chat.tools.utils.circuit_breaker") as mock_cb:
        mock_cb.is_open = AsyncMock(return_value=False)
        mock_cb.record_success = AsyncMock()
        mock_cb.record_failure = AsyncMock()
        
        result = await decorated()
        
        assert result == {"data": "ok"}
        mock_func.assert_called_once()
        mock_cb.record_success.assert_called_once_with("test_source")

@pytest.mark.asyncio
async def test_decorator_returns_error_when_circuit_open():
    """Decorator skips the tool call and returns an error if circuit is open."""
    mock_func = AsyncMock()
    decorated = crypto_tool_decorator("test_source")(mock_func)
    
    with patch("app.agents.new_chat.tools.utils.circuit_breaker") as mock_cb:
        mock_cb.is_open = AsyncMock(return_value=True)
        
        result = await decorated()
        
        assert result["status"] == "error"
        assert "Circuit open" in result["error"]
        mock_func.assert_not_called()

@pytest.mark.asyncio
async def test_decorator_handles_exceptions_gracefully():
    """Decorator catches exceptions, records failure, and returns standard error dict."""
    mock_func = AsyncMock(side_effect=RuntimeError("Boom!"))
    decorated = crypto_tool_decorator("test_source")(mock_func)
    
    with patch("app.agents.new_chat.tools.utils.circuit_breaker") as mock_cb:
        mock_cb.is_open = AsyncMock(return_value=False)
        mock_cb.record_failure = AsyncMock()
        
        result = await decorated()
        
        assert result["status"] == "error"
        assert "Unexpected error" in result["error"]
        assert "RuntimeError" in result["error"]
        mock_cb.record_failure.assert_called_once_with("test_source")

@pytest.mark.asyncio
async def test_decorator_handles_timeout_error():
    """Decorator specifically handles asyncio.TimeoutError."""
    mock_func = AsyncMock(side_effect=asyncio.TimeoutError())
    decorated = crypto_tool_decorator("test_source")(mock_func)
    
    with patch("app.agents.new_chat.tools.utils.circuit_breaker") as mock_cb:
        mock_cb.is_open = AsyncMock(return_value=False)
        mock_cb.record_failure = AsyncMock()
        
        result = await decorated()
        
        assert result["status"] == "error"
        assert "timed out" in result["error"]
        mock_cb.record_failure.assert_called_once_with("test_source")

@pytest.mark.asyncio
async def test_decorator_handles_logical_errors():
    """Decorator records failure if the returned dict contains an 'error' key."""
    mock_func = AsyncMock(return_value={"error": "API Key Invalid"})
    decorated = crypto_tool_decorator("test_source")(mock_func)
    
    with patch("app.agents.new_chat.tools.utils.circuit_breaker") as mock_cb:
        mock_cb.is_open = AsyncMock(return_value=False)
        mock_cb.record_failure = AsyncMock()
        
        result = await decorated()
        
        assert result == {"error": "API Key Invalid"}
        mock_cb.record_failure.assert_called_once_with("test_source")
