"""Root conftest — shared fixtures available to all test modules."""

from __future__ import annotations

import os

_DEFAULT_TEST_DB = "postgresql+asyncpg://postgres:postgres@localhost:5432/nowing_test"
TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL", _DEFAULT_TEST_DB)

# Force the app to use the test database regardless of any pre-existing
# DATABASE_URL in the environment (e.g. from .env or shell profile).
os.environ["DATABASE_URL"] = TEST_DATABASE_URL
os.environ.setdefault("EMBEDDING_MODEL", "all-minilm-l6-v2")
if not os.environ.get("EMBEDDING_MODEL"):
    os.environ["EMBEDDING_MODEL"] = "all-minilm-l6-v2"

# Integration tests authenticate over HTTP via email/password, so the
# password-auth routers must be mounted (they are skipped under AUTH_TYPE=GOOGLE).
# setdefault (not load_dotenv, which runs later with override=False) lets a
# developer's .env=GOOGLE be overridden here while still honouring an explicitly
# exported shell AUTH_TYPE.
os.environ.setdefault("AUTH_TYPE", "LOCAL")
os.environ.setdefault("REGISTRATION_ENABLED", "TRUE")

# The ETL pipeline requires a parser provider. DOCLING is installed and used
# across both local tests and E2E, so default to it when the operator has not
# explicitly chosen UNSTRUCTURED / LLAMACLOUD.
os.environ.setdefault("ETL_SERVICE", "DOCLING")
os.environ.setdefault("EMBEDDING_MODEL", "all-minilm-l6-v2")

# Mutation gate: avoid heavy model/library imports in each mutant process.
# `app.config` is imported by `app.db` below and eagerly initializes embeddings,
# chunkers, and rerankers, which adds several seconds of import overhead per
# subprocess. Under cosmic-ray we inject lightweight stubs for these third-party
# modules before `app.config` is loaded.
if os.environ.get("COSMIC_RAY") == "1":
    import sys
    import types

    os.environ.setdefault("EMBEDDING_MODEL", "dummy-embedding-model")

    class _CosmicRayEmbedding:
        dimension = 384
        max_seq_length = 512

        def get_tokenizer(self):
            return str.split

        def embed(self, _text):
            return [0.1] * self.dimension

        def embed_batch(self, texts):
            return [[0.1] * self.dimension for _ in texts]

    class _CosmicRayAutoEmbeddings:
        @classmethod
        def get_embeddings(cls, *args, **kwargs):
            return _CosmicRayEmbedding()

    class _CosmicRayChunker:
        def __init__(self, *args, **kwargs):
            pass

        def __call__(self, text, *args, **kwargs):
            return [text]

    _fake_chonkie = types.ModuleType("chonkie")
    _fake_chonkie.AutoEmbeddings = _CosmicRayAutoEmbeddings
    _fake_chonkie.CodeChunker = _CosmicRayChunker
    _fake_chonkie.RecursiveChunker = _CosmicRayChunker
    sys.modules["chonkie"] = _fake_chonkie

    class _CosmicRayReranker:
        def __init__(self, *args, **kwargs):
            pass

    _fake_rerankers = types.ModuleType("rerankers")
    _fake_rerankers.Reranker = _CosmicRayReranker
    sys.modules["rerankers"] = _fake_rerankers

    # litellm takes ~3s to import; memory code only needs its exception classes.
    _fake_litellm = types.ModuleType("litellm")
    _fake_litellm.__path__ = []
    _fake_litellm_exceptions = types.ModuleType("litellm.exceptions")

    class _LiteLLMError(Exception): ...

    class APIConnectionError(_LiteLLMError): ...

    class APIResponseValidationError(_LiteLLMError): ...

    class AuthenticationError(_LiteLLMError): ...

    class BadGatewayError(_LiteLLMError): ...

    class BadRequestError(_LiteLLMError): ...

    class ContextWindowExceededError(_LiteLLMError): ...

    class InternalServerError(_LiteLLMError): ...

    class NotFoundError(_LiteLLMError): ...

    class PermissionDeniedError(_LiteLLMError): ...

    class RateLimitError(_LiteLLMError): ...

    class ServiceUnavailableError(_LiteLLMError): ...

    class Timeout(_LiteLLMError): ...  # noqa: N818

    class UnprocessableEntityError(_LiteLLMError): ...

    _fake_litellm_exceptions.APIConnectionError = APIConnectionError
    _fake_litellm_exceptions.APIResponseValidationError = APIResponseValidationError
    _fake_litellm_exceptions.AuthenticationError = AuthenticationError
    _fake_litellm_exceptions.BadGatewayError = BadGatewayError
    _fake_litellm_exceptions.BadRequestError = BadRequestError
    _fake_litellm_exceptions.ContextWindowExceededError = ContextWindowExceededError
    _fake_litellm_exceptions.InternalServerError = InternalServerError
    _fake_litellm_exceptions.NotFoundError = NotFoundError
    _fake_litellm_exceptions.PermissionDeniedError = PermissionDeniedError
    _fake_litellm_exceptions.RateLimitError = RateLimitError
    _fake_litellm_exceptions.ServiceUnavailableError = ServiceUnavailableError
    _fake_litellm_exceptions.Timeout = Timeout
    _fake_litellm_exceptions.UnprocessableEntityError = UnprocessableEntityError

    async def _no_op_async(*args, **kwargs):
        return None

    def _no_op_info(*args, **kwargs):
        return {}

    def _token_counter(*args, **kwargs):
        return 0

    def _completion_cost(*args, **kwargs):
        return 1e-6

    def _cost_per_token(*args, **kwargs):
        return 1e-7, 1e-7

    _fake_litellm.atranscription = _no_op_async
    _fake_litellm.aspeech = _no_op_async
    _fake_litellm.acompletion = _no_op_async
    _fake_litellm.aimage_generation = _no_op_async
    _fake_litellm.image_generation = _no_op_async
    _fake_litellm.get_model_info = _no_op_info
    _fake_litellm.token_counter = _token_counter
    _fake_litellm.completion_cost = _completion_cost
    _fake_litellm.cost_per_token = _cost_per_token
    _fake_litellm.exceptions = _fake_litellm_exceptions

    class _FakeRouter:
        def __init__(self, *args, **kwargs):
            pass

    _fake_litellm.Router = _FakeRouter

    class _ImageResponse:
        pass

    _fake_litellm_utils = types.ModuleType("litellm.utils")
    _fake_litellm_utils.ImageResponse = _ImageResponse
    _fake_litellm.utils = _fake_litellm_utils

    class CustomLogger:
        pass

    _fake_litellm_integrations = types.ModuleType("litellm.integrations")
    _fake_litellm_custom_logger = types.ModuleType("litellm.integrations.custom_logger")
    _fake_litellm_custom_logger.CustomLogger = CustomLogger
    _fake_litellm_integrations.custom_logger = _fake_litellm_custom_logger

    # langchain_litellm expects litellm.types.utils.Delta.
    _fake_litellm_types = types.ModuleType("litellm.types")
    _fake_litellm_types_utils = types.ModuleType("litellm.types.utils")

    class _Delta: ...

    _fake_litellm_types_utils.Delta = _Delta
    _fake_litellm_types.utils = _fake_litellm_types_utils

    sys.modules["litellm"] = _fake_litellm
    sys.modules["litellm.exceptions"] = _fake_litellm_exceptions
    sys.modules["litellm.utils"] = _fake_litellm_utils
    sys.modules["litellm.types"] = _fake_litellm_types
    sys.modules["litellm.types.utils"] = _fake_litellm_types_utils
    sys.modules["litellm.integrations"] = _fake_litellm_integrations
    sys.modules["litellm.integrations.custom_logger"] = _fake_litellm_custom_logger

