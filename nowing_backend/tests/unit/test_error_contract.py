"""Unit tests for the structured error response contract.

Validates that:
- Global exception handlers produce the backward-compatible error envelope.
- 5xx responses never leak raw internal exception text.
- X-Request-ID is propagated correctly.
- NowingError, HTTPException, validation, and unhandled exceptions all
  use the same response shape.
"""

from __future__ import annotations

import json

import pytest
from fastapi import HTTPException
from pydantic import BaseModel, Field
from starlette.testclient import TestClient

from app.capabilities.core.validation import HttpUrlStr
from app.exceptions import (
    GENERIC_5XX_MESSAGE,
    ISSUES_URL,
    ConfigurationError,
    ConnectorError,
    ContextOverflowError,
    DatabaseError,
    DocumentError,
    ExternalAPIError,
    ExternalServiceError,
    ForbiddenError,
    IndexingError,
    LLMError,
    ModelUnavailableError,
    NotFoundError,
    NowingError,
    OAuthError,
    ParseError,
    PermissionDeniedError,
    RateLimitError,
    StorageError,
    UploadError,
    ValidationError,
)

pytestmark = pytest.mark.unit


# NOTE: models must live at module level — with ``from __future__ import
# annotations`` FastAPI resolves body annotations via module globals, so a
# class defined only inside ``_make_test_app`` would be treated as a query
# param (harness bug found during Story 2.9 red-phase).


class _Item(BaseModel):
    name: str = Field(min_length=1)
    count: int


class _ScrapeBody(BaseModel):
    urls: list[HttpUrlStr]


# ---------------------------------------------------------------------------
# Helpers - lightweight FastAPI app that re-uses the real global handlers
# ---------------------------------------------------------------------------


def _make_test_app():
    """Build a minimal FastAPI app with the same handlers as the real one."""
    from fastapi import FastAPI
    from fastapi.exceptions import RequestValidationError

    from app.app import (
        RequestIDMiddleware,
        _http_exception_handler,
        _nowing_error_handler,
        _unhandled_exception_handler,
        _validation_error_handler,
    )

    app = FastAPI()
    app.add_middleware(RequestIDMiddleware)
    app.add_exception_handler(NowingError, _nowing_error_handler)
    app.add_exception_handler(RequestValidationError, _validation_error_handler)
    app.add_exception_handler(HTTPException, _http_exception_handler)
    app.add_exception_handler(Exception, _unhandled_exception_handler)

    @app.get("/ok")
    async def ok():
        return {"status": "ok"}

    @app.get("/http-400")
    async def raise_http_400():
        raise HTTPException(status_code=400, detail="Bad input")

    @app.get("/http-500")
    async def raise_http_500():
        raise HTTPException(status_code=500, detail="secret db password leaked")

    @app.get("/http-503")
    async def raise_http_503():
        raise HTTPException(
            status_code=503,
            detail="Page purchases are temporarily unavailable.",
        )

    @app.get("/http-502")
    async def raise_http_502():
        raise HTTPException(
            status_code=502,
            detail="Unable to create Stripe checkout session.",
        )

    @app.get("/nowing-connector")
    async def raise_connector():
        raise ConnectorError("GitHub API returned 401")

    @app.get("/nowing-notfound")
    async def raise_notfound():
        raise NotFoundError("Document #42 was not found")

    @app.get("/nowing-forbidden")
    async def raise_forbidden():
        raise ForbiddenError()

    @app.get("/nowing-config")
    async def raise_config():
        raise ConfigurationError()

    @app.get("/nowing-db")
    async def raise_db():
        raise DatabaseError()

    @app.get("/nowing-external")
    async def raise_external():
        raise ExternalServiceError()

    @app.get("/nowing-validation")
    async def raise_validation():
        raise ValidationError("Email is invalid")

    @app.get("/nowing-permission-denied")
    async def raise_permission_denied():
        raise PermissionDeniedError()

    @app.get("/nowing-oauth")
    async def raise_oauth():
        raise OAuthError("Google token expired")

    @app.get("/nowing-indexing")
    async def raise_indexing():
        raise IndexingError("Connector indexing failed")

    @app.get("/nowing-rate-limit")
    async def raise_rate_limit():
        raise RateLimitError()

    @app.get("/nowing-upload")
    async def raise_upload():
        raise UploadError("File too large")

    @app.get("/nowing-parse")
    async def raise_parse():
        raise ParseError("PDF parsing failed")

    @app.get("/nowing-storage")
    async def raise_storage():
        raise StorageError("S3 upload failed")

    @app.get("/nowing-llm")
    async def raise_llm():
        raise LLMError("OpenAI request failed")

    @app.get("/nowing-context-overflow")
    async def raise_context_overflow():
        raise ContextOverflowError()

    @app.get("/nowing-model-unavailable")
    async def raise_model_unavailable():
        raise ModelUnavailableError()

    @app.get("/nowing-external-api")
    async def raise_external_api():
        raise ExternalAPIError("Third-party API failed")

    @app.get("/unhandled")
    async def raise_unhandled():
        raise RuntimeError("should never reach the client")

    @app.post("/validated")
    async def validated(item: _Item):
        return item.model_dump()

    @app.post("/scrape")
    async def scrape(body: _ScrapeBody):
        return body.model_dump()

    return app


