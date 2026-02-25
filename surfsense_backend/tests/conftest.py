"""Root conftest — shared fixtures available to all test modules."""

from __future__ import annotations

import contextlib
from collections.abc import AsyncGenerator

import httpx
import pytest

from tests.utils.helpers import (
    BACKEND_URL,
    auth_headers,
    delete_document,
    get_auth_token,
    get_search_space_id,
    poll_document_status,
)


@pytest.fixture(scope="session")
def backend_url() -> str:
    return BACKEND_URL


@pytest.fixture(scope="session")
async def auth_token(backend_url: str) -> str:
    """Authenticate once per session, registering the user if needed."""
    async with httpx.AsyncClient(
        base_url=backend_url, timeout=30.0
    ) as client:
        return await get_auth_token(client)


@pytest.fixture(scope="session")
async def search_space_id(backend_url: str, auth_token: str) -> int:
    """Discover the first search space belonging to the test user."""
    async with httpx.AsyncClient(
        base_url=backend_url, timeout=30.0
    ) as client:
        return await get_search_space_id(client, auth_token)


@pytest.fixture(scope="session", autouse=True)
async def _purge_test_search_space(
    backend_url: str,
    auth_token: str,
    search_space_id: int,
):
    """
    Delete all documents in the test search space before the session starts.

    Ensures no stale data from a previous run interferes with the current
    session.  Paginates through all documents and waits for any in-flight
    documents to reach a terminal state before deleting.
    """
    hdrs = auth_headers(auth_token)
    async with httpx.AsyncClient(base_url=backend_url, timeout=60.0) as client:
        all_docs: list[dict] = []
        page = 0
        page_size = 200

        while True:
            resp = await client.get(
                "/api/v1/documents",
                headers=hdrs,
                params={
                    "search_space_id": search_space_id,
                    "page": page,
                    "page_size": page_size,
                },
            )
            if resp.status_code != 200:
                break

            body = resp.json()
            all_docs.extend(body.get("items", []))

            if not body.get("has_more", False):
                break
            page += 1

        if not all_docs:
            yield
            return

        in_flight = [
            doc["id"]
            for doc in all_docs
            if doc.get("status", {}).get("state") in ("pending", "processing")
        ]
        if in_flight:
            with contextlib.suppress(Exception):
                await poll_document_status(
                    client,
                    hdrs,
                    in_flight,
                    search_space_id=search_space_id,
                    timeout=120.0,
                )

        for doc in all_docs:
            with contextlib.suppress(Exception):
                await client.delete(
                    f"/api/v1/documents/{doc['id']}",
                    headers=hdrs,
                )

    yield


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
