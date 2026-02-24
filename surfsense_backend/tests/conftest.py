import pytest

from app.db import DocumentType
from app.indexing_pipeline.connector_document import ConnectorDocument


@pytest.fixture
def sample_user_id() -> str:
    return "00000000-0000-0000-0000-000000000001"


@pytest.fixture
def sample_search_space_id() -> int:
    return 1


@pytest.fixture
def sample_connector_id() -> int:
    return 42


@pytest.fixture
def make_connector_document():
    def _make(**overrides):
        defaults = {
            "title": "Test Document",
            "source_markdown": "## Heading\n\nSome content.",
            "unique_id": "test-id-001",
            "document_type": DocumentType.CLICKUP_CONNECTOR,
            "search_space_id": 1,
        }
        defaults.update(overrides)
        return ConnectorDocument(**defaults)
    return _make
