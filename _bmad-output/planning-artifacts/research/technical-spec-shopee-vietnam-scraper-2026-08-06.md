# Technical Spec — Shopee Vietnam Scraper

**Date:** 2026-08-06
**Author:** Luis + AI research
**Status:** draft
**Platform:** Shopee Vietnam (shopee.vn)
**Approach:** Internal API (cookie-based, no official public API)

---

## 1. Executive Summary

Scrape Shopee Vietnam product data via reverse-engineered internal API. Cookie-based authentication, structured JSON responses, no HTML parsing required. Fastest path to e-commerce data for Nowing's canonical entity system.

---

## 2. API Endpoints

### 2.1 Search Products

```
GET https://shopee.vn/api/v4/search/search_items
```

| Param | Type | Required | Description |
|-------|------|----------|-------------|
| `by` | string | Yes | `relevancy` / `sales` / `ctime` |
| `keyword` | string | Yes | Search query (URL-encoded) |
| `limit` | int | No | Items per page (default 60, max 100) |
| `newest` | int | No | Offset (page * limit) |
| `order` | string | No | `desc` (default) / `asc` |
| `page_type` | string | No | `search` (default) |
| `scenario` | string | No | `PAGE_GLOBAL_SEARCH` |
| `version` | string | No | `2` |

**Response:**
```json
{
  "total_count": 12345,
  "items": [
    {
      "itemid": 123456789,
      "shopid": 987654321,
      "title": "Product Name",
      "image": "abc123",
      "brand": "Brand Name",
      "currency": "VND",
      "price": 259000000,  // VND * 100000
      "price_before_discount": 359000000,
      "discount": 28,
      "historical_sold": 1520,
      "rating_star": 4.7,
      "rating_count": [520, 120, 80, 50, 30],
      "shop_name": "Shop Name",
      "shop_location": "Hà Nội",
      "is_adult": false,
      "catid": 1234,
      "categories": [...]
    }
  ]
}
```

### 2.2 Product Detail

```
GET https://shopee.vn/api/v4/item/get
```

| Param | Type | Required | Description |
|-------|------|----------|-------------|
| `itemid` | int | Yes | Product ID |
| `shopid` | int | Yes | Shop ID |

**Response:**
```json
{
  "item": {
    "itemid": 123456789,
    "shopid": 987654321,
    "title": "Product Name",
    "description": "Full description...",
    "images": ["abc123", "def456"],
    "price": 259000000,
    "price_before_discount": 359000000,
    "discount": 28,
    "historical_sold": 1520,
    "rating_star": 4.7,
    "rating_count": [520, 120, 80, 50, 30],
    "models": [
      {
        "modelid": 111,
        "name": "Red / M",
        "price": 259000000,
        "stock": 50
      }
    ],
    "shop_name": "Shop Name",
    "shop_location": "Hà Nội",
    "catid": 1234,
    "categories": [...],
    "brand": "Brand Name",
    "condition": 1,
    "weight": 5000,
    "dimension": {...},
    "attributes": [...]
  }
}
```

### 2.3 Shop Profile

```
GET https://shopee.vn/api/v4/shop/get_shop_detail
```

| Param | Type | Required | Description |
|-------|------|----------|-------------|
| `shopid` | int | Yes | Shop ID |

**Response:**
```json
{
  "data": {
    "shopid": 987654321,
    "name": "Shop Name",
    "rating_star": 4.8,
    "rating_bad": 50,
    "rating_good": 5000,
    "rating_normal": 200,
    "follower_count": 15000,
    "item_count": 500,
    "response_rate": 95,
    "response_time": 3600,
    "account": {
      "username": "shopname",
      "portrait": "abc123"
    }
  }
}
```

### 2.4 Shop Products

```
GET https://shopee.vn/api/v4/shop/search_items
```

| Param | Type | Required | Description |
|-------|------|----------|-------------|
| `shopid` | int | Yes | Shop ID |
| `limit` | int | No | Items per page (max 100) |
| `newest` | int | No | Offset |
| `order` | string | No | `desc` / `asc` |

---

## 3. Data Schema

### 3.1 Normalized Product (ShopeeProduct)

```python
class ShopeeProduct(BaseModel):
    source: str = "shopee"
    source_item_id: int
    source_shop_id: int
    title: str
    brand: str | None
    category_path: list[str]
    price_vnd: int              # Already in VND (divide raw by 100000)
    original_price_vnd: int | None
    discount_pct: int | None
    currency: str = "VND"
    sold_count: int
    rating_avg: float
    rating_count: int
    stock_qty: int | None
    shop_name: str
    shop_location: str
    shop_follower_count: int | None
    shop_rating: float | None
    image_urls: list[str]
    description: str | None
    variants: list[dict] | None
    source_url: str             # https://shopee.vn/product/<shopid>/<itemid>
    fetched_at: datetime
```

### 3.2 Normalized Shop (ShopeeShop)

```python
class ShopeeShop(BaseModel):
    source: str = "shopee"
    source_shop_id: int
    name: str
    username: str
    rating_avg: float
    follower_count: int
    item_count: int
    response_rate: int | None    # Percentage
    response_time: int | None    # Seconds
    location: str
    portrait_url: str | None
    fetched_at: datetime
```

---

## 4. Authentication

### 4.1 Cookie-Based

