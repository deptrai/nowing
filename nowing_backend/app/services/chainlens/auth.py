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
import hashlib
import hmac
import json
import logging
import math
import threading
import time
import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from functools import lru_cache
from typing import Any

from fastapi import HTTPException, Request, status

from app.config import config
from app.observability import metrics

logger = logging.getLogger(__name__)

# 30 days in seconds; used for JWT exp pre-emptive rotation.
_ROTATION_THRESHOLD_SECONDS = 30 * 24 * 60 * 60
_AUTHORIZATION_BEARER_PREFIX = "Bearer "

# ChainLens HMAC fast-path header. Must match packages/shared/src/auth/hmac.ts.
_USER_CTX_HEADER = "x-user-ctx"
_USER_CTX_TTL_MS = 60 * 1000

# Guard against obviously bogus cost values; does not limit legitimate billing.
_MAX_REASONABLE_COST_DOLLARS = 1_000_000.0


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

        cfg = config_obj if config_obj is not None else config
        self._hmac_secret = (
            getattr(cfg, "CHAINLENS_AUTH_CONTEXT_SECRET", "") or ""
        ).strip()
        self._hmac_user_id = (
            getattr(cfg, "CHAINLENS_HMAC_USER_ID", "00000000-0000-0000-0000-000000000001")
            or "00000000-0000-0000-0000-000000000001"
        ).strip()

        self._index = 0
        self._lock = threading.Lock()

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
        return bool(self._tokens) or bool(self._hmac_secret)

    @property
    def current_token(self) -> str:
        """Return the currently-selected token.

        Raises ``ValueError`` when no token is configured so callers can turn
        this into a fail-open ``service_auth_unavailable`` response instead of
        exposing an internal error.
        """
        with self._lock:
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

    def rotate(self, *, workspace_id: int = 0, reason: str = "expiry") -> str | None:
        """Move to the next configured token and return it.

        Returns ``None`` if no additional token is available.
        """
        if len(self._tokens) <= 1:
            logger.warning(
                "ChainLens service token rotation requested but only one token configured"
            )
            return None
        with self._lock:
            self._index = (self._index + 1) % len(self._tokens)
            token = self._tokens[self._index % len(self._tokens)]
        metrics.record_chainlens_token_rotated(
            workspace_id=workspace_id,
            reason=reason,
        )
        logger.info(
            "Rotated chainlens service token (index %d of %d)",
            self._index,
            len(self._tokens),
        )
        return token

    def rotate_if_expiring(self, *, workspace_id: int = 0) -> str | None:
        """Pre-emptively rotate when the current token's JWT exp is within 30d.

        Returns the new token if rotated, otherwise None.
        """
        if len(self._tokens) <= 1:
            return None
        exp = self._token_expiry(self.current_token)
        if exp is None:
            return None
        if exp < time.time():
            # Current token is already expired; try to find a non-expired one.
            for _ in range(len(self._tokens) - 1):
                rotated = self.rotate(workspace_id=workspace_id, reason="expired")
                if rotated is None:
                    break
                if (self._token_expiry(rotated) or 0) > time.time():
                    return rotated
            logger.error(
                "All configured chainlens service tokens appear expired; continuing with current token"
            )
            return None
        if exp - time.time() < _ROTATION_THRESHOLD_SECONDS:
            return self.rotate(workspace_id=workspace_id, reason="preemptive")
        return None

    def _sign_user_context(self) -> str | None:
        """Sign a ChainLens-compatible ``x-user-ctx`` HMAC header.

        Payload format mirrors ``packages/shared/src/auth/hmac.ts``:
        ``userId|exp|base64url-hmac``, 30s TTL, SHA256.
        """
        if not self._hmac_secret:
            return None
        if "|" in self._hmac_user_id:
            logger.warning(
                "CHAINLENS_HMAC_USER_ID contains '|'; cannot sign x-user-ctx"
            )
            return None
        exp = int((time.time() * 1000) + _USER_CTX_TTL_MS)
        payload = f"{self._hmac_user_id}|{exp}"
        sig = hmac.new(
            self._hmac_secret.encode("utf-8"),
            payload.encode("utf-8"),
            hashlib.sha256,
        ).digest()
        b64_sig = base64.urlsafe_b64encode(sig).rstrip(b"=").decode("ascii")
        return f"{payload}|{b64_sig}"

    def get_outbound_headers(
        self,
        workspace_id: int,
        *,
        correlation_id: str | None = None,
        content_type: str | None = None,
    ) -> dict[str, str]:
        """Return headers for outbound chainlens-research requests.

        The bearer token comes from ``current_token`` when tokens are configured.
        When ``CHAINLENS_AUTH_CONTEXT_SECRET`` is set, a signed ``x-user-ctx``
        HMAC header is also attached so the ChainLens HmacAuthGuard can identify
        the request. ``X-Correlation-Id`` is generated if not supplied.
        """
        self.rotate_if_expiring(workspace_id=workspace_id)

        headers: dict[str, str] = {
            "X-Workspace-Id": str(workspace_id),
        }

        if self._tokens:
            token = self.current_token
            headers["Authorization"] = f"{_AUTHORIZATION_BEARER_PREFIX}{token}"

        user_ctx = self._sign_user_context()
        if user_ctx:
            headers[_USER_CTX_HEADER] = user_ctx

        headers["X-Correlation-Id"] = (
            correlation_id if correlation_id else str(uuid.uuid4())
        )
        if content_type:
            headers["Content-Type"] = content_type
        return headers

    def validate_inbound_token(self, request: Request) -> ChainLensAuthContext:
        """Validate an inbound request from chainlens-research.

        Checks ``Authorization: Bearer <token>`` against the configured token
        pool and extracts ``X-Workspace-Id`` / ``X-Correlation-Id``. Raises
        ``HTTPException(401)`` on missing/invalid token.
        """
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.lower().startswith(_AUTHORIZATION_BEARER_PREFIX.lower()):
            logger.warning(
                "ChainLens inbound auth failed: missing or malformed Authorization header"
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Unauthorized",
            )
        token = auth_header[len(_AUTHORIZATION_BEARER_PREFIX) :].strip()
        if token not in self._tokens:
            logger.warning(
                "ChainLens inbound auth failed: token not in configured pool"
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Unauthorized",
            )

        workspace_id_str = request.headers.get("X-Workspace-Id", "")
        if not workspace_id_str:
            logger.warning(
                "ChainLens inbound auth failed: missing X-Workspace-Id header"
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Unauthorized",
            )
        try:
            workspace_id = int(workspace_id_str)
            if workspace_id <= 0:
                raise ValueError("workspace_id must be positive")
        except ValueError as exc:
            logger.warning(
                "ChainLens inbound auth failed: invalid X-Workspace-Id %r",
                workspace_id_str,
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Unauthorized",
            ) from exc

        correlation_id = request.headers.get("X-Correlation-Id")
        logger.info(
            "ChainLens inbound auth accepted (workspace_id=%d, correlation_id=%s)",
            workspace_id,
            correlation_id,
        )
        return ChainLensAuthContext(
            workspace_id=workspace_id,
            correlation_id=correlation_id,
            token=token,
        )

    @classmethod
    def cost_dollars_to_micros(cls, cost_dollars: float) -> int:
        """Convert USD to micro-USD with half-up rounding.

        Matches the conversion used in ``chainlens.research.executor``.
        """
        from decimal import ROUND_HALF_UP, Decimal

        if not math.isfinite(cost_dollars):
            raise ValueError("cost_dollars must be a finite number")
        if cost_dollars < 0:
            raise ValueError("cost_dollars must be non-negative")
        if cost_dollars > _MAX_REASONABLE_COST_DOLLARS:
            raise ValueError(
                f"cost_dollars {cost_dollars} exceeds maximum reasonable value"
            )

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
    """Return an auth header dict for backwards compatibility.

    Does not include workspace/correlation headers; prefer
    ``ChainLensServiceAuth.get_outbound_headers``.
    """
    auth = get_chainlens_auth()
    if not auth.configured:
        return {}
    # Back-compat: no workspace id available, so use 0 as placeholder.
    # Workspace 0 is not generated by auto-increment; treat it as a sentinel.
    headers = auth.get_outbound_headers(workspace_id=0, correlation_id=None)
    out: dict[str, str] = {}
    if "Authorization" in headers:
        out["Authorization"] = headers["Authorization"]
    if _USER_CTX_HEADER in headers:
        out[_USER_CTX_HEADER] = headers[_USER_CTX_HEADER]
    return out
