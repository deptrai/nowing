"""Root conftest — shared fixtures available to all test modules."""

from __future__ import annotations

import os
from collections.abc import AsyncGenerator
from pathlib import Path

import asyncpg
import httpx
import pytest
from dotenv import load_dotenv

from tests.utils.helpers import (
    BACKEND_URL,
    auth_headers,
    delete_document,
    get_auth_token,
    get_search_space_id,
)

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL",
    os.environ.get("DATABASE_URL", ""),
).replace("postgresql+asyncpg://", "postgresql://")


async def _force_delete_documents_db(
    search_space_id: int,
) -> int:
    """
    Bypass the API and delete documents directly from the database.

    This handles stuck documents in pending/processing state that the API
    refuses to delete (409 Conflict). Chunks are cascade-deleted by the
    foreign key constraint.

    Returns the number of deleted rows.
    """
    conn = await asyncpg.connect(DATABASE_URL)
    try:
        result = await conn.execute(
            "DELETE FROM documents WHERE search_space_id = $1",
            search_space_id,
        )
        return int(result.split()[-1])
    finally:
        await conn.close()


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
    search_space_id: int,
):
    """
    Delete all documents in the test search space before the session starts.

    Uses direct database access to bypass the API's 409 protection on
    pending/processing documents. This ensures stuck documents from
    previous crashed runs are always cleaned up.
    """
    deleted = await _force_delete_documents_db(search_space_id)
    if deleted:
        print(f"\n[purge] Deleted {deleted} stale document(s) from search space {search_space_id}")

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
    search_space_id: int,
    cleanup_doc_ids: list[int],
):
    """
    Runs after every test. Tries the API first for clean deletes, then
    falls back to direct DB access for any stuck documents.
    """
    yield

    remaining_ids: list[int] = []
    for doc_id in cleanup_doc_ids:
        try:
            resp = await delete_document(client, headers, doc_id)
            if resp.status_code == 409:
                remaining_ids.append(doc_id)
        except Exception:
            remaining_ids.append(doc_id)

    if remaining_ids:
        conn = await asyncpg.connect(DATABASE_URL)
        try:
            await conn.execute(
                "DELETE FROM documents WHERE id = ANY($1::int[])",
                remaining_ids,
            )
        finally:
            await conn.close()