import pytest  # noqa: E402

from app.config import config as _app_config  # noqa: E402
from app.db import DocumentType  # noqa: E402

# Many unit and integration tests rely on PII encryption, DNC hashing, and JWT
# signing. The `SECRET_KEY` env var may be unset in CI/hermetic environments, so
# ensure a stable test key is present before any service/route module is loaded.
if not getattr(_app_config, "SECRET_KEY", None):
    _app_config.SECRET_KEY = "test-secret-key-integration-very-secure-32chars"
from app.indexing_pipeline.connector_document import ConnectorDocument  # noqa: E402
from app.rate_limiter import limiter  # noqa: E402

# ---------------------------------------------------------------------------
# Unit test fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def sample_user_id() -> str:
    return "00000000-0000-0000-0000-000000000001"


@pytest.fixture
def sample_workspace_id() -> int:
    return 1


@pytest.fixture
def sample_connector_id() -> int:
    return 42


@pytest.fixture
def make_connector_document():
    """
    Generic factory for unit tests. Overridden in tests/integration/conftest.py
    with real DB-backed IDs for integration tests.
    """

    def _make(**overrides):
        defaults = {
            "title": "Test Document",
            "source_markdown": "## Heading\n\nSome content.",
            "unique_id": "test-id-001",
            "document_type": DocumentType.CLICKUP_CONNECTOR,
            "workspace_id": 1,
            "connector_id": 1,
            "created_by_id": "00000000-0000-0000-0000-000000000001",
        }
        defaults.update(overrides)
        return ConnectorDocument(**defaults)

    return _make


@pytest.fixture(autouse=True)
def _manage_rate_limiter_for_test_isolation(request, monkeypatch):
    """Re-enable the global rate limiter for unit tests.

    Many integration conftests set ``limiter.enabled = False`` at module-import
    time to avoid rate-limit rejections. Without isolation, that disabled state
    leaks to unit tests (e.g. ``test_lead_batch_ingest``) that assert rate
    limits are enforced. Unit tests are marked ``pytest.mark.unit``; integration
    tests own their own setup and should not be forced back on.
    """
    if not request.node.get_closest_marker("integration"):
        monkeypatch.setattr(limiter, "enabled", True)

    yield
    # monkeypatch cleans up at teardown
