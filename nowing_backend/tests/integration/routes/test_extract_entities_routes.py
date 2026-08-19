"""Integration tests for test-only entity extraction REST endpoint."""

import pytest
from httpx import ASGITransport, AsyncClient

from app.app import app

pytestmark = pytest.mark.integration


class TestExtractEntitiesRoutes:
    """Test POST /api/v1/test/extract-entities endpoint security and response schema."""

    @pytest.mark.asyncio
    async def test_extract_entities_endpoint_success_with_valid_secret(
        self, monkeypatch
    ):
        """Endpoint extracts entities when the dedicated test secret header is provided."""
        monkeypatch.setenv("TEST_EXTRACTION_SECRET", "my-secret-token")

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
            headers={"X-Internal-Test": "my-secret-token"},
        ) as client:
            payload = {
                "source_text": "Liên hệ CÔNG TY TNHH ABC qua SĐT 0908123456 hoặc MST 0100109106",
                "source_url": "https://example.com/contact",
            }
            response = await client.post("/api/v1/test/extract-entities", json=payload)
            assert response.status_code == 200
            data = response.json()
            assert "0908123456" in data["phones"]
            assert "0100109106" in data["tax_ids"]
            assert data["tax_ids_valid"] == [True]

    @pytest.mark.asyncio
    async def test_extract_entities_endpoint_rejects_missing_header(self, monkeypatch):
        """Endpoint returns 403 when the X-Internal-Test header is missing."""
        monkeypatch.setenv("TEST_EXTRACTION_SECRET", "my-secret-token")

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            payload = {"source_text": "Sample text 0908123456"}
            response = await client.post("/api/v1/test/extract-entities", json=payload)
            assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_extract_entities_endpoint_rejects_default_secret(self, monkeypatch):
        """The old hardcoded fallback secret no longer grants access."""
        monkeypatch.setenv("TEST_EXTRACTION_SECRET", "my-secret-token")

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
            headers={"X-Internal-Test": "test-internal-secret"},
        ) as client:
            payload = {"source_text": "Sample text 0908123456"}
            response = await client.post("/api/v1/test/extract-entities", json=payload)
            assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_extract_entities_endpoint_rejects_environment_bypass(
        self, monkeypatch
    ):
        """ENVIRONMENT=test or ENVIRONMENT=local no longer bypasses the secret."""
        monkeypatch.setenv("TEST_EXTRACTION_SECRET", "my-secret-token")
        monkeypatch.setenv("ENVIRONMENT", "test")

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            payload = {"source_text": "Sample text 0908123456"}
            response = await client.post("/api/v1/test/extract-entities", json=payload)
            assert response.status_code == 403

        monkeypatch.setenv("ENVIRONMENT", "local")
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.post("/api/v1/test/extract-entities", json=payload)
            assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_extract_entities_endpoint_rejects_when_secret_unconfigured(
        self, monkeypatch
    ):
        """If TEST_EXTRACTION_SECRET is unset, the endpoint fails closed with 503."""
        monkeypatch.delenv("TEST_EXTRACTION_SECRET", raising=False)

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
            headers={"X-Internal-Test": "any-secret"},
        ) as client:
            payload = {"source_text": "Sample text 0908123456"}
            response = await client.post("/api/v1/test/extract-entities", json=payload)
            assert response.status_code == 503

    @pytest.mark.asyncio
    async def test_extract_entities_endpoint_not_in_openapi_schema(self):
        """The test-only route is hidden from the generated OpenAPI schema."""
        openapi = app.openapi()
        for path in (
            "/api/v1/test/extract-entities",
            "/test/extract-entities",
            "/api/test/extract-entities",
        ):
            assert path not in openapi["paths"], f"{path} should not appear in OpenAPI"

    @pytest.mark.asyncio
    async def test_extract_entities_endpoint_rejects_oversized_payload(
        self, monkeypatch
    ):
        """A source_text larger than 100k characters is rejected with 413."""
        monkeypatch.setenv("TEST_EXTRACTION_SECRET", "my-secret-token")

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
            headers={"X-Internal-Test": "my-secret-token"},
        ) as client:
            payload = {"source_text": "x" * 100_001}
            response = await client.post("/api/v1/test/extract-entities", json=payload)
            assert response.status_code == 413

    @pytest.mark.asyncio
    async def test_extract_entities_endpoint_rejects_malformed_payload(
        self, monkeypatch
    ):
        """Malformed or missing source_text is rejected with 422."""
        monkeypatch.setenv("TEST_EXTRACTION_SECRET", "my-secret-token")

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
            headers={"X-Internal-Test": "my-secret-token"},
        ) as client:
            # Missing source_text
            response = await client.post("/api/v1/test/extract-entities", json={})
            assert response.status_code == 422

            # Wrong type for source_text
            response = await client.post(
                "/api/v1/test/extract-entities", json={"source_text": 123}
            )
            assert response.status_code == 422

            # Invalid JSON body
            response = await client.post(
                "/api/v1/test/extract-entities",
                content="not-json",
                headers={"Content-Type": "application/json"},
            )
            assert response.status_code == 422
