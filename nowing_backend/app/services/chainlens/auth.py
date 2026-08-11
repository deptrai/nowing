"""Service-to-service auth adapter for chainlens-research.

Story 20.4 replaces the temporary ``auth_stub.py`` with ``ChainLensServiceAuth``:
- One or more service tokens via ``CHAINLENS_SERVICE_TOKEN`` (comma-separated)
  with ``CHAINLENS_API_KEY`` as legacy fallback.
- Outbound requests carry ``Authorization``, ``X-Correlation-Id``,
  ``X-Workspace-Id`` headers.
- Inbound callbacks from chainlens-research are validated against the same
  token pool and mapped to the workspace supplied in ``X-Workspace-Id``.
- Best-effort rotation on ``401`` responses and on tokens that look close to
  expiry (JWT ``exp`` claim within 30 days).

 ponytail: For MVP tokens live in env; a future ``ChainLensServiceToken``
 Postgres-backed store can be plugged in by replacing ``_load_tokens``.
"""

from __future__ import annotations

import base64
import binascii
import json
import logging
import time
import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from functools import lru_cache
from typing import Any

from fastapi import HTTPException, Request
from starlette.status import HTTP_401_UNAUTHORIZED

from app.config import config

logger = logging.getLogger(__name__)

# 30 days in seconds; used for JWT exp pre-emptive rotation.
_ROTATION_THRESHOLD_SECONDS = 30 * 24 * 60 * 60
_AUTHORIZATION_BEARER_PREFIX = "Bearer "


@dataclass(frozen=True, slots=True)
class ChainLensAuthContext:
    """Inbound validated context from a chainlens-research callback."""

    workspace_id: int
    correlation_id: str | None
    token: str


