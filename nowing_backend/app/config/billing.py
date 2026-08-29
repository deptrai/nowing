"""Config domain: billing."""

from __future__ import annotations

import os

from app.config._helpers import (
    logger,
)

# Stripe checkout (shared secrets for the unified credit wallet)
STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY")
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET")
STRIPE_RECONCILIATION_LOOKBACK_MINUTES = int(
    os.getenv("STRIPE_RECONCILIATION_LOOKBACK_MINUTES", "10")
)
STRIPE_RECONCILIATION_BATCH_SIZE = int(
    os.getenv("STRIPE_RECONCILIATION_BATCH_SIZE", "100")
)

# Unified credit wallet (micro-USD) settings.
#
# Storage unit is integer micro-USD (1_000_000 = $1.00). A single
# ``credit_micros_balance`` funds both ETL page processing and premium
# model calls. New users start with ``DEFAULT_CREDIT_MICROS_BALANCE``
# ($5 by default).
#
# Legacy env names (``PREMIUM_CREDIT_MICROS_LIMIT`` / ``PREMIUM_TOKEN_LIMIT``,
# ``STRIPE_PREMIUM_TOKEN_PRICE_ID``, ``STRIPE_CREDIT_MICROS_PER_UNIT`` /
# ``STRIPE_TOKENS_PER_UNIT``, ``STRIPE_TOKEN_BUYING_ENABLED``) are still
# honoured as fall-backs for one release; deprecation warnings fire below.
DEFAULT_CREDIT_MICROS_BALANCE = int(
    os.getenv("DEFAULT_CREDIT_MICROS_BALANCE")
    or os.getenv("PREMIUM_CREDIT_MICROS_LIMIT")
    or os.getenv("PREMIUM_TOKEN_LIMIT", "5000000")
)
STRIPE_CREDIT_PRICE_ID = os.getenv("STRIPE_CREDIT_PRICE_ID") or os.getenv(
    "STRIPE_PREMIUM_TOKEN_PRICE_ID"
)
STRIPE_CREDIT_MICROS_PER_UNIT = int(
    os.getenv("STRIPE_CREDIT_MICROS_PER_UNIT")
    or os.getenv("STRIPE_TOKENS_PER_UNIT", "1000000")
)
STRIPE_CREDIT_BUYING_ENABLED = (
    os.getenv("STRIPE_CREDIT_BUYING_ENABLED")
    or os.getenv("STRIPE_TOKEN_BUYING_ENABLED", "FALSE")
).upper() == "TRUE"

# ETL page processing debits the credit wallet only when enabled. Defaults
# to FALSE so self-hosted / OSS installs keep effectively-free ETL; hosted
# deployments set this TRUE. 1 page == ``MICROS_PER_PAGE`` micro-USD.
ETL_CREDIT_BILLING_ENABLED = (
    os.getenv("ETL_CREDIT_BILLING_ENABLED", "FALSE").upper() == "TRUE"
)
MICROS_PER_PAGE = int(os.getenv("MICROS_PER_PAGE", "1000"))

# Web-crawl billing debits the credit wallet per *successful* crawl request
# (CrawlOutcomeStatus.SUCCESS). Off by default so self-hosted / OSS installs
# keep crawling effectively-free; hosted deployments set this TRUE.
#
# The price is fully config-driven — there is no hardcoded rate anywhere.
# ``WEB_CRAWL_MICROS_PER_SUCCESS`` is the single source of truth; retune it
# to any rate with just an env change + restart (no code/migration):
#   WEB_CRAWL_MICROS_PER_SUCCESS = round(USD_per_1000_crawls * 1_000)
#   $2/1000 -> 2000 (default) | $1/1000 -> 1000 | $0.50/1000 -> 500
WEB_CRAWL_CREDIT_BILLING_ENABLED = (
    os.getenv("WEB_CRAWL_CREDIT_BILLING_ENABLED", "FALSE").upper() == "TRUE"
)
WEB_CRAWL_MICROS_PER_SUCCESS = int(
    os.getenv("WEB_CRAWL_MICROS_PER_SUCCESS", "2000")
)

# Phase 3d captcha-solve billing. Captcha can't ride the per-success crawl
# meter above: the solver charges per *attempt* regardless of whether the
# crawl ultimately succeeds, so solves are metered as a SEPARATE per-attempt
# unit (usage_type="web_crawl_captcha"). Off by default; independent of the
# crawl-billing flag. Price is config-driven (no hardcoded rate):
#   WEB_CRAWL_CAPTCHA_MICROS_PER_SOLVE = round(USD_per_1000_solves * 1_000)
#   $3/1000 -> 3000 (default) | $5/1000 -> 5000
# Set with margin over the solver vendor's per-attempt price.
WEB_CRAWL_CAPTCHA_BILLING_ENABLED = (
    os.getenv("WEB_CRAWL_CAPTCHA_BILLING_ENABLED", "FALSE").upper() == "TRUE"
)
WEB_CRAWL_CAPTCHA_MICROS_PER_SOLVE = int(
    os.getenv("WEB_CRAWL_CAPTCHA_MICROS_PER_SOLVE", "3000")
)

