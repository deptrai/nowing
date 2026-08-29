"""Config domain: scraper."""

from __future__ import annotations

import os

# Platform-native scraper billing (Reddit, Google Search, Google Maps,
# YouTube). Debits the credit wallet per *item returned* — the same
# per-unit model as web crawl, one meter per verb. Off by default so
# self-hosted / OSS installs keep scraping effectively-free; hosted
# deployments set this TRUE.
#
# Rates are fully config-driven (no hardcoded price). Each is micro-USD
# per item; retune with an env change + restart (no code/migration):
#   <KEY> = round(USD_per_1000_items * 1_000)
#   $3.50/1000 -> 3500 | $5.00/1000 -> 5000 | $2.00/1000 -> 2000
# Defaults include margin for proxy, compute, and storage costs while
# remaining independently adjustable for each platform.
PLATFORM_SCRAPE_BILLING_ENABLED = (
    os.getenv("PLATFORM_SCRAPE_BILLING_ENABLED", "FALSE").upper() == "TRUE"
)
REDDIT_SCRAPE_MICROS_PER_ITEM = int(
    os.getenv("REDDIT_SCRAPE_MICROS_PER_ITEM", "3500")
)
GOOGLE_SEARCH_MICROS_PER_SERP = int(
    os.getenv("GOOGLE_SEARCH_MICROS_PER_SERP", "5500")
)
GOOGLE_MAPS_MICROS_PER_PLACE = int(
    os.getenv("GOOGLE_MAPS_MICROS_PER_PLACE", "3500")
)
GOOGLE_MAPS_MICROS_PER_REVIEW = int(
    os.getenv("GOOGLE_MAPS_MICROS_PER_REVIEW", "1500")
)
AMAZON_MICROS_PER_PRODUCT = int(os.getenv("AMAZON_MICROS_PER_PRODUCT", "3500"))
YOUTUBE_MICROS_PER_VIDEO = int(os.getenv("YOUTUBE_MICROS_PER_VIDEO", "2500"))
# Kept separate from the video rate so comments can be re-tuned toward the
# cheaper per-comment market ($0.40-2.00/1k) without touching video pricing.
YOUTUBE_MICROS_PER_COMMENT = int(os.getenv("YOUTUBE_MICROS_PER_COMMENT", "1500"))
INSTAGRAM_SCRAPE_MICROS_PER_ITEM = int(
    os.getenv("INSTAGRAM_SCRAPE_MICROS_PER_ITEM", "3500")
)
# Kept separate from the item rate so comments can be re-tuned toward the
# cheaper per-comment market without touching post/reel pricing.
INSTAGRAM_SCRAPE_MICROS_PER_COMMENT = int(
    os.getenv("INSTAGRAM_SCRAPE_MICROS_PER_COMMENT", "1500")
)
# Mobile API listings are cheap and stable, priced near Reddit/Instagram.
BATDONGSAN_SCRAPE_MICROS_PER_ITEM = int(
    os.getenv("BATDONGSAN_SCRAPE_MICROS_PER_ITEM", "3500")
)
# Pacing: seconds between page requests while paginating, and the base of
# the exponential backoff (base * 2**attempt) between retries. Politeness
# keeps the mobile endpoint from rate-limiting us.
BATDONGSAN_PAGE_DELAY_S = float(os.getenv("BATDONGSAN_PAGE_DELAY_S", "0.5"))
BATDONGSAN_RETRY_BACKOFF_BASE_S = float(
    os.getenv("BATDONGSAN_RETRY_BACKOFF_BASE_S", "0.5")
)
# Phone-reveal rate limits per account.  These are conservative defaults
# for batdongsan.com.vn; tune them once you have measured the real threshold.
BATDONGSAN_PHONE_RPM = float(os.getenv("BATDONGSAN_PHONE_RPM", "5.0"))
BATDONGSAN_PHONE_BURST = int(os.getenv("BATDONGSAN_PHONE_BURST", "2"))
BATDONGSAN_PHONE_COOLDOWN_S = float(
    os.getenv("BATDONGSAN_PHONE_COOLDOWN_S", "300.0")
)
BATDONGSAN_PHONE_MAX_CONSECUTIVE_FAILURES = int(
    os.getenv("BATDONGSAN_PHONE_MAX_CONSECUTIVE_FAILURES", "3")
)
# Chợ Tốt Nhà uses a public JSON gateway, similar cost to Batdongsan.
CHOTOT_BDS_SCRAPE_MICROS_PER_ITEM = int(
    os.getenv("CHOTOT_BDS_SCRAPE_MICROS_PER_ITEM", "3500")
)
CHOTOT_SCRAPE_MICROS_PER_ITEM = int(
    os.getenv("CHOTOT_SCRAPE_MICROS_PER_ITEM", "3500")
)
CHOTOT_BDS_PAGE_DELAY_S = float(os.getenv("CHOTOT_BDS_PAGE_DELAY_S", "0.5"))
CHOTOT_BDS_RETRY_BACKOFF_BASE_S = float(
    os.getenv("CHOTOT_BDS_RETRY_BACKOFF_BASE_S", "0.5")
)
CHOTOT_BDS_TIMEOUT_S = float(os.getenv("CHOTOT_BDS_TIMEOUT_S", "30.0"))
CHOTOT_BDS_USER_AGENT = os.getenv("CHOTOT_BDS_USER_AGENT", "")
# Muaban.net requires a headless browser to pass Cloudflare, so the per-item
# rate sits above the API-backed Batdongsan/Chotot rates.
MUABAN_BDS_SCRAPE_MICROS_PER_ITEM = int(
    os.getenv("MUABAN_BDS_SCRAPE_MICROS_PER_ITEM", "5500")
)
MUABAN_BDS_PAGE_DELAY_S = float(os.getenv("MUABAN_BDS_PAGE_DELAY_S", "1.0"))
MUABAN_BDS_RETRY_BACKOFF_BASE_S = float(
    os.getenv("MUABAN_BDS_RETRY_BACKOFF_BASE_S", "1.0")
)
# Multi-source BĐS aggregation charges a flat query fee on top of the
# underlying scraper item costs. This covers normalize/dedupe/conflict work.
VN_BDS_AGGREGATE_QUERY_MICROS_PER_QUERY = int(
    os.getenv("VN_BDS_AGGREGATE_QUERY_MICROS_PER_QUERY", "5000")
)
# VietnamWorks is a public API-backed source; price near other API platforms.
VIETNAMWORKS_SCRAPE_MICROS_PER_ITEM = int(
    os.getenv("VIETNAMWORKS_SCRAPE_MICROS_PER_ITEM", "3000")
)
VIETNAMWORKS_PAGE_DELAY_S = float(os.getenv("VIETNAMWORKS_PAGE_DELAY_S", "0.5"))
VIETNAMWORKS_TIMEOUT_S = float(os.getenv("VIETNAMWORKS_TIMEOUT_S", "30.0"))
VIETNAMWORKS_MAX_PAGES = int(os.getenv("VIETNAMWORKS_MAX_PAGES", "5"))
VIETNAMWORKS_MAX_ITEMS = int(os.getenv("VIETNAMWORKS_MAX_ITEMS", "100"))
VIETNAMWORKS_RETRY_ATTEMPTS = int(os.getenv("VIETNAMWORKS_RETRY_ATTEMPTS", "2"))
VIETNAMWORKS_RETRY_BACKOFF_BASE_S = float(
    os.getenv("VIETNAMWORKS_RETRY_BACKOFF_BASE_S", "0.5")
)
VIETNAMWORKS_USER_AGENT = os.getenv(
    "VIETNAMWORKS_USER_AGENT",
    (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/126.0.0.0 Safari/537.36"
    ),
)
TOPCV_USER_AGENT = os.getenv(
    "TOPCV_USER_AGENT",
    (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/126.0.0.0 Safari/537.36"
    ),
)
# TopCV is Cloudflare-protected and uses the web crawler stack. The platform
# per-item rate is a pass-through; actual anti-bot cost is metered via
# WEB_CRAWL + WEB_CRAWL_CAPTCHA_MICROS_PER_SOLVE (see AD-23).
TOPCV_ENABLED = os.getenv("TOPCV_ENABLED", "TRUE").upper() == "TRUE"
TOPCV_SCRAPE_MICROS_PER_ITEM = int(
    os.getenv("TOPCV_SCRAPE_MICROS_PER_ITEM", "5500")
)
TOPCV_PAGE_DELAY_S = float(os.getenv("TOPCV_PAGE_DELAY_S", "1.0"))
TOPCV_TIMEOUT_S = float(os.getenv("TOPCV_TIMEOUT_S", "60.0"))
TOPCV_MAX_PAGES = int(os.getenv("TOPCV_MAX_PAGES", "3"))
TOPCV_RETRY_ATTEMPTS = int(os.getenv("TOPCV_RETRY_ATTEMPTS", "2"))
TOPCV_RETRY_BACKOFF_BASE_S = float(os.getenv("TOPCV_RETRY_BACKOFF_BASE_S", "2.0"))
TOPCV_CIRCUIT_BREAKER_THRESHOLD = int(
    os.getenv("TOPCV_CIRCUIT_BREAKER_THRESHOLD", "3")
)
TOPCV_CIRCUIT_BREAKER_TIMEOUT_S = float(
    os.getenv("TOPCV_CIRCUIT_BREAKER_TIMEOUT_S", "60.0")
)
# ITviec is server-rendered HTML; cheaper than TopCV, no anti-bot expected.
ITVIEC_SCRAPE_MICROS_PER_ITEM = int(
    os.getenv("ITVIEC_SCRAPE_MICROS_PER_ITEM", "3000")
)
ITVIEC_PAGE_DELAY_S = float(os.getenv("ITVIEC_PAGE_DELAY_S", "0.5"))
ITVIEC_TIMEOUT_S = float(os.getenv("ITVIEC_TIMEOUT_S", "30.0"))
ITVIEC_MAX_PAGES = int(os.getenv("ITVIEC_MAX_PAGES", "5"))
# Indeed is Cloudflare-protected and uses the browser/anti-bot stack.
INDEED_SCRAPE_MICROS_PER_ITEM = int(
    os.getenv("INDEED_SCRAPE_MICROS_PER_ITEM", "5000")
)
INDEED_PAGE_DELAY_S = float(os.getenv("INDEED_PAGE_DELAY_S", "1.0"))
INDEED_MAX_PAGES = int(os.getenv("INDEED_MAX_PAGES", "5"))
INDEED_MAX_ITEMS = int(os.getenv("INDEED_MAX_ITEMS", "50"))
# Walmart is a Next.js storefront; data is primarily in __NEXT_DATA__ JSON.
WALMART_SCRAPE_MICROS_PER_ITEM = int(
    os.getenv("WALMART_SCRAPE_MICROS_PER_ITEM", "5000")
)
WALMART_REVIEW_MICROS_PER_ITEM = int(
    os.getenv("WALMART_REVIEW_MICROS_PER_ITEM", "500")
)
ECOMMERCE_PRODUCT_MICROS_PER_ITEM = int(
    os.getenv("ECOMMERCE_PRODUCT_MICROS_PER_ITEM", "5000")
)
WALMART_PAGE_DELAY_S = float(os.getenv("WALMART_PAGE_DELAY_S", "1.0"))
WALMART_MAX_ITEMS = int(os.getenv("WALMART_MAX_ITEMS", "50"))
WALMART_MAX_REVIEWS = int(os.getenv("WALMART_MAX_REVIEWS", "100"))
# CafeF unofficial API. Demo mode uses stable synthetic data so the
# capability works in tests and demos without relying on undocumented
# public quote/news endpoints. Set CAFEF_DEMO_MODE=false and supply live
# URLs to hit the real CafeF APIs.
CAFEF_DATA_MICROS_PER_ITEM = int(os.getenv("CAFEF_DATA_MICROS_PER_ITEM", "5000"))
CAFEF_RATE_LIMIT_RPS = float(os.getenv("CAFEF_RATE_LIMIT_RPS", str(20 / 60)))
CAFEF_TIMEOUT_S = float(os.getenv("CAFEF_TIMEOUT_S", "15.0"))
CAFEF_DEMO_MODE = os.getenv("CAFEF_DEMO_MODE", "TRUE").upper() == "TRUE"
CAFEF_QUOTE_URL = os.getenv("CAFEF_QUOTE_URL", "")
CAFEF_NEWS_URL = os.getenv("CAFEF_NEWS_URL", "")
CAFEF_FINANCIAL_BASE_URL = os.getenv("CAFEF_FINANCIAL_BASE_URL", "")
# Vietstock unofficial API. Demo mode uses stable synthetic data so the
# capability works in tests and demos without real credentials.
VIETSTOCK_DATA_MICROS_PER_ITEM = int(
    os.getenv("VIETSTOCK_DATA_MICROS_PER_ITEM", "5000")
)
VIETSTOCK_RATE_LIMIT_RPS = float(
    os.getenv("VIETSTOCK_RATE_LIMIT_RPS", str(20 / 60))
)
VIETSTOCK_TIMEOUT_S = float(os.getenv("VIETSTOCK_TIMEOUT_S", "15.0"))
VIETSTOCK_DEMO_MODE = os.getenv("VIETSTOCK_DEMO_MODE", "TRUE").upper() == "TRUE"
VIETSTOCK_QUOTE_URL = os.getenv("VIETSTOCK_QUOTE_URL", "")
VIETSTOCK_FINANCIAL_URL = os.getenv("VIETSTOCK_FINANCIAL_URL", "")
VIETSTOCK_SESSION_COOKIE = os.getenv("VIETSTOCK_SESSION_COOKIE", "")
# masothue.com company directory. Cloudflare-protected; use polite pacing.
MASOTHUE_SCRAPE_MICROS_PER_ITEM = int(
    os.getenv("MASOTHUE_SCRAPE_MICROS_PER_ITEM", "3000")
)
MASOTHUE_PAGE_DELAY_S = float(os.getenv("MASOTHUE_PAGE_DELAY_S", "1.0"))
MASOTHUE_TIMEOUT_S = float(os.getenv("MASOTHUE_TIMEOUT_S", "30.0"))
MASOTHUE_MAX_PAGES = int(os.getenv("MASOTHUE_MAX_PAGES", "5"))
MASOTHUE_MAX_ITEMS = int(os.getenv("MASOTHUE_MAX_ITEMS", "50"))
# Multi-source job aggregation (VietnamWorks/TopCV/ITviec).
VN_JOBS_AGGREGATE_QUERY_MICROS_PER_QUERY = int(
    os.getenv("VN_JOBS_AGGREGATE_QUERY_MICROS_PER_QUERY", "5000")
)
VN_JOBS_AGGREGATE_MAX_ITEMS_PER_SOURCE = int(
    os.getenv("VN_JOBS_AGGREGATE_MAX_ITEMS_PER_SOURCE", "50")
)
VN_JOBS_AGGREGATE_MAX_PAGES = int(os.getenv("VN_JOBS_AGGREGATE_MAX_PAGES", "5"))
# PII redaction confidence threshold (0-1) before treating a source as unsafe
# for memory extraction.
PII_REDACTION_MIN_CONFIDENCE = float(
    os.getenv("PII_REDACTION_MIN_CONFIDENCE", "0.7")
)
# Browser-driven listings make TikTok heavier per item than the API-backed
# video meter, so it sits a touch above YouTube's video rate.
TIKTOK_MICROS_PER_VIDEO = int(os.getenv("TIKTOK_MICROS_PER_VIDEO", "3500"))
# User search returns lighter account records (name/followers/bio), priced
# below the video meter to mirror the cheaper account-discovery market.
TIKTOK_MICROS_PER_USER = int(os.getenv("TIKTOK_MICROS_PER_USER", "2500"))
# Comments are the cheapest per-item TikTok data, matching the per-comment
# market (and YouTube's comment meter).
TIKTOK_MICROS_PER_COMMENT = int(os.getenv("TIKTOK_MICROS_PER_COMMENT", "1500"))
# Retry an empty listing draw on a fresh rotating IP. Set to 1 for a static
# proxy, where every retry re-hits the same exit.
TIKTOK_LISTING_MAX_ATTEMPTS = int(os.getenv("TIKTOK_LISTING_MAX_ATTEMPTS", "3"))