class ChainLensServiceAuth:
    """Manage service-to-service tokens for chainlens-research."""

    def __init__(
        self,
        *,
        tokens: Sequence[str] | None = None,
        config_obj: Any | None = None,
    ) -> None:
        if tokens is None:
            tokens = self._load_tokens(config_obj)
        # Deduplicate while preserving order.
        seen: set[str] = set()
        self._tokens: list[str] = []
        for token in tokens:
            token = token.strip()
            if token and token not in seen:
                seen.add(token)
                self._tokens.append(token)
        self._index = 0

    @staticmethod
    def _load_tokens(config_obj: Any | None = None) -> list[str]:
        """Load tokens from environment.

        ``CHAINLENS_SERVICE_TOKEN`` is the preferred service-to-service token.
        ``CHAINLENS_API_KEY`` is a legacy alias. Both may be comma-separated for
        rotation. ``config_obj`` overrides the global config for testing.
        """
        cfg = config_obj if config_obj is not None else config
        raw: list[str] = []
        service_token = getattr(cfg, "CHAINLENS_SERVICE_TOKEN", "")
        if service_token:
            raw.extend(service_token.split(","))
        api_key = getattr(cfg, "CHAINLENS_API_KEY", "")
        if api_key:
            raw.extend(api_key.split(","))
        return [t.strip() for t in raw if t.strip()]

    @property
    def configured(self) -> bool:
        return bool(self._tokens)

    @property
    def current_token(self) -> str:
        """Return the currently-selected token.

        Raises ``ValueError`` when no token is configured so callers can turn
        this into a fail-open ``service_auth_unavailable`` response instead of
        exposing an internal error.
        """
        if not self._tokens:
            raise ValueError("No chainlens service token configured")
        return self._tokens[self._index % len(self._tokens)]

    def _token_expiry(self, token: str) -> float | None:
        """Best-effort JWT ``exp`` extraction. Returns None for opaque secrets."""
        parts = token.split(".")
        if len(parts) != 3:
            return None
        try:
            payload_b64 = parts[1]
            # JWT payload is base64url; add padding if needed.
            padding = 4 - len(payload_b64) % 4
            if padding != 4:
                payload_b64 += "=" * padding
            payload_bytes = base64.urlsafe_b64decode(payload_b64)
            payload = json.loads(payload_bytes)
        except (binascii.Error, json.JSONDecodeError, ValueError, UnicodeDecodeError):
            return None
        exp = payload.get("exp")
        if isinstance(exp, (int, float)):
            return float(exp)
        return None

    def rotate(self) -> str | None:
        """Move to the next configured token and return it.

        Returns ``None`` if no additional token is available.
        """
        if len(self._tokens) <= 1:
            logger.warning(
                "ChainLens service token rotation requested but only one token configured"
            )
            return None
        self._index = (self._index + 1) % len(self._tokens)
        token = self.current_token
        logger.info(
            "Rotated chainlens service token (index %d of %d)",
            self._index,
            len(self._tokens),
        )
        return token

    def rotate_if_expiring(self) -> str | None:
        """Pre-emptively rotate when the current token's JWT exp is within 30d.

        Returns the new token if rotated, otherwise None.
        """
        if len(self._tokens) <= 1:
            return None
        exp = self._token_expiry(self.current_token)
        if exp is None:
            return None
        if exp - time.time() < _ROTATION_THRESHOLD_SECONDS:
            return self.rotate()
        return None

    def get_outbound_headers(
        self,
        workspace_id: int,
        *,
        correlation_id: str | None = None,
        content_type: str | None = None,
    ) -> dict[str, str]:
        """Return headers for outbound chainlens-research requests.

        The bearer token comes from ``current_token``. ``X-Correlation-Id`` is
        generated if not supplied so every request is traceable.
        """
        self.rotate_if_expiring()
        token = self.current_token
        headers: dict[str, str] = {
            "Authorization": f"{_AUTHORIZATION_BEARER_PREFIX}{token}",
            "X-Workspace-Id": str(workspace_id),
        }
        if correlation_id:
            headers["X-Correlation-Id"] = correlation_id
        else:
            headers["X-Correlation-Id"] = str(uuid.uuid4())
        if content_type:
            headers["Content-Type"] = content_type
        return headers

    def validate_inbound_token(self, request: Request) -> ChainLensAuthContext:
        """Validate an inbound request from chainlens-research.

        Checks ``Authorization: Bearer <token>`` against the configured token
        pool and extracts ``X-Workspace-Id`` / ``X-Correlation-Id``. Raises
        ``HTTPException(401)`` on missing/invalid token.
        """
        auth_header = request.headers.get("authorization", "")
        if not auth_header.startswith(_AUTHORIZATION_BEARER_PREFIX):
            raise HTTPException(
                status_code=HTTP_401_UNAUTHORIZED,
                detail="Missing or invalid Authorization header",
            )
        token = auth_header[len(_AUTHORIZATION_BEARER_PREFIX) :].strip()
        if token not in self._tokens:
            raise HTTPException(
                status_code=HTTP_401_UNAUTHORIZED,
                detail="Invalid chainlens service token",
            )

        workspace_id_str = request.headers.get("x-workspace-id", "")
        if not workspace_id_str:
            raise HTTPException(
                status_code=HTTP_401_UNAUTHORIZED,
                detail="Missing X-Workspace-Id header",
            )
        try:
            workspace_id = int(workspace_id_str)
        except ValueError as exc:
            raise HTTPException(
                status_code=HTTP_401_UNAUTHORIZED,
                detail="Invalid X-Workspace-Id header",
            ) from exc

        return ChainLensAuthContext(
            workspace_id=workspace_id,
            correlation_id=request.headers.get("x-correlation-id"),
            token=token,
        )

    @classmethod
    def cost_dollars_to_micros(cls, cost_dollars: float) -> int:
        """Convert USD to micro-USD with half-up rounding.

        Matches the conversion used in ``chainlens.research.executor``.
        """
        from decimal import ROUND_HALF_UP, Decimal

        micros = (Decimal(str(cost_dollars)) * Decimal("1000000")).to_integral_value(
            ROUND_HALF_UP
        )
        return int(micros)


@lru_cache(maxsize=1)
def get_chainlens_auth() -> ChainLensServiceAuth:
    """Return the process-wide ``ChainLensServiceAuth`` instance."""
    return ChainLensServiceAuth()


# Re-export the legacy stub signature so existing imports keep working until
# callers are migrated to the class-based API.
def get_chainlens_auth_header(config: Any | None = None) -> dict[str, str]:
    """Return an ``Authorization`` header dict for backwards compatibility.

    Does not include workspace/correlation headers; prefer
    ``ChainLensServiceAuth.get_outbound_headers``.
    """
    auth = get_chainlens_auth()
    if not auth.configured:
        return {}
    # Back-compat: no workspace id available, so use 0 as placeholder.
    headers = auth.get_outbound_headers(workspace_id=0, correlation_id=None)
    return {"Authorization": headers["Authorization"]}