@pytest.fixture(scope="module")
def client():
    app = _make_test_app()
    return TestClient(app, raise_server_exceptions=False)


# ---------------------------------------------------------------------------
# Envelope shape validation
# ---------------------------------------------------------------------------


def _assert_envelope(resp, expected_status: int):
    """Every error response MUST contain the standard envelope."""
    assert resp.status_code == expected_status
    body = resp.json()
    assert "error" in body, f"Missing 'error' key: {body}"
    assert "detail" in body, f"Missing legacy 'detail' key: {body}"

    err = body["error"]
    assert isinstance(err["code"], str) and len(err["code"]) > 0
    assert isinstance(err["message"], str) and len(err["message"]) > 0
    assert err["status"] == expected_status
    assert isinstance(err["request_id"], str) and len(err["request_id"]) > 0
    assert "timestamp" in err
    assert err["report_url"] == ISSUES_URL

    # Legacy compat: detail mirrors message
    assert body["detail"] == err["message"]

    return body


# ---------------------------------------------------------------------------
# X-Request-ID propagation
# ---------------------------------------------------------------------------


class TestRequestID:
    def test_generated_when_missing(self, client):
        resp = client.get("/ok")
        assert "X-Request-ID" in resp.headers
        assert resp.headers["X-Request-ID"].startswith("req_")

    def test_echoed_when_provided(self, client):
        resp = client.get("/ok", headers={"X-Request-ID": "my-trace-123"})
        assert resp.headers["X-Request-ID"] == "my-trace-123"

    def test_present_in_error_response_body(self, client):
        resp = client.get("/http-400", headers={"X-Request-ID": "trace-abc"})
        body = _assert_envelope(resp, 400)
        assert body["error"]["request_id"] == "trace-abc"


# ---------------------------------------------------------------------------
# HTTPException handling
# ---------------------------------------------------------------------------


class TestHTTPExceptionHandler:
    def test_400_preserves_detail(self, client):
        body = _assert_envelope(client.get("/http-400"), 400)
        assert body["error"]["message"] == "Bad input"
        assert body["error"]["code"] == "BAD_REQUEST"

    def test_500_sanitizes_detail(self, client):
        body = _assert_envelope(client.get("/http-500"), 500)
        assert "secret" not in body["error"]["message"]
        assert "password" not in body["error"]["message"]
        assert body["error"]["message"] == GENERIC_5XX_MESSAGE
        assert body["error"]["code"] == "INTERNAL_ERROR"

    def test_503_preserves_detail(self, client):
        # Intentional 503s (e.g. feature flag off) must surface the developer
        # message so the frontend can render actionable copy.
        body = _assert_envelope(client.get("/http-503"), 503)
        assert body["error"]["message"] == "Page purchases are temporarily unavailable."
        assert body["error"]["message"] != GENERIC_5XX_MESSAGE

    def test_502_preserves_detail(self, client):
        body = _assert_envelope(client.get("/http-502"), 502)
        assert body["error"]["message"] == "Unable to create Stripe checkout session."
        assert body["error"]["message"] != GENERIC_5XX_MESSAGE


# ---------------------------------------------------------------------------
# NowingError hierarchy
# ---------------------------------------------------------------------------


