"""Config domain: E2E test provisioning (Phase 0/3 no-mock E2E).

Loads ``E2E_PROVISION_ENABLED`` + ``E2E_<PROVIDER>_*`` env vars used by the
gated ``POST /__e2e__/connectors/provision`` endpoint. When the master flag is
off (default), the route is not registered at all — production stays silent.

Provider keys never carry default secrets; missing values yield ``None`` and
the provision route returns 404 for that provider (never partially provisions).
"""

from __future__ import annotations

import os

# Master switch — mount the /__e2e__/connectors/provision route only when
# explicitly enabled. Default FALSE so prod stays 404.
E2E_PROVISION_ENABLED = (
    os.getenv("E2E_PROVISION_ENABLED", "FALSE").upper() == "TRUE"
)

# Mapping of provider key -> {env_name: env_value}. The endpoint uses the key
# name (lowercase) to look up this dict; missing required keys → 404.
#
# Each provider's required env vars:
#   slack           : E2E_SLACK_BOT_TOKEN, E2E_SLACK_TEAM_ID, E2E_SLACK_TEAM_NAME (optional BOT_USER_ID, REFRESH_TOKEN)
#   notion          : E2E_NOTION_ACCESS_TOKEN (optional WORKSPACE_ID, WORKSPACE_NAME, BOT_ID, REFRESH_TOKEN)
#   linear          : E2E_LINEAR_ACCESS_TOKEN, E2E_LINEAR_CLIENT_ID, E2E_LINEAR_TOKEN_ENDPOINT (optional REFRESH_TOKEN, CLIENT_SECRET)
#   jira            : E2E_JIRA_ACCESS_TOKEN, E2E_JIRA_CLIENT_ID, E2E_JIRA_TOKEN_ENDPOINT, E2E_JIRA_CLOUD_ID, E2E_JIRA_BASE_URL (optional REFRESH_TOKEN, CLIENT_SECRET, SITE_NAME)
#   clickup         : E2E_CLICKUP_ACCESS_TOKEN, E2E_CLICKUP_CLIENT_ID, E2E_CLICKUP_TOKEN_ENDPOINT, E2E_CLICKUP_WORKSPACE_ID, E2E_CLICKUP_WORKSPACE_NAME (optional REFRESH_TOKEN, CLIENT_SECRET)
#   confluence      : E2E_CONFLUENCE_ACCESS_TOKEN, E2E_CONFLUENCE_CLIENT_ID, E2E_CONFLUENCE_TOKEN_ENDPOINT, E2E_CONFLUENCE_CLOUD_ID, E2E_CONFLUENCE_BASE_URL (optional REFRESH_TOKEN, CLIENT_SECRET)
#   airtable        : E2E_AIRTABLE_ACCESS_TOKEN, E2E_AIRTABLE_CLIENT_ID, E2E_AIRTABLE_TOKEN_ENDPOINT (optional REFRESH_TOKEN, CLIENT_SECRET)
#   google_drive    : E2E_GOOGLE_CLIENT_ID, E2E_GOOGLE_CLIENT_SECRET, E2E_GOOGLE_REFRESH_TOKEN (backend mints access_token lazily)
#   gmail           : same google_* envs
#   google_calendar : same google_* envs
#   dropbox         : E2E_DROPBOX_ACCESS_TOKEN (optional REFRESH_TOKEN, APP_KEY, APP_SECRET)
#   onedrive        : E2E_ONEDRIVE_ACCESS_TOKEN (optional REFRESH_TOKEN, CLIENT_ID, CLIENT_SECRET)
#   composio_drive  : E2E_COMPOSIO_API_KEY, E2E_COMPOSIO_DRIVE_ACCOUNT_ID
#   composio_gmail  : E2E_COMPOSIO_API_KEY, E2E_COMPOSIO_GMAIL_ACCOUNT_ID
#   composio_calendar: E2E_COMPOSIO_API_KEY, E2E_COMPOSIO_CALENDAR_ACCOUNT_ID

