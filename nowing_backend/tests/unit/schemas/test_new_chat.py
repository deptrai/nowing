"""Red-phase unit tests for Story 18.2 NewChatRequest schema extensions.

These tests exercise ``NewChatRequest``, ``NewChatThreadCreate``, and
``RegenerateRequest`` with the new ``agent_id``, ``client_id``, and
``platform_metadata`` fields.  They are pure Pydantic instantiation tests —
no database — and will fail until 18.2 adds the fields and validators to
``app/schemas/new_chat.py``.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.schemas.new_chat import NewChatRequest, NewChatThreadCreate, RegenerateRequest

pytestmark = pytest.mark.unit


# -----------------------------------------------------------------------------
# NewChatRequest new fields
# -----------------------------------------------------------------------------


def test_new_chat_request_has_agent_client_metadata_fields() -> None:
    """AC-1/AC-3: NewChatRequest model should declare the three new fields."""
    assert "agent_id" in NewChatRequest.model_fields
    assert "client_id" in NewChatRequest.model_fields
    assert "platform_metadata" in NewChatRequest.model_fields


def test_new_chat_request_defaults_are_none() -> None:
    """AC-4: legacy requests without the new fields default to None."""
    req = NewChatRequest(chat_id=1, user_query="hello", workspace_id=1)
    assert req.agent_id is None
    assert req.client_id is None
    assert req.platform_metadata is None


def test_new_chat_request_accepts_agent_client_and_metadata() -> None:
    """AC-1/AC-3: valid values are accepted and round-trip."""
    metadata = {"source": "bdsai", "listing_id": 123}
    req = NewChatRequest(
        chat_id=1,
        user_query="hello",
        workspace_id=1,
        agent_id="bdsai-listing-assistant",
        client_id="bdsai.vn",
        platform_metadata=metadata,
    )
    assert req.agent_id == "bdsai-listing-assistant"
    assert req.client_id == "bdsai.vn"
    assert req.platform_metadata == metadata


def test_new_chat_request_agent_id_requires_client_id() -> None:
    """AC-1/AC-3: agent_id present without client_id should raise ValidationError."""
    with pytest.raises(ValidationError) as exc_info:
        NewChatRequest(
            chat_id=1,
            user_query="hello",
            workspace_id=1,
            agent_id="bdsai-listing-assistant",
        )
    assert "client_id" in str(exc_info.value).lower()


def test_new_chat_request_client_id_matches_agent_scope() -> None:
    """AC-1/AC-2: client_id must be a valid slug and compatible with agent_id."""
    with pytest.raises(ValidationError) as exc_info:
        NewChatRequest(
            chat_id=1,
            user_query="hello",
            workspace_id=1,
            agent_id="bdsai-listing-assistant",
            client_id="INVALID CLIENT",
        )
    assert "client_id" in str(exc_info.value).lower()


def test_new_chat_request_rejects_invalid_agent_id_slug() -> None:
    """AC-1: agent_id must be a lowercase slug."""
    with pytest.raises(ValidationError) as exc_info:
        NewChatRequest(
            chat_id=1,
            user_query="hello",
            workspace_id=1,
            agent_id="Bad Agent!",
            client_id="bdsai.vn",
        )
    assert "agent_id" in str(exc_info.value).lower()


@pytest.mark.parametrize(
    "field,value",
    [
        ("agent_id", "a" * 64),
        ("client_id", "b" * 64),
    ],
)
def test_new_chat_request_rejects_long_slugs(field: str, value: str) -> None:
    """AC-1/AC-2: slugs are bounded to 63 characters."""
    kwargs = {
        "chat_id": 1,
        "user_query": "hello",
        "workspace_id": 1,
        "agent_id": "bdsai-listing-assistant",
        "client_id": "bdsai.vn",
        field: value,
    }
    with pytest.raises(ValidationError) as exc_info:
        NewChatRequest(**kwargs)
    assert field in str(exc_info.value).lower()


def test_new_chat_request_rejects_empty_client_id() -> None:
    """AC-2: empty client_id is not a valid vertical client slug."""
    with pytest.raises(ValidationError) as exc_info:
        NewChatRequest(
            chat_id=1,
            user_query="hello",
            workspace_id=1,
            agent_id="bdsai-listing-assistant",
            client_id="",
        )
    assert "client_id" in str(exc_info.value).lower()


# -----------------------------------------------------------------------------
# platform_metadata bounds and safety
# -----------------------------------------------------------------------------


def test_new_chat_request_accepts_nested_platform_metadata() -> None:
    """AC-3: platform_metadata may contain nested JSON objects/arrays."""
    metadata = {
        "listing": {
            "id": 42,
            "tags": ["bds", "listing"],
        },
        "extra": {"nested": {"token": "{secret}"}},
    }
    req = NewChatRequest(
        chat_id=1,
        user_query="hello",
        workspace_id=1,
        client_id="bdsai.vn",
        platform_metadata=metadata,
    )
    assert req.platform_metadata == metadata


def test_new_chat_request_rejects_oversized_platform_metadata() -> None:
    """AC-3: platform_metadata is bounded to prevent prompt-context abuse."""
    with pytest.raises(ValidationError) as exc_info:
        NewChatRequest(
            chat_id=1,
            user_query="hello",
            workspace_id=1,
            client_id="bdsai.vn",
            platform_metadata={f"key_{i}": "x" for i in range(64)},
        )
    assert "platform_metadata" in str(exc_info.value).lower()


def test_new_chat_request_rejects_long_string_in_platform_metadata() -> None:
    """AC-3: platform_metadata string values are bounded."""
    with pytest.raises(ValidationError) as exc_info:
        NewChatRequest(
            chat_id=1,
            user_query="hello",
            workspace_id=1,
            client_id="bdsai.vn",
            platform_metadata={"payload": "x" * 2048},
        )
    assert "platform_metadata" in str(exc_info.value).lower()


def test_new_chat_request_rejects_non_json_serializable_platform_metadata() -> None:
    """AC-3: platform_metadata values must be JSON-serializable primitives."""
    with pytest.raises(ValidationError) as exc_info:
        NewChatRequest(
            chat_id=1,
            user_query="hello",
            workspace_id=1,
            client_id="bdsai.vn",
            platform_metadata={"bad": {1, 2, 3}},
        )
    assert "platform_metadata" in str(exc_info.value).lower()


def test_new_chat_request_platform_metadata_no_secret_interpolation() -> None:
    """AC-3: curly braces that look like format placeholders round-trip verbatim."""
    metadata = {"token": "{secret}", "template": "{{api_key}}"}
    req = NewChatRequest(
        chat_id=1,
        user_query="hello",
        workspace_id=1,
        client_id="bdsai.vn",
        platform_metadata=metadata,
    )
    assert req.platform_metadata["token"] == "{secret}"
    assert req.platform_metadata["template"] == "{{api_key}}"


# -----------------------------------------------------------------------------
# NewChatThreadCreate new fields
# -----------------------------------------------------------------------------


def test_new_chat_thread_create_has_client_id_and_agent_id() -> None:
    """AC-1/AC-2: NewChatThreadCreate should declare client_id and agent_id."""
    assert "client_id" in NewChatThreadCreate.model_fields
    assert "agent_id" in NewChatThreadCreate.model_fields


def test_new_chat_thread_create_accepts_client_id_and_agent_id() -> None:
    """AC-1/AC-2: thread creation schema accepts client_id/agent_id."""
    req = NewChatThreadCreate(
        workspace_id=1,
        client_id="bdsai.vn",
        agent_id="bdsai-listing-assistant",
    )
    assert req.client_id == "bdsai.vn"
    assert req.agent_id == "bdsai-listing-assistant"


def test_new_chat_thread_create_defaults_to_none() -> None:
    """AC-4: legacy thread creation has client_id/agent_id default None."""
    req = NewChatThreadCreate(workspace_id=1)
    assert req.client_id is None
    assert req.agent_id is None


def test_new_chat_thread_create_rejects_invalid_agent_id() -> None:
    """AC-1: agent_id in thread create must be a valid slug."""
    with pytest.raises(ValidationError) as exc_info:
        NewChatThreadCreate(
            workspace_id=1,
            client_id="bdsai.vn",
            agent_id="BAD AGENT",
        )
    assert "agent_id" in str(exc_info.value).lower()


def test_new_chat_thread_create_rejects_invalid_client_id() -> None:
    """AC-2: client_id in thread create must be a valid slug."""
    with pytest.raises(ValidationError) as exc_info:
        NewChatThreadCreate(
            workspace_id=1,
            client_id="",
            agent_id="bdsai-listing-assistant",
        )
    assert "client_id" in str(exc_info.value).lower()


# -----------------------------------------------------------------------------
# RegenerateRequest new fields
# -----------------------------------------------------------------------------


def test_regenerate_request_has_agent_client_metadata_fields() -> None:
    """AC-1/AC-3: RegenerateRequest mirrors the three new fields."""
    assert "agent_id" in RegenerateRequest.model_fields
    assert "client_id" in RegenerateRequest.model_fields
    assert "platform_metadata" in RegenerateRequest.model_fields


def test_regenerate_request_defaults_are_none() -> None:
    """AC-4: regenerate without the new fields defaults to None."""
    req = RegenerateRequest(workspace_id=1, user_query="hello")
    assert req.agent_id is None
    assert req.client_id is None
    assert req.platform_metadata is None


def test_regenerate_request_accepts_agent_client_and_metadata() -> None:
    """AC-1/AC-3: regenerate can override agent/client/metadata for the new turn."""
    metadata = {"regenerated": True}
    req = RegenerateRequest(
        workspace_id=1,
        user_query="hello",
        agent_id="bdsai-listing-assistant",
        client_id="bdsai.vn",
        platform_metadata=metadata,
    )
    assert req.agent_id == "bdsai-listing-assistant"
    assert req.client_id == "bdsai.vn"
    assert req.platform_metadata == metadata


def test_regenerate_request_agent_id_requires_client_id() -> None:
    """AC-1: agent_id in RegenerateRequest requires client_id."""
    with pytest.raises(ValidationError) as exc_info:
        RegenerateRequest(
            workspace_id=1,
            user_query="hello",
            agent_id="bdsai-listing-assistant",
        )
    assert "client_id" in str(exc_info.value).lower()


def test_regenerate_request_rejects_invalid_platform_metadata() -> None:
    """AC-3: RegenerateRequest platform_metadata is bounded the same way."""
    with pytest.raises(ValidationError) as exc_info:
        RegenerateRequest(
            workspace_id=1,
            user_query="hello",
            client_id="bdsai.vn",
            platform_metadata={f"k{i}": "v" for i in range(100)},
        )
    assert "platform_metadata" in str(exc_info.value).lower()
