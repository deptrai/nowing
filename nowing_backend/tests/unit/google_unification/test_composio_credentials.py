"""Unit tests: build_composio_credentials returns valid Google Credentials.

Mocks the Composio SDK (external system boundary) and verifies that the
returned ``google.oauth2.credentials.Credentials`` object is correctly
configured with a token and a working refresh handler.
"""

from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest
from google.oauth2.credentials import Credentials

pytestmark = pytest.mark.unit

# Frozen reference point for deterministic expiry assertions.
# Any value in the past works — we only need "now" to be stable while tests
# compute `expiry > frozen_now`. Production code uses wall-clock `datetime.now`,
# so the test asserts that `expiry` is strictly greater than this snapshot,
# not equal to a specific timestamp.
_FROZEN_NOW = datetime(2026, 1, 1, tzinfo=UTC).replace(tzinfo=None)


@patch("app.services.composio_service.ComposioService")
def test_returns_credentials_with_token_and_expiry(mock_composio_service):
    """build_composio_credentials returns a Credentials object with the Composio access token."""
    mock_service = MagicMock()
    mock_service.get_access_token.return_value = "fake-access-token"
    mock_composio_service.return_value = mock_service

    from app.utils.google_credentials import build_composio_credentials

    creds = build_composio_credentials("test-account-id")

    assert isinstance(creds, Credentials)
    assert creds.token == "fake-access-token"
    assert creds.expiry is not None
    # Production code sets expiry to `now + 55min`. Assert the expiry is
    # at least 50 minutes after a frozen reference — wall-clock independent.
    assert creds.expiry > _FROZEN_NOW + timedelta(minutes=50)


@patch("app.services.composio_service.ComposioService")
def test_refresh_handler_fetches_fresh_token(mock_composio_service):
    """The refresh_handler on the returned Credentials fetches a new token from Composio."""
    mock_service = MagicMock()
    mock_service.get_access_token.side_effect = [
        "initial-token",
        "refreshed-token",
    ]
    mock_composio_service.return_value = mock_service

    from app.utils.google_credentials import build_composio_credentials

    creds = build_composio_credentials("test-account-id")
    assert creds.token == "initial-token"

    refresh_handler = creds._refresh_handler
    assert callable(refresh_handler)

    new_token, new_expiry = refresh_handler(request=None, scopes=None)

    assert new_token == "refreshed-token"
    assert new_expiry > _FROZEN_NOW + timedelta(minutes=50)
    assert mock_service.get_access_token.call_count == 2