class TestNowingErrorHandler:
    def test_connector_error(self, client):
        body = _assert_envelope(client.get("/nowing-connector"), 502)
        assert body["error"]["code"] == "CONNECTOR_ERROR"
        assert "GitHub" in body["error"]["message"]

    def test_not_found_error(self, client):
        body = _assert_envelope(client.get("/nowing-notfound"), 404)
        assert body["error"]["code"] == "NOT_FOUND"

    def test_forbidden_error(self, client):
        body = _assert_envelope(client.get("/nowing-forbidden"), 403)
        assert body["error"]["code"] == "FORBIDDEN"

    def test_configuration_error(self, client):
        body = _assert_envelope(client.get("/nowing-config"), 500)
        assert body["error"]["code"] == "CONFIGURATION_ERROR"

    def test_database_error(self, client):
        body = _assert_envelope(client.get("/nowing-db"), 500)
        assert body["error"]["code"] == "DATABASE_ERROR"

    def test_external_service_error(self, client):
        body = _assert_envelope(client.get("/nowing-external"), 502)
        assert body["error"]["code"] == "EXTERNAL_SERVICE_ERROR"

    def test_validation_error_custom(self, client):
        body = _assert_envelope(client.get("/nowing-validation"), 422)
        assert body["error"]["code"] == "VALIDATION_ERROR"

    def test_permission_denied_error(self, client):
        body = _assert_envelope(client.get("/nowing-permission-denied"), 403)
        assert body["error"]["code"] == "PERMISSION_DENIED"

    def test_oauth_error(self, client):
        body = _assert_envelope(client.get("/nowing-oauth"), 502)
        assert body["error"]["code"] == "OAUTH_ERROR"

    def test_indexing_error(self, client):
        body = _assert_envelope(client.get("/nowing-indexing"), 502)
        assert body["error"]["code"] == "INDEXING_ERROR"

    def test_rate_limit_error(self, client):
        body = _assert_envelope(client.get("/nowing-rate-limit"), 429)
        assert body["error"]["code"] == "RATE_LIMITED"

    def test_upload_error(self, client):
        body = _assert_envelope(client.get("/nowing-upload"), 400)
        assert body["error"]["code"] == "UPLOAD_ERROR"

    def test_parse_error(self, client):
        body = _assert_envelope(client.get("/nowing-parse"), 422)
        assert body["error"]["code"] == "PARSE_ERROR"

    def test_storage_error(self, client):
        body = _assert_envelope(client.get("/nowing-storage"), 500)
        assert body["error"]["code"] == "STORAGE_ERROR"

    def test_llm_error(self, client):
        body = _assert_envelope(client.get("/nowing-llm"), 502)
        assert body["error"]["code"] == "LLM_ERROR"

    def test_context_overflow_error(self, client):
        body = _assert_envelope(client.get("/nowing-context-overflow"), 413)
        assert body["error"]["code"] == "CONTEXT_OVERFLOW"

    def test_model_unavailable_error(self, client):
        body = _assert_envelope(client.get("/nowing-model-unavailable"), 503)
        assert body["error"]["code"] == "MODEL_UNAVAILABLE"

    def test_external_api_error(self, client):
        body = _assert_envelope(client.get("/nowing-external-api"), 502)
        assert body["error"]["code"] == "EXTERNAL_API_ERROR"


# ---------------------------------------------------------------------------
# Unhandled exception (catch-all)
# ---------------------------------------------------------------------------


class TestUnhandledException:
    def test_returns_500_generic_message(self, client):
        body = _assert_envelope(client.get("/unhandled"), 500)
        assert body["error"]["code"] == "INTERNAL_ERROR"
        assert body["error"]["message"] == GENERIC_5XX_MESSAGE
        assert "should never reach" not in json.dumps(body)


# ---------------------------------------------------------------------------
# RequestValidationError (pydantic / FastAPI)
# ---------------------------------------------------------------------------