E2E_PROVIDER_ENV: dict[str, dict[str, str | None]] = {
    "slack": {
        "bot_token": os.getenv("E2E_SLACK_BOT_TOKEN"),
        "refresh_token": os.getenv("E2E_SLACK_REFRESH_TOKEN"),
        "bot_user_id": os.getenv("E2E_SLACK_BOT_USER_ID"),
        "team_id": os.getenv("E2E_SLACK_TEAM_ID"),
        "team_name": os.getenv("E2E_SLACK_TEAM_NAME"),
    },
    "notion": {
        "access_token": os.getenv("E2E_NOTION_ACCESS_TOKEN"),
        "refresh_token": os.getenv("E2E_NOTION_REFRESH_TOKEN"),
        "workspace_id": os.getenv("E2E_NOTION_WORKSPACE_ID"),
        "workspace_name": os.getenv("E2E_NOTION_WORKSPACE_NAME"),
        "bot_id": os.getenv("E2E_NOTION_BOT_ID"),
    },
    "linear": {
        "access_token": os.getenv("E2E_LINEAR_ACCESS_TOKEN"),
        "refresh_token": os.getenv("E2E_LINEAR_REFRESH_TOKEN"),
        "client_id": os.getenv("E2E_LINEAR_CLIENT_ID"),
        "client_secret": os.getenv("E2E_LINEAR_CLIENT_SECRET"),
        "token_endpoint": os.getenv("E2E_LINEAR_TOKEN_ENDPOINT"),
        "expires_in": os.getenv("E2E_LINEAR_EXPIRES_IN"),
        "scope": os.getenv("E2E_LINEAR_SCOPE"),
        "organization_name": os.getenv("E2E_LINEAR_ORGANIZATION_NAME"),
        "organization_url_key": os.getenv("E2E_LINEAR_ORGANIZATION_URL_KEY"),
    },
    "jira": {
        "access_token": os.getenv("E2E_JIRA_ACCESS_TOKEN"),
        "refresh_token": os.getenv("E2E_JIRA_REFRESH_TOKEN"),
        "client_id": os.getenv("E2E_JIRA_CLIENT_ID"),
        "client_secret": os.getenv("E2E_JIRA_CLIENT_SECRET"),
        "token_endpoint": os.getenv("E2E_JIRA_TOKEN_ENDPOINT"),
        "expires_in": os.getenv("E2E_JIRA_EXPIRES_IN"),
        "scope": os.getenv("E2E_JIRA_SCOPE"),
        "cloud_id": os.getenv("E2E_JIRA_CLOUD_ID"),
        "site_name": os.getenv("E2E_JIRA_SITE_NAME"),
        "base_url": os.getenv("E2E_JIRA_BASE_URL"),
    },
    "clickup": {
        "access_token": os.getenv("E2E_CLICKUP_ACCESS_TOKEN"),
        "refresh_token": os.getenv("E2E_CLICKUP_REFRESH_TOKEN"),
        "client_id": os.getenv("E2E_CLICKUP_CLIENT_ID"),
        "client_secret": os.getenv("E2E_CLICKUP_CLIENT_SECRET"),
        "token_endpoint": os.getenv("E2E_CLICKUP_TOKEN_ENDPOINT"),
        "expires_in": os.getenv("E2E_CLICKUP_EXPIRES_IN"),
        "scope": os.getenv("E2E_CLICKUP_SCOPE"),
        "workspace_id": os.getenv("E2E_CLICKUP_WORKSPACE_ID"),
        "workspace_name": os.getenv("E2E_CLICKUP_WORKSPACE_NAME"),
    },
    "confluence": {
        "access_token": os.getenv("E2E_CONFLUENCE_ACCESS_TOKEN"),
        "refresh_token": os.getenv("E2E_CONFLUENCE_REFRESH_TOKEN"),
        "client_id": os.getenv("E2E_CONFLUENCE_CLIENT_ID"),
        "client_secret": os.getenv("E2E_CONFLUENCE_CLIENT_SECRET"),
        "token_endpoint": os.getenv("E2E_CONFLUENCE_TOKEN_ENDPOINT"),
        "expires_in": os.getenv("E2E_CONFLUENCE_EXPIRES_IN"),
        "scope": os.getenv("E2E_CONFLUENCE_SCOPE"),
        "cloud_id": os.getenv("E2E_CONFLUENCE_CLOUD_ID"),
        "base_url": os.getenv("E2E_CONFLUENCE_BASE_URL"),
    },
    "airtable": {
        "access_token": os.getenv("E2E_AIRTABLE_ACCESS_TOKEN"),
        "refresh_token": os.getenv("E2E_AIRTABLE_REFRESH_TOKEN"),
        "client_id": os.getenv("E2E_AIRTABLE_CLIENT_ID"),
        "client_secret": os.getenv("E2E_AIRTABLE_CLIENT_SECRET"),
        "token_endpoint": os.getenv("E2E_AIRTABLE_TOKEN_ENDPOINT"),
        "expires_in": os.getenv("E2E_AIRTABLE_EXPIRES_IN"),
        "scope": os.getenv("E2E_AIRTABLE_SCOPE"),
        "user_id": os.getenv("E2E_AIRTABLE_USER_ID"),
        "user_email": os.getenv("E2E_AIRTABLE_USER_EMAIL"),
    },
    # Google OAuth-backed connectors share the same refresh-token envs.
    "google_drive": {
        "client_id": os.getenv("E2E_GOOGLE_CLIENT_ID"),
        "client_secret": os.getenv("E2E_GOOGLE_CLIENT_SECRET"),
        "refresh_token": os.getenv("E2E_GOOGLE_REFRESH_TOKEN"),
    },
    "gmail": {
        "client_id": os.getenv("E2E_GOOGLE_CLIENT_ID"),
        "client_secret": os.getenv("E2E_GOOGLE_CLIENT_SECRET"),
        "refresh_token": os.getenv("E2E_GOOGLE_REFRESH_TOKEN"),
    },
    "google_calendar": {
        "client_id": os.getenv("E2E_GOOGLE_CLIENT_ID"),
        "client_secret": os.getenv("E2E_GOOGLE_CLIENT_SECRET"),
        "refresh_token": os.getenv("E2E_GOOGLE_REFRESH_TOKEN"),
    },
    "dropbox": {
        "access_token": os.getenv("E2E_DROPBOX_ACCESS_TOKEN"),
        "refresh_token": os.getenv("E2E_DROPBOX_REFRESH_TOKEN"),
        "app_key": os.getenv("E2E_DROPBOX_APP_KEY"),
        "app_secret": os.getenv("E2E_DROPBOX_APP_SECRET"),
    },
    "onedrive": {
        "access_token": os.getenv("E2E_ONEDRIVE_ACCESS_TOKEN"),
        "refresh_token": os.getenv("E2E_ONEDRIVE_REFRESH_TOKEN"),
        "client_id": os.getenv("E2E_ONEDRIVE_CLIENT_ID"),
        "client_secret": os.getenv("E2E_ONEDRIVE_CLIENT_SECRET"),
    },
    "composio_drive": {
        "api_key": os.getenv("E2E_COMPOSIO_API_KEY"),
        "connected_account_id": os.getenv("E2E_COMPOSIO_DRIVE_ACCOUNT_ID"),
    },
    "composio_gmail": {
        "api_key": os.getenv("E2E_COMPOSIO_API_KEY"),
        "connected_account_id": os.getenv("E2E_COMPOSIO_GMAIL_ACCOUNT_ID"),
    },
    "composio_calendar": {
        "api_key": os.getenv("E2E_COMPOSIO_API_KEY"),
        "connected_account_id": os.getenv("E2E_COMPOSIO_CALENDAR_ACCOUNT_ID"),
    },
    # Non-connector E2E envs documented for completeness; the provision
    # endpoint doesn't accept these as `connector` values.
    "mailgun": {
        "signing_key": os.getenv("E2E_MAILGUN_SIGNING_KEY"),
    },
    "stripe_test": {
        "test_key": os.getenv("E2E_STRIPE_TEST_KEY"),
    },
}


__all__ = ["E2E_PROVIDER_ENV", "E2E_PROVISION_ENABLED"]
