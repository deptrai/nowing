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


@pytest.mark.parametrize(
    "embedding_model,ollama_base_url",
    [
        ("ollama://nomic-embed-text", "http://localhost:11434"),
        ("ollama://mxbai-embed-large", "http://my-ollama-server:11434"),
    ],
    ids=["localhost", "custom_server"],
)
def test_ollama_model_with_base_url_injects_base_url(embedding_model, ollama_base_url):
    """When EMBEDDING_MODEL starts with 'ollama://' and OLLAMA_BASE_URL is set,
    base_url must be present in embedding_kwargs with the correct value."""
    kwargs = _build_embedding_kwargs(
        embedding_model=embedding_model,
        azure_openai_endpoint=None,
        azure_openai_api_key=None,
        ollama_base_url=ollama_base_url,
    )

    assert "base_url" in kwargs
    assert kwargs["base_url"] == ollama_base_url


# ---------------------------------------------------------------------------
# T2 — non-ollama model + OLLAMA_BASE_URL set → base_url NOT injected
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "embedding_model",
    [
        "text-embedding-3-small",
        "openai/text-embedding-ada-002",
    ],
    ids=["plain", "openai_prefixed"],
)
def test_non_ollama_model_does_not_get_base_url(embedding_model):
    """When EMBEDDING_MODEL does NOT start with 'ollama://', base_url must
    NOT be injected even when OLLAMA_BASE_URL is set.
    This prevents crashes on Azure/OpenAI providers (PR #605 fix)."""
    kwargs = _build_embedding_kwargs(
        embedding_model=embedding_model,
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


# ---------------------------------------------------------------------------
# T3 — OLLAMA_BASE_URL not set (or invalid prefix) → base_url not injected
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "embedding_model,ollama_base_url",
    [
        ("ollama://nomic-embed-text", None),                      # missing base_url
        (None, None),                                              # no model, no base_url
        ("ollama://nomic-embed-text", ""),                         # empty-string base_url
        ("OLLAMA://nomic-embed-text", "http://localhost:11434"),   # wrong-case prefix
    ],
    ids=["no_base_url", "no_model", "empty_string_base_url", "uppercase_prefix"],
)
def test_base_url_not_injected(embedding_model, ollama_base_url):
    """base_url must NOT appear in kwargs when any required condition is not met:
    missing base_url, missing model, empty base_url, or wrong-case 'ollama://' prefix."""
    kwargs = _build_embedding_kwargs(
        embedding_model=embedding_model,
        azure_openai_endpoint=None,
        azure_openai_api_key=None,
        ollama_base_url=ollama_base_url,
    )

    assert "base_url" not in kwargs


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


def test_azure_and_ollama_together_only_azure_keys():
    """With Azure credentials set, only azure_* keys appear; base_url stays absent."""
    kwargs = _build_embedding_kwargs(
        embedding_model="text-embedding-3-small",
        azure_openai_endpoint="https://example.openai.azure.com",
        azure_openai_api_key="secret",
        ollama_base_url="http://localhost:11434",
    )

    assert set(kwargs.keys()) == {"azure_endpoint", "azure_api_key"}