class TestValidationErrorHandler:
    def test_missing_fields(self, client):
        resp = client.post("/validated", json={})
        body = _assert_envelope(resp, 422)
        assert body["error"]["code"] == "VALIDATION_ERROR"
        assert "required" in body["error"]["message"].lower()

    def test_wrong_type(self, client):
        resp = client.post("/validated", json={"name": "test", "count": "not-a-number"})
        body = _assert_envelope(resp, 422)
        assert body["error"]["code"] == "VALIDATION_ERROR"

    # --- AC-2: structured error.fields array ---------------------------------

    def test_422_includes_error_fields_array(self, client):
        resp = client.post("/scrape", json={"urls": ["not-a-url"]})
        body = _assert_envelope(resp, 422)
        fields = body["error"].get("fields")
        assert isinstance(fields, list) and len(fields) == 1
        item = fields[0]
        assert set(item.keys()) == {"loc", "msg"}
        assert isinstance(item["loc"], list)
        assert isinstance(item["msg"], str) and len(item["msg"]) > 0

    def test_error_fields_loc_starts_at_field_not_body(self, client):
        # "body" root prefix must not leak into loc paths or the message summary.
        resp = client.post("/scrape", json={"urls": ["not-a-url"]})
        body = _assert_envelope(resp, 422)
        fields = body["error"]["fields"]
        assert fields[0]["loc"][0] == "urls"
        assert "body" not in body["error"]["message"].lower()

    def test_error_fields_reports_multiple_invalid_fields(self, client):
        resp = client.post("/validated", json={"name": "", "count": "x"})
        body = _assert_envelope(resp, 422)
        fields = body["error"]["fields"]
        assert len(fields) == 2
        assert {"name", "count"} == {f["loc"][0] for f in fields}

    def test_error_fields_list_index_loc_preserved(self, client):
        # ["urls", 1] style list-index loc survives into the envelope.
        resp = client.post("/scrape", json={"urls": ["https://example.com", "bad"]})
        body = _assert_envelope(resp, 422)
        fields = body["error"]["fields"]
        assert fields[0]["loc"] == ["urls", 1]

    def test_error_fields_non_list_body_still_422(self, client):
        # null / non-object body must not crash the handler.
        resp = client.post("/scrape", json=None)
        body = _assert_envelope(resp, 422)
        assert body["error"]["code"] == "VALIDATION_ERROR"

    def test_validation_error_with_zero_errors_has_fallback_message(self, client):
        # Over-mocking guard: empty exc.errors() -> no crash, generic message.
        from fastapi import Request
        from fastapi.exceptions import RequestValidationError

        from app.app import _validation_error_handler

        request = Request(
            {"type": "http", "method": "POST", "path": "/scrape", "headers": []}
        )
        resp = _validation_error_handler(request, RequestValidationError(errors=[]))
        body = json.loads(resp.body)
        assert body["error"]["code"] == "VALIDATION_ERROR"
        assert body["error"]["message"] == "Validation failed."


# ---------------------------------------------------------------------------
# NowingError class hierarchy unit tests
# ---------------------------------------------------------------------------


class TestNowingErrorClasses:
    def test_base_defaults(self):
        err = NowingError()
        assert err.code == "INTERNAL_ERROR"
        assert err.status_code == 500
        assert err.safe_for_client is True

    def test_connector_error(self):
        err = ConnectorError("fail")
        assert err.code == "CONNECTOR_ERROR"
        assert err.status_code == 502

    def test_database_error(self):
        err = DatabaseError()
        assert err.status_code == 500

    def test_not_found_error(self):
        err = NotFoundError()
        assert err.status_code == 404

    def test_forbidden_error(self):
        err = ForbiddenError()
        assert err.status_code == 403

    def test_custom_code(self):
        err = ConnectorError("x", code="GITHUB_TOKEN_EXPIRED")
        assert err.code == "GITHUB_TOKEN_EXPIRED"

    def test_permission_denied_defaults(self):
        err = PermissionDeniedError()
        assert err.status_code == 403
        assert err.code == "PERMISSION_DENIED"

    def test_oauth_error(self):
        err = OAuthError("token expired")
        assert err.code == "OAUTH_ERROR"
        assert err.status_code == 502

    def test_indexing_error(self):
        err = IndexingError("connector failed")
        assert err.code == "INDEXING_ERROR"
        assert err.status_code == 502

    def test_rate_limit_error(self):
        err = RateLimitError()
        assert err.code == "RATE_LIMITED"
        assert err.status_code == 429

    def test_document_error_subclasses(self):
        assert UploadError("x").status_code == 400
        assert ParseError("x").status_code == 422
        assert StorageError("x").status_code == 500

    def test_llm_error_subclasses(self):
        assert LLMError("x").status_code == 502
        assert ContextOverflowError().status_code == 413
        assert ModelUnavailableError().status_code == 503

    def test_external_api_error(self):
        err = ExternalAPIError("x")
        assert err.code == "EXTERNAL_API_ERROR"
        assert err.status_code == 502
