"""Root conftest — shared fixtures available to all test modules."""

from __future__ import annotations

import contextlib
from collections.abc import AsyncGenerator

import httpx
import pytest

from tests.utils.helpers import (
    BACKEND_URL,
    TEST_SEARCH_SPACE_ID,
    auth_headers,
    delete_document,
    get_auth_token,
)


@pytest.fixture(scope="session")
def backend_url() -> str:
    return BACKEND_URL


@pytest.fixture(scope="session")
def search_space_id() -> int:
    return TEST_SEARCH_SPACE_ID


@pytest.fixture(scope="session")
async def auth_token(backend_url: str) -> str:
    """Authenticate once per session and return the JWT token."""
    async with httpx.AsyncClient(
        base_url=backend_url, timeout=30.0
    ) as client:
        return await get_auth_token(client)


@pytest.fixture(scope="session")
def headers(auth_token: str) -> dict[str, str]:
    """Authorization headers reused across all tests in the session."""
    return auth_headers(auth_token)


@pytest.fixture
async def client(backend_url: str) -> AsyncGenerator[httpx.AsyncClient]:
    """Per-test async HTTP client pointing at the running backend."""
    async with httpx.AsyncClient(
        base_url=backend_url, timeout=180.0
    ) as c:
        yield c


@pytest.fixture
def cleanup_doc_ids() -> list[int]:
    """Accumulator for document IDs that should be deleted after the test."""
    return []


@pytest.fixture(autouse=True)
async def _cleanup_documents(
    client: httpx.AsyncClient,
    headers: dict[str, str],
    cleanup_doc_ids: list[int],
):
    """
    Runs after every test.  Deletes any document IDs that were appended to
    the ``cleanup_doc_ids`` list during the test body.
    """
    yield
    for doc_id in cleanup_doc_ids:
        with contextlib.suppress(Exception):
            await delete_document(client, headers, doc_id)
