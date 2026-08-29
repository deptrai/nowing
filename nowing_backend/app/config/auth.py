"""Config domain: auth."""

from __future__ import annotations

import os

# Cloudflare Turnstile CAPTCHA
TURNSTILE_ENABLED = os.getenv("TURNSTILE_ENABLED", "FALSE").upper() == "TRUE"
TURNSTILE_SECRET_KEY = os.getenv("TURNSTILE_SECRET_KEY", "")

# Auth
AUTH_TYPE = os.getenv("AUTH_TYPE", "LOCAL")
REGISTRATION_ENABLED = os.getenv("REGISTRATION_ENABLED", "TRUE").upper() == "TRUE"

# OAuth JWT
SECRET_KEY = os.getenv("SECRET_KEY")

# JWT Token Lifetimes
ACCESS_TOKEN_LIFETIME_SECONDS = int(
    os.getenv("ACCESS_TOKEN_LIFETIME_SECONDS", str(60 * 60))  # 60 minutes
)
MIN_ISSUED_AT = int(os.getenv("MIN_ISSUED_AT", "0"))
REFRESH_TOKEN_LIFETIME_SECONDS = int(
    os.getenv("REFRESH_TOKEN_LIFETIME_SECONDS", str(14 * 24 * 60 * 60))  # 2 weeks
)
REFRESH_ROTATION_GRACE_SECONDS = int(
    os.getenv("REFRESH_ROTATION_GRACE_SECONDS", "45")
)
REFRESH_ABSOLUTE_LIFETIME_SECONDS = int(
    os.getenv("REFRESH_ABSOLUTE_LIFETIME_SECONDS", str(30 * 24 * 60 * 60))
)
if REFRESH_ABSOLUTE_LIFETIME_SECONDS <= REFRESH_TOKEN_LIFETIME_SECONDS:
    raise ValueError(
        "REFRESH_ABSOLUTE_LIFETIME_SECONDS must be greater than "
        "REFRESH_TOKEN_LIFETIME_SECONDS so the sliding inactivity window works."
    )
SESSION_COOKIE_NAME = os.getenv("SESSION_COOKIE_NAME", "nowing_session")
REFRESH_COOKIE_NAME = os.getenv("REFRESH_COOKIE_NAME", "nowing_refresh")
SESSION_COOKIE_SECURE_POLICY = os.getenv(
    "SESSION_COOKIE_SECURE_POLICY", "auto"
).lower()
SESSION_COOKIE_SAMESITE = os.getenv("SESSION_COOKIE_SAMESITE", "lax").lower()
if SESSION_COOKIE_SAMESITE == "none":
    raise ValueError("SESSION_COOKIE_SAMESITE=none is not supported")
COOKIE_DOMAIN = os.getenv("COOKIE_DOMAIN") or None
CSRF_ALLOWED_ORIGINS = [
    origin.strip()
    for origin in os.getenv("CSRF_ALLOWED_ORIGINS", "").split(",")
    if origin.strip()
]
_CSRF_ALLOW_LOOPBACK = os.getenv("CSRF_ALLOW_LOOPBACK", "").strip().lower()
CSRF_ALLOW_LOOPBACK = _CSRF_ALLOW_LOOPBACK in {"1", "true", "yes"}
_PAT_MAX_EXPIRY_DAYS = os.getenv("PAT_MAX_EXPIRY_DAYS", "").strip()
PAT_MAX_EXPIRY_DAYS = int(_PAT_MAX_EXPIRY_DAYS) if _PAT_MAX_EXPIRY_DAYS else None

# Cloudflare Turnstile is already handled free in-framework (03a), NOT here.
# One app-wide config (mirrors the single PROXY_PROVIDER model) — no
# per-connector config. Off by default => zero solve attempts, zero cost.
# Solving may violate a target site's ToS; treat as opt-in/owner-acknowledged
# and public-data only (no logged-in bypass).
# =====================================================================
CAPTCHA_SOLVING_ENABLED = (
    os.getenv("CAPTCHA_SOLVING_ENABLED", "FALSE").upper() == "TRUE"
)
# Solver vendor. "capsolver" (AI-native, fastest on reCAPTCHA-Enterprise) and
# "2captcha" have in-house clients today; anticaptcha / capmonster are added
# progressively in solvers._PROVIDERS.
CAPTCHA_SOLVER_PROVIDER = os.getenv("CAPTCHA_SOLVER_PROVIDER", "capsolver")
CAPTCHA_SOLVER_API_KEY = os.getenv("CAPTCHA_SOLVER_API_KEY")
# Per-URL solve cap so one hostile page can't burn unbounded solver credit.
CAPTCHA_MAX_ATTEMPTS_PER_URL = int(os.getenv("CAPTCHA_MAX_ATTEMPTS_PER_URL", "1"))
# Abort a single solve after this many seconds (solves take 10-60s).
CAPTCHA_SOLVE_TIMEOUT_S = int(os.getenv("CAPTCHA_SOLVE_TIMEOUT_S", "120"))
# Default captcha type when detection is ambiguous: v2 | v3 | hcaptcha.
CAPTCHA_TYPE_DEFAULT = os.getenv("CAPTCHA_TYPE_DEFAULT", "v2")
# reCAPTCHA v3 tuning (only used for v3 challenges).
CAPTCHA_V3_MIN_SCORE = float(os.getenv("CAPTCHA_V3_MIN_SCORE", "0.7"))
CAPTCHA_V3_ACTION = os.getenv("CAPTCHA_V3_ACTION", "verify")

# =====================================================================


__all__ = ['ACCESS_TOKEN_LIFETIME_SECONDS', 'AUTH_TYPE', 'CAPTCHA_MAX_ATTEMPTS_PER_URL', 'CAPTCHA_SOLVER_API_KEY', 'CAPTCHA_SOLVER_PROVIDER', 'CAPTCHA_SOLVE_TIMEOUT_S', 'CAPTCHA_SOLVING_ENABLED', 'CAPTCHA_TYPE_DEFAULT', 'CAPTCHA_V3_ACTION', 'CAPTCHA_V3_MIN_SCORE', 'COOKIE_DOMAIN', 'CSRF_ALLOWED_ORIGINS', 'CSRF_ALLOW_LOOPBACK', 'MIN_ISSUED_AT', 'PAT_MAX_EXPIRY_DAYS', 'REFRESH_ABSOLUTE_LIFETIME_SECONDS', 'REFRESH_COOKIE_NAME', 'REFRESH_ROTATION_GRACE_SECONDS', 'REFRESH_TOKEN_LIFETIME_SECONDS', 'REGISTRATION_ENABLED', 'SECRET_KEY', 'SESSION_COOKIE_NAME', 'SESSION_COOKIE_SAMESITE', 'SESSION_COOKIE_SECURE_POLICY', 'TURNSTILE_ENABLED', 'TURNSTILE_SECRET_KEY', '_CSRF_ALLOW_LOOPBACK', '_PAT_MAX_EXPIRY_DAYS']