# Low-balance WARNING threshold (micro-USD). Surfaced by the quota service
# so the UI can nudge the user to top up / enable auto-reload. $0.50.
CREDIT_LOW_BALANCE_WARNING_MICROS = int(
    os.getenv("CREDIT_LOW_BALANCE_WARNING_MICROS", "500000")
)

# Auto-reload (off-session Stripe top-up) feature flag and guards.
AUTO_RELOAD_ENABLED = os.getenv("AUTO_RELOAD_ENABLED", "FALSE").upper() == "TRUE"
# Minimum configurable reload amount (micro-USD). $1.00 to match pack pricing.
AUTO_RELOAD_MIN_AMOUNT_MICROS = int(
    os.getenv("AUTO_RELOAD_MIN_AMOUNT_MICROS", "1000000")
)
# Cooldown so a burst of debits can't fire multiple charges (minutes).
AUTO_RELOAD_COOLDOWN_MINUTES = int(os.getenv("AUTO_RELOAD_COOLDOWN_MINUTES", "10"))

# Safety ceiling on the per-call premium reservation. ``stream_new_chat``
# estimates an upper-bound cost from ``litellm.get_model_info`` x the
# config's ``quota_reserve_tokens`` and clamps the result to this value
# so a misconfigured "$1000/M" model can't lock the user's whole balance
# on one call. Default $1.00 covers realistic worst-cases (Opus + 4K
# reserve_tokens ≈ $0.36) with headroom.
QUOTA_MAX_RESERVE_MICROS = int(os.getenv("QUOTA_MAX_RESERVE_MICROS", "1000000"))

if (
    os.getenv("PREMIUM_TOKEN_LIMIT") or os.getenv("PREMIUM_CREDIT_MICROS_LIMIT")
) and not os.getenv("DEFAULT_CREDIT_MICROS_BALANCE"):
    logger.warning("Warning: PREMIUM_TOKEN_LIMIT / PREMIUM_CREDIT_MICROS_LIMIT are "
        "deprecated; rename to DEFAULT_CREDIT_MICROS_BALANCE. The old keys "
        "will be removed in a future release.")
if os.getenv("STRIPE_TOKENS_PER_UNIT") and not os.getenv(
    "STRIPE_CREDIT_MICROS_PER_UNIT"
):
    logger.warning("Warning: STRIPE_TOKENS_PER_UNIT is deprecated; rename to "
        "STRIPE_CREDIT_MICROS_PER_UNIT (1:1 numerical mapping). "
        "The old key will be removed in a future release.")
if os.getenv("STRIPE_PREMIUM_TOKEN_PRICE_ID") and not os.getenv(
    "STRIPE_CREDIT_PRICE_ID"
):
    logger.warning("Warning: STRIPE_PREMIUM_TOKEN_PRICE_ID is deprecated; rename to "
        "STRIPE_CREDIT_PRICE_ID. The old key will be removed in a future "
        "release.")
if os.getenv("STRIPE_TOKEN_BUYING_ENABLED") and not os.getenv(
    "STRIPE_CREDIT_BUYING_ENABLED"
):
    logger.warning("Warning: STRIPE_TOKEN_BUYING_ENABLED is deprecated; rename to "
        "STRIPE_CREDIT_BUYING_ENABLED. The old key will be removed in a "
        "future release.")



__all__ = ['AUTO_RELOAD_COOLDOWN_MINUTES', 'AUTO_RELOAD_ENABLED', 'AUTO_RELOAD_MIN_AMOUNT_MICROS', 'CREDIT_LOW_BALANCE_WARNING_MICROS', 'DEFAULT_CREDIT_MICROS_BALANCE', 'ETL_CREDIT_BILLING_ENABLED', 'MICROS_PER_PAGE', 'QUOTA_MAX_RESERVE_MICROS', 'STRIPE_CREDIT_BUYING_ENABLED', 'STRIPE_CREDIT_MICROS_PER_UNIT', 'STRIPE_CREDIT_PRICE_ID', 'STRIPE_RECONCILIATION_BATCH_SIZE', 'STRIPE_RECONCILIATION_LOOKBACK_MINUTES', 'STRIPE_SECRET_KEY', 'STRIPE_WEBHOOK_SECRET', 'WEB_CRAWL_CAPTCHA_BILLING_ENABLED', 'WEB_CRAWL_CAPTCHA_MICROS_PER_SOLVE', 'WEB_CRAWL_CREDIT_BILLING_ENABLED', 'WEB_CRAWL_MICROS_PER_SUCCESS']
