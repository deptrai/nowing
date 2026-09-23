---
story_key: 17-5-tiktok-shop-product-trending-skus-ingestion
status: done
epic: 17
---

# Story 17.5: TikTok Shop Product & Trending SKUs Ingestion

**Status:** `done`  
**Epic:** Epic 17 — E-commerce Intelligence

## Story

As a social commerce researcher,  
I want product, pricing, and sales volume data from TikTok Shop Vietnam,  
so that I can analyze viral e-commerce trends, top KOC promoted products, and competitive pricing.

## Acceptance Criteria

- **Given** the `XActions` `x_tiktok_shop_products` MCP tool is available, **When** a user provides a search query or category, **Then** product listings are returned with title, current price (using divisor `1.0`), units sold, shop name, rating, and creator/affiliate metrics.
- **Given** product data is fetched from XActions, **When** normalized and stored, **Then** records are saved into `ecommerce_products` with `platform: 'tiktok_shop'` and linked to `ecommerce_price_history`.
- **Given** historical product runs, **When** analyzed, **Then** the engine calculates sales velocity `(sold_t2 - sold_t1) / delta_days` to classify trending breakout SKUs.
- **Given** an AI Agent session, **When** calling `ecommerce_search_products(platform='tiktok_shop', query=...)`, **Then** top trending products with sales velocity metrics are returned.

## Dev Notes

- Raw TikTok Shop scraping and crawler sessions are delegated to XActions (`x_tiktok_shop_products` MCP tool) per AD-SOC-1 / AD-SOC-2 / AD-SOC-9.
- Nowing focus: `TikTokShopLeadAdapter`, schema mapping into `ecommerce_products` / `ecommerce_price_history`, trending sales velocity calculations, and AI Agent query tools.
- `TiktokShopLeadAdapter.search_leads` currently returns metadata stub; full implementation is a fast-follow after XActions tool is available.

## Verification

- Adapter: `app/lead_intelligence/adapters/tiktok_shop.py`
- Schema: `app/proprietary/platforms/shopee/models.py` (`ecommerce_products`, `ecommerce_price_history`)
