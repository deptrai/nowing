import pytest


@pytest.fixture
def sample_user_id() -> str:
    return "00000000-0000-0000-0000-000000000001"


@pytest.fixture
def sample_search_space_id() -> int:
    return 1


@pytest.fixture
def sample_connector_id() -> int:
    return 42
