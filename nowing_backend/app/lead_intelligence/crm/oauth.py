"""OAuth helpers for CRM providers (Story 21.5).

ponytail: This is a minimal, provider-agnostic OAuth bootstrap.
Salesforce/HubSpot/Pipedrive all support standard OAuth2 + PKCE.
Specific discovery / metadata / token URLs are hard-coded for MVP.
"""

from __future__ import annotations

import json
from urllib.parse import urlencode
from uuid import UUID

import httpx
from fastapi import HTTPException

from app.config import config
from app.utils.oauth_security import (
    OAuthStateManager,
    TokenEncryption,
    generate_pkce_pair,
)

CRM_PROVIDERS = {
    "salesforce": {
        "auth_url": "https://login.salesforce.com/services/oauth2/authorize",
        "token_url": "https://login.salesforce.com/services/oauth2/token",
        "scopes": ["api", "refresh_token"],
        "scope_param": "scope",
    },
    "hubspot": {
        "auth_url": "https://app.hubspot.com/oauth/authorize",
        "token_url": "https://api.hubapi.com/oauth/v1/token",
        "scopes": ["contacts", "crm.objects.contacts.read"],
        "scope_param": "scope",
    },
    "pipedrive": {
        "auth_url": "https://oauth.pipedrive.com/oauth/authorize",
        "token_url": "https://oauth.pipedrive.com/oauth/token",
        "scopes": ["contacts:read", "contacts:write", "deals:read", "deals:write"],
        "scope_param": "scope",
    },
}


def _get_token_encryption() -> TokenEncryption:
    if not config.SECRET_KEY:
        raise HTTPException(status_code=500, detail="SECRET_KEY not configured.")
    return TokenEncryption(config.SECRET_KEY)


def _get_state_manager() -> OAuthStateManager:
    if not config.SECRET_KEY:
        raise HTTPException(status_code=500, detail="SECRET_KEY not configured.")
    return OAuthStateManager(config.SECRET_KEY)


def _get_client_creds(provider: str) -> tuple[str, str, str]:
    client_id = getattr(config, f"{provider.upper()}_CLIENT_ID", "")
    client_secret = getattr(config, f"{provider.upper()}_CLIENT_SECRET", "")
    redirect_uri = getattr(config, f"{provider.upper()}_REDIRECT_URI", "")
    if not client_id or not redirect_uri:
        raise HTTPException(
            status_code=500,
            detail=f"{provider.title()} OAuth not configured.",
        )
    return client_id, client_secret, redirect_uri


def build_auth_url(provider: str, workspace_id: int, user_id: UUID) -> str:
    """Build an OAuth authorization URL for a CRM provider."""
    meta = CRM_PROVIDERS.get(provider)
    if not meta:
        raise HTTPException(status_code=400, detail=f"Unknown CRM provider: {provider}")

    client_id, _, redirect_uri = _get_client_creds(provider)
    verifier, challenge = generate_pkce_pair()
    state = _get_state_manager().generate_secure_state(
        workspace_id,
        user_id,
        provider=provider,
        code_verifier=verifier,
    )

    params: dict[str, str] = {
        "client_id": client_id,
        "response_type": "code",
        "redirect_uri": redirect_uri,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
        "state": state,
    }
    if meta["scopes"]:
        params[meta["scope_param"]] = " ".join(meta["scopes"])

    return f"{meta['auth_url']}?{urlencode(params)}"


async def exchange_code(
    provider: str,
    code: str,
    state: str,
) -> tuple[dict, str]:
    """Exchange an OAuth authorization code for tokens.

    Returns the encrypted credential blob and the raw access token.
    """
    meta = CRM_PROVIDERS.get(provider)
    if not meta:
        raise HTTPException(status_code=400, detail=f"Unknown CRM provider: {provider}")

    state_data = _get_state_manager().validate_state(state)
    stored_provider = state_data.get("provider")
    if stored_provider != provider:
        raise HTTPException(status_code=400, detail="State/provider mismatch")

    code_verifier = state_data.get("code_verifier")
    if not code_verifier:
        raise HTTPException(status_code=400, detail="Missing PKCE verifier")

    client_id, client_secret, redirect_uri = _get_client_creds(provider)
    payload = {
        "grant_type": "authorization_code",
        "client_id": client_id,
        "client_secret": client_secret,
        "code": code,
        "redirect_uri": redirect_uri,
        "code_verifier": code_verifier,
    }

    try:
        async with httpx.AsyncClient(timeout=config.CRM_SYNC_TIMEOUT_SECONDS) as client:
            response = await client.post(meta["token_url"], data=payload)
            response.raise_for_status()
            token_json = response.json()
    except httpx.HTTPError as e:
        raise HTTPException(
            status_code=502, detail=f"{provider.title()} token exchange failed: {e!s}"
        ) from e

    access_token = token_json.get("access_token")
    if not access_token:
        raise HTTPException(status_code=502, detail=f"No access token from {provider}")

    enc = _get_token_encryption()
    credentials = {
        "provider": provider,
        "client_id": client_id,
        "access_token": access_token,
        "refresh_token": token_json.get("refresh_token"),
        "expires_at": _expires_at(token_json.get("expires_in")),
        "scope": token_json.get("scope", ""),
    }
    encrypted = enc.encrypt_token(json.dumps(credentials))
    return encrypted, access_token


def _expires_at(expires_in: int | None) -> str | None:
    if not expires_in:
        return None
    from datetime import UTC, datetime, timedelta

    return (datetime.now(UTC) + timedelta(seconds=int(expires_in))).isoformat()


def decrypt_credentials(credentials_encrypted: str) -> dict:
    """Decrypt and parse the stored credentials blob."""
    if not credentials_encrypted:
        return {}
    enc = _get_token_encryption()
    try:
        return json.loads(enc.decrypt_token(credentials_encrypted))
    except (json.JSONDecodeError, ValueError) as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to decrypt CRM credentials: {e!s}"
        ) from e
