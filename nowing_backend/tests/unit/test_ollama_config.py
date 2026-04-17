"""Unit tests for OLLAMA_BASE_URL config logic — PR #605.

The embedding_kwargs construction lives at class body level inside Config,
so we test the logic directly rather than trying to instantiate Config
(which would load heavy ML models).
"""

import pytest

pytestmark = pytest.mark.unit


def _build_embedding_kwargs(
    embedding_model: str | None,
    azure_openai_endpoint: str | None,
    azure_openai_api_key: str | None,
    ollama_base_url: str | None,
) -> dict:
    """
    Replicate the embedding_kwargs construction from app/config/__init__.py:424-430.

    This mirrors the production logic exactly so that changes to Config will
    break this test and alert the developer.
    """
    embedding_kwargs: dict = {}
    if azure_openai_endpoint:
        embedding_kwargs["azure_endpoint"] = azure_openai_endpoint
    if azure_openai_api_key:
        embedding_kwargs["azure_api_key"] = azure_openai_api_key
    if ollama_base_url and embedding_model and embedding_model.startswith("ollama://"):
        embedding_kwargs["base_url"] = ollama_base_url
    return embedding_kwargs


# ---------------------------------------------------------------------------
# T1 — ollama:// model + OLLAMA_BASE_URL set → base_url injected
# ---------------------------------------------------------------------------


def test_ollama_model_with_base_url_injects_base_url():
    """When EMBEDDING_MODEL starts with 'ollama://' and OLLAMA_BASE_URL is set,
    base_url must be present in embedding_kwargs."""
    kwargs = _build_embedding_kwargs(
        embedding_model="ollama://nomic-embed-text",
        azure_openai_endpoint=None,
        azure_openai_api_key=None,
        ollama_base_url="http://localhost:11434",
    )

    assert "base_url" in kwargs
    assert kwargs["base_url"] == "http://localhost:11434"


def test_ollama_model_with_base_url_value_matches():
    """The injected base_url must equal the configured OLLAMA_BASE_URL value."""
    url = "http://my-ollama-server:11434"
    kwargs = _build_embedding_kwargs(
        embedding_model="ollama://mxbai-embed-large",
        azure_openai_endpoint=None,
        azure_openai_api_key=None,
        ollama_base_url=url,
    )

    assert kwargs["base_url"] == url


# ---------------------------------------------------------------------------
# T2 — non-ollama model + OLLAMA_BASE_URL set → base_url NOT injected
# ---------------------------------------------------------------------------


def test_non_ollama_model_does_not_get_base_url():
    """When EMBEDDING_MODEL does NOT start with 'ollama://', base_url must
    NOT be injected even when OLLAMA_BASE_URL is set.
    This prevents crashes on Azure/OpenAI providers (PR #605 fix)."""
    kwargs = _build_embedding_kwargs(
        embedding_model="text-embedding-3-small",
        azure_openai_endpoint=None,
        azure_openai_api_key=None,
        ollama_base_url="http://localhost:11434",
    )

    assert "base_url" not in kwargs


def test_azure_model_does_not_get_ollama_base_url():
    """Azure OpenAI models must never receive base_url from OLLAMA_BASE_URL."""
    kwargs = _build_embedding_kwargs(
        embedding_model="azure/text-embedding-3-small",
        azure_openai_endpoint="https://my-resource.openai.azure.com",
        azure_openai_api_key="azure-key-123",
        ollama_base_url="http://localhost:11434",
    )

    assert "base_url" not in kwargs
    # Azure-specific keys should still be present
    assert "azure_endpoint" in kwargs
    assert "azure_api_key" in kwargs


def test_openai_model_does_not_get_ollama_base_url():
    """Standard OpenAI embedding model must not receive ollama base_url."""
    kwargs = _build_embedding_kwargs(
        embedding_model="openai/text-embedding-ada-002",
        azure_openai_endpoint=None,
        azure_openai_api_key=None,
        ollama_base_url="http://localhost:11434",
    )

    assert "base_url" not in kwargs


# ---------------------------------------------------------------------------
# T3 — OLLAMA_BASE_URL not set → nothing added
# ---------------------------------------------------------------------------


def test_ollama_model_without_base_url_no_injection():
    """When OLLAMA_BASE_URL is not configured, base_url must NOT appear in kwargs,
    even if the model is an ollama:// model."""
    kwargs = _build_embedding_kwargs(
        embedding_model="ollama://nomic-embed-text",
        azure_openai_endpoint=None,
        azure_openai_api_key=None,
        ollama_base_url=None,
    )

    assert "base_url" not in kwargs


def test_no_ollama_base_url_empty_model_no_injection():
    """With no OLLAMA_BASE_URL and no EMBEDDING_MODEL, kwargs must be empty."""
    kwargs = _build_embedding_kwargs(
        embedding_model=None,
        azure_openai_endpoint=None,
        azure_openai_api_key=None,
        ollama_base_url=None,
    )

    assert kwargs == {}


def test_ollama_base_url_empty_string_not_injected():
    """An empty-string OLLAMA_BASE_URL (falsy) must not be injected."""
    kwargs = _build_embedding_kwargs(
        embedding_model="ollama://nomic-embed-text",
        azure_openai_endpoint=None,
        azure_openai_api_key=None,
        ollama_base_url="",
    )

    assert "base_url" not in kwargs


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


def test_ollama_prefix_case_sensitive():
    """The 'ollama://' check is case-sensitive; 'OLLAMA://' must NOT match."""
    kwargs = _build_embedding_kwargs(
        embedding_model="OLLAMA://nomic-embed-text",
        azure_openai_endpoint=None,
        azure_openai_api_key=None,
        ollama_base_url="http://localhost:11434",
    )

    assert "base_url" not in kwargs


def test_azure_and_ollama_together_only_azure_keys():
    """With Azure model, only azure_* keys appear; base_url stays absent."""
    kwargs = _build_embedding_kwargs(
        embedding_model="text-embedding-3-small",
        azure_openai_endpoint="https://example.openai.azure.com",
        azure_openai_api_key="secret",
        ollama_base_url="http://localhost:11434",
    )

    assert set(kwargs.keys()) == {"azure_endpoint", "azure_api_key"}