```python
# Cookie extraction (manual or automated)
COOKIE_STRING = "SPC_EC=...; SPC_F=...; SPC_R_T_ID=...; ..."

headers = {
    "User-Agent": "Mozilla/5.0 ...",
    "Cookie": COOKIE_STRING,
    "Referer": "https://shopee.vn/search?keyword=...",
    "X-Api-Source": "PC",
    "X-Requested-With": "XMLHttpRequest"
}
```

### 4.2 Cookie Refresh Strategy

| Approach | Pros | Cons |
|----------|------|------|
| **Manual refresh** (browser DevTools) | Simple, reliable | Not scalable, manual |
| **Headless browser login** | Automated | Complex, CAPTCHA risk |
| **Cookie pool** (multiple accounts) | Scalable | Account management |

**Recommendation:** Start with manual refresh (cookie valid ~7 days), automate later.

---

## 5. Rate Limiting

### 5.1 Limits

| Endpoint | Limit | Window |
|----------|-------|--------|
| Search | ~10 req/min | Per cookie |
| Product detail | ~30 req/min | Per cookie |
| Shop profile | ~10 req/min | Per cookie |
| Shop products | ~10 req/min | Per cookie |

### 5.2 Strategy

```python
# Token bucket rate limiter
class ShopeeRateLimiter:
    def __init__(self, requests_per_minute: int = 10):
        self.rate = requests_per_minute / 60.0
        self.tokens = requests_per_minute / 2
        self.max_tokens = requests_per_minute / 2
        self.last_refill = time.monotonic()

    async def acquire(self):
        now = time.monotonic()
        elapsed = now - self.last_refill
        self.tokens = min(self.max_tokens, self.tokens + elapsed * self.rate)
        self.last_refill = now
        if self.tokens < 1.0:
            await asyncio.sleep((1.0 - self.tokens) / self.rate)
            self.tokens = 0
        else:
            self.tokens -= 1
```

### 5.3 Jitter

```python
# Add randomized delay between requests
async def jitter_delay(base: float = 1.0, jitter: float = 0.5):
    await asyncio.sleep(base + random.uniform(0, jitter))
```

---

## 6. Error Handling

| Error | Cause | Action |
|-------|-------|--------|
| `error` in response | API error | Log + retry with backoff |
| `error 90309999` | Cookie expired | Refresh cookie |
| HTTP 429 | Rate limited | Exponential backoff |
| HTTP 403 | IP/UA blocked | Rotate UA + proxy |
| HTTP 500 | Server error | Retry 3x, then skip |
| Empty results | End of pagination | Stop pagination |

---

## 7. Implementation

### 7.1 File Structure

```
app/proprietary/platforms/shopee/
├── __init__.py
├── client.py          # API client + rate limiter
├── models.py          # ShopeeProduct, ShopeeShop schemas
├── cookie_manager.py  # Cookie refresh logic
└── exceptions.py      # ShopeeAPIError, CookieExpiredError

app/capabilities/shopee/scrape/
├── __init__.py
├── definition.py      # Capability registration
├── schemas.py         # API response schemas
├── executor.py        # Orchestrator
└── billing.py         # BillingUnit integration
```

### 7.2 Executor Flow

```python
class ShopeeExecutor:
    async def execute(self, request: ShopeeScrapeRequest) -> ShopeeScrapeResult:
        # 1. Validate cookie
        # 2. Search products (paginated)
        # 3. Enrich with product detail (optional)
        # 4. Enrich with shop profile (optional)
        # 5. Normalize to ShopeeProduct schema
        # 6. Persist to raw_scapes table
        # 7. Return ShopeeScrapeResult
```

### 7.3 Billing

| Request type | Cost |
|--------------|------|
| Search (per 100 results) | 1 credit |
| Product detail | 0.1 credit |
| Shop profile | 0.5 credit |
| Shop products (per 100 results) | 1 credit |

---

## 8. Risks + Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| API change | Medium | High | Monitor + version pin |
| Cookie expiry | High | Medium | Cookie pool + refresh automation |
| IP ban | Low | High | Residential proxies (backup) |
| Legal (ToS) | Low | Medium | Public data only, no login bypass |
| Rate limit change | Medium | Low | Adaptive rate limiter |

---

## 9. Testing

| Test | File | Validates |
|------|------|-----------|
| API client | `test_shopee_client.py` | Endpoints, rate limiting |
| Cookie refresh | `test_shopee_cookie_manager.py` | Cookie expiry handling |
| Normalization | `test_shopee_models.py` | Schema mapping |
| Error handling | `test_shopee_errors.py` | 429, 403, expired cookie |
| Integration | `test_shopee_e2e.py` | Full flow with mock API |

---

## 10. Timeline

| Phase | Duration | Deliverable |
|-------|----------|-------------|
| API research + prototype | 2 days | Working client |
| Cookie management | 1 day | Refresh logic |
| Executor + billing | 2 days | Full capability |
| Tests | 2 days | 80% coverage |
| Integration + monitoring | 1 day | Production ready |
| **Total** | **8 days** | |

---

## 11. Dependencies

| Package | Version | Use |
|---------|---------|-----|
| `httpx` | latest | Async HTTP client |
| `pydantic` | v2 | Schema validation |
| `tenacity` | latest | Retry with backoff |
| `aiocache` | latest | Cookie cache |

---

**Next step:** Implement `app/proprietary/platforms/shopee/client.py` prototype.
