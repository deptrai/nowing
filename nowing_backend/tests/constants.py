"""Shared test constants.

Import these wherever you need stable, project-wide test values.
Avoid hardcoding these strings directly in test files.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

TEST_EMAIL = "testuser@nowing.com"
TEST_PASSWORD = "testpassword123"

# ---------------------------------------------------------------------------
# API routes
# ---------------------------------------------------------------------------

AUTH_LOGIN = "/auth/jwt/login"
AUTH_REGISTER = "/auth/register"

DOCUMENTS_UPLOAD = "/api/v1/documents/fileupload"
DOCUMENTS_STATUS = "/api/v1/documents/status"

SEARCHSPACES_LIST = "/api/v1/searchspaces"

STRIPE_STATUS = "/api/v1/stripe/status"
STRIPE_CHECKOUT = "/api/v1/stripe/create-checkout-session"

NOTIFICATIONS_LIST = "/api/v1/notifications"

DEXSCREENER_ADD = "/api/v1/connectors/dexscreener/add"
DEXSCREENER_LIST = "/api/v1/connectors/dexscreener"
DEXSCREENER_TEST = "/api/v1/connectors/dexscreener/test"
