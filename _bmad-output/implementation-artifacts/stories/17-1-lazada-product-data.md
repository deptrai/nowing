---
story_key: 17-1-lazada-product-data
status: done
epic: 17
---

# Story 17.1: Lazada Product Data

**Status:** `done`  
**Epic:** Epic 17 — E-commerce Intelligence

## Story

As a product researcher,  
I want product data from Lazada Vietnam including price, seller, ratings, and variants,  
so that I can perform pricing analysis and competitor tracking.

## Acceptance Criteria

- **Given** the `XActions` `x_lazada_search` / `x_lazada_product` MCP tool is available and returns product data, **When** a user searches by product keyword, **Then** product listings are returned with: title, price, original price, discount, rating, review count, seller name, variants.
- **Given** product data is fetched from XActions, **When** normalized to `Chunk[]`, **Then** `metadata.source: 'xactions_adapter'`, `sourceId` (stable: normalized `title` + `seller_id` + `sku` if available), `domain: 'lazada.vn'`, `fetchedAt`, `contentType: 'product'` are set.
- **Given** the XActions tool returns anti-bot/captcha, **When** the adapter handles it, **Then** it propagates `degraded=true` with `degradation_reason: ANTI_BOT`; no in-house Playwright crawler is built inside Nowing.
- **Given** a `Chunk[]` batch, **When** `NowingIngestService.ingest()` is called, **Then** it calls `POST /v1/ingest/scraper` and returns `ingestJobId`.

## Dev Notes

- Raw Lazada scraping and anti-bot proxy rotation are delegated to XActions MCP tools (`x_lazada_search`, `x_lazada_product`) per AD-SOC-1 / AD-SOC-9.
- Nowing focus: `LazadaLeadAdapter`, schema normalization into `ecommerce_products`, Confidence Gate verification, and `chainlens-research` ingestion.
- `LazadaLeadAdapter` currently shares module space with `app/lead_intelligence/adapters/ecommerce.py`; separate `lazada.py` is a fast-follow.

## Verification

- Adapter: `app/lead_intelligence/adapters/ecommerce.py` / `lazada.py` (planned)
- Schema: `app/proprietary/platforms/shopee/models.py` reused for `ecommerce_products` / `ecommerce_price_history`