__all__ = ['AMAZON_MICROS_PER_PRODUCT', 'BATDONGSAN_PAGE_DELAY_S', 'BATDONGSAN_PHONE_BURST', 'BATDONGSAN_PHONE_COOLDOWN_S', 'BATDONGSAN_PHONE_MAX_CONSECUTIVE_FAILURES', 'BATDONGSAN_PHONE_RPM', 'BATDONGSAN_RETRY_BACKOFF_BASE_S', 'BATDONGSAN_SCRAPE_MICROS_PER_ITEM', 'CAFEF_DATA_MICROS_PER_ITEM', 'CAFEF_DEMO_MODE', 'CAFEF_FINANCIAL_BASE_URL', 'CAFEF_NEWS_URL', 'CAFEF_QUOTE_URL', 'CAFEF_RATE_LIMIT_RPS', 'CAFEF_TIMEOUT_S', 'CHOTOT_BDS_PAGE_DELAY_S', 'CHOTOT_BDS_RETRY_BACKOFF_BASE_S', 'CHOTOT_BDS_SCRAPE_MICROS_PER_ITEM', 'CHOTOT_BDS_TIMEOUT_S', 'CHOTOT_BDS_USER_AGENT', 'CHOTOT_SCRAPE_MICROS_PER_ITEM', 'ECOMMERCE_PRODUCT_MICROS_PER_ITEM', 'GOOGLE_MAPS_MICROS_PER_PLACE', 'GOOGLE_MAPS_MICROS_PER_REVIEW', 'GOOGLE_SEARCH_MICROS_PER_SERP', 'INDEED_MAX_ITEMS', 'INDEED_MAX_PAGES', 'INDEED_PAGE_DELAY_S', 'INDEED_SCRAPE_MICROS_PER_ITEM', 'INSTAGRAM_SCRAPE_MICROS_PER_COMMENT', 'INSTAGRAM_SCRAPE_MICROS_PER_ITEM', 'ITVIEC_MAX_PAGES', 'ITVIEC_PAGE_DELAY_S', 'ITVIEC_SCRAPE_MICROS_PER_ITEM', 'ITVIEC_TIMEOUT_S', 'MASOTHUE_MAX_ITEMS', 'MASOTHUE_MAX_PAGES', 'MASOTHUE_PAGE_DELAY_S', 'MASOTHUE_SCRAPE_MICROS_PER_ITEM', 'MASOTHUE_TIMEOUT_S', 'MUABAN_BDS_PAGE_DELAY_S', 'MUABAN_BDS_RETRY_BACKOFF_BASE_S', 'MUABAN_BDS_SCRAPE_MICROS_PER_ITEM', 'PII_REDACTION_MIN_CONFIDENCE', 'PLATFORM_SCRAPE_BILLING_ENABLED', 'REDDIT_SCRAPE_MICROS_PER_ITEM', 'TIKTOK_LISTING_MAX_ATTEMPTS', 'TIKTOK_MICROS_PER_COMMENT', 'TIKTOK_MICROS_PER_USER', 'TIKTOK_MICROS_PER_VIDEO', 'TOPCV_CIRCUIT_BREAKER_THRESHOLD', 'TOPCV_CIRCUIT_BREAKER_TIMEOUT_S', 'TOPCV_ENABLED', 'TOPCV_MAX_PAGES', 'TOPCV_PAGE_DELAY_S', 'TOPCV_RETRY_ATTEMPTS', 'TOPCV_RETRY_BACKOFF_BASE_S', 'TOPCV_SCRAPE_MICROS_PER_ITEM', 'TOPCV_TIMEOUT_S', 'TOPCV_USER_AGENT', 'VIETNAMWORKS_MAX_ITEMS', 'VIETNAMWORKS_MAX_PAGES', 'VIETNAMWORKS_PAGE_DELAY_S', 'VIETNAMWORKS_RETRY_ATTEMPTS', 'VIETNAMWORKS_RETRY_BACKOFF_BASE_S', 'VIETNAMWORKS_SCRAPE_MICROS_PER_ITEM', 'VIETNAMWORKS_TIMEOUT_S', 'VIETNAMWORKS_USER_AGENT', 'VIETSTOCK_DATA_MICROS_PER_ITEM', 'VIETSTOCK_DEMO_MODE', 'VIETSTOCK_FINANCIAL_URL', 'VIETSTOCK_QUOTE_URL', 'VIETSTOCK_RATE_LIMIT_RPS', 'VIETSTOCK_SESSION_COOKIE', 'VIETSTOCK_TIMEOUT_S', 'VN_BDS_AGGREGATE_QUERY_MICROS_PER_QUERY', 'VN_JOBS_AGGREGATE_MAX_ITEMS_PER_SOURCE', 'VN_JOBS_AGGREGATE_MAX_PAGES', 'VN_JOBS_AGGREGATE_QUERY_MICROS_PER_QUERY', 'WALMART_MAX_ITEMS', 'WALMART_MAX_REVIEWS', 'WALMART_PAGE_DELAY_S', 'WALMART_REVIEW_MICROS_PER_ITEM', 'WALMART_SCRAPE_MICROS_PER_ITEM', 'YOUTUBE_MICROS_PER_COMMENT', 'YOUTUBE_MICROS_PER_VIDEO']
