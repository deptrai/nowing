---
stepsCompleted: [1, 2, 3, 4, 5, 6]
inputDocuments:
  - file: /Users/luisphan/Documents/GitHub/nowing/nowing_backend/app/capabilities/reddit/scrape/definition.py
  - file: /Users/luisphan/Documents/GitHub/nowing/nowing_backend/app/capabilities/reddit/scrape/executor.py
  - file: /Users/luisphan/Documents/GitHub/nowing/nowing_backend/app/capabilities/reddit/scrape/schemas.py
  - file: /Users/luisphan/Documents/GitHub/nowing/nowing_backend/app/proprietary/platforms/reddit/fetch.py
  - file: /Users/luisphan/Documents/GitHub/nowing/nowing_backend/app/proprietary/platforms/reddit/parsers.py
  - file: /Users/luisphan/Documents/GitHub/nowing/nowing_backend/app/proprietary/platforms/reddit/schemas.py
  - file: /Users/luisphan/Documents/GitHub/nowing/nowing_backend/app/proprietary/platforms/reddit/scraper.py
  - file: /Users/luisphan/Documents/GitHub/nowing/nowing_backend/app/capabilities/core/types.py
  - file: /Users/luisphan/Documents/GitHub/nowing/nowing_backend/app/capabilities/core/billing.py
  - file: /Users/luisphan/Documents/GitHub/nowing/nowing_backend/app/capabilities/core/access/rest.py
  - file: /Users/luisphan/Documents/GitHub/nowing/nowing_backend/app/routes/__init__.py
  - file: /Users/luisphan/Documents/GitHub/nowing/nowing_mcp/mcp_server/features/scrapers/platforms/reddit.py
  - file: /Users/luisphan/Documents/GitHub/nowing/nowing_mcp/mcp_server/features/scrapers/__init__.py
  - file: /Users/luisphan/Documents/GitHub/nowing/nowing_mcp/mcp_server/features/scrapers/capability.py
  - file: /Users/luisphan/Documents/GitHub/nowing/nowing_backend/app/mcp_tools.py
  - file: /Users/luisphan/Documents/GitHub/nowing/nowing_web/app/(home)/mcp-server/page.tsx
  - web: https://batdongsan.com.vn/robots.txt
  - web: https://stackoverflow.com/questions/59318810/request-return-gzip-vietnam-characters
  - web: https://apify.com/abotapi/batdongsan-com-vn-scraper/api
  - web: https://github.com/trannguyenhan/batdongsan.com.vn-crawler-python
  - web: https://dataflirt.com/scraper/batdongsan/
workflowType: research
lastStep: 6
research_type: technical
research_topic: Giải pháp kỹ thuật thêm scraper batdongsan.com.vn vào Nowing
research_goals: Xác định cách tích hợp nền tảng batdongsan.com.vn vào kiến trúc scraper hiện tại của Nowing (backend capability, proprietary fetcher, MCP tool, billing, route, test) và các rủi ro kỹ thuật/pháp lý.
user_name: Luisphan
date: 2026-08-02
web_research_enabled: true
source_verification: true
---

# Research Report: technical

**Date:** 2026-08-02  
**Author:** Luisphan  
**Research Type:** technical  

---

## Research Overview

Tài liệu này tổng hợp nghiên cứu kỹ thuật cho việc thêm một **scraper tool mới `batdongsan`** vào Nowing, dựa trên kiến trúc scraper hiện tại của dự án. Nội dung chính bao gồm: (1) phân tích kiến trúc scraper của Nowing; (2) khảo sát nguồn dữ liệu từ `batdongsan.com.vn` (API di động nội bộ, cấu trúc phản hồi, chống bot); (3) đề xuất giải pháp kỹ thuật cụ thể với danh sách file cần tạo/sửa; (4) các rủi ro, hạn chế và lộ trình triển khai.

> **Lưu ý tên miền:** người dùng đề cập `batdongsang.com.vn`, nhưng tên miền đúng của nền tảng là `batdongsan.com.vn` (thiếu chữ "g"). Toàn bộ nghiên cứu và đề xuất code sử dụng tên miền chính xác này.

---

## Mục lục

1. [Tóm tắt điều hành (Executive Summary)](#1-tóm-tắt-điều-hành-executive-summary)
2. [Kiến trúc scraper hiện tại của Nowing](#2-kiến-trúc-scraper-hiện-tại-của-nowing)
3. [Khảo sát nguồn dữ liệu batdongsan.com.vn](#3-khảo-sát-nguồn-dữ-liệu-batdongsancomvn)
4. [Phương án tích hợp đề xuất](#4-phương-án-tích-hợp-đề-xuất)
5. [Danh sách file cần tạo/sửa](#5-danh-sách-file-cần-tạosửa)
6. [Chi tiết thiết kế kỹ thuật](#6-chi-tiết-thiết-kế-kỹ-thuật)
7. [Billing và Metering](#7-billing-và-metering)
8. [MCP Tool và Frontend](#8-mcp-tool-và-frontend)
9. [Test Strategy](#9-test-strategy)
10. [Rủi ro, hạn chế và lưu ý pháp lý](#10-rủi-ro-hạn-chế-và-lưu-ý-pháp-lý)
11. [Lộ trình triển khai đề xuất](#11-lộ-trình-triển-khai-đề-xuất)
12. [Tài liệu tham khảo](#12-tài-liệu-tham-khảo)

---

## 1. Tóm tắt điều hành (Executive Summary)

**Kết luận chính:** `batdongsan.com.vn` có thể được tích hợp như một scraper platform mới của Nowing bằng cách **tái sử dụng mẫu capability/proprietary platform** đã được chứng minh với `reddit.scrape`, `google_search.scrape`, `youtube.scrape`, v.v. Điểm khác biệt lớn nhất là dữ liệu tin rao có thể lấy qua **API di động nội bộ `https://apimap.batdongsan.com.vn/api/p_sync`** thay vì phải chạy trình duyệt — giảm chi phí và tăng độ ổn định.

**Những phát hiện quan trọng từ nghiên cứu thực tế:**

- Trang `batdongsan.com.vn` chính bị **Cloudflare "Just a moment..."** khi truy cập bằng `curl` thông thường; HTML scraping trực tiếp không khả thi mà không có proxy residential hoặc trình duyệt stealth.
- Tuy nhiên, endpoint `apimap.batdongsan.com.vn/api/p_sync` (của ứng dụng di động Android) vẫn **phản hồi thành công** từ môi trường thử nghiệm (không cần proxy VN) khi gửi đúng `User-Agent` di động, `Origin`, và các tham số form.
- Phản hồi từ API được mã hóa theo trình tự: **gzip → base64 → nibble-swap → Latin-1 JSON**. Sau giải mã, dữ liệu là JSON chuẩn chứa mảng `data[]` các tin rao với các trường: `id`, `title`, `address`, `price`, `area`, `cat` (loại BĐS), `lat`, `lon`, `date`, `room`, `avatar`, `url`.
- Hai giá trị `ptype` đã xác định: `38` = **Mua bán** (bán), `49` = **Cho thuê**. `cate=0` hoạt động, `cate>0` trả về rỗng trong thử nghiệm.
- Mã thành phố thử nghiệm thành công: `HN` (Hà Nội), `SG` (TP.HCM), `HP` (Hải Phòng), `CT` (Cần Thơ). `HCM`, `TP-HCM`, `tp-hcm`, `Da-Nang`, `DN`, `ĐN` không được chấp nhận.
- `dist` là ID số của quận/huyện. Ví dụ với `city=HN`: `dist=2` = Ba Đình, `dist=5` = Thanh Xuân, `dist=6` = Tây Hồ, `dist=7` = Cầu Giấy, `dist=8` = Hoàng Mai, `dist=9` = Long Biên, `dist=14` = Nam Từ Liêm.
- Phân trang hoạt động qua `page` và `pagesize` (mặc định tối đa khoảng 23–30 item/trang). `pagesize=30` trả về 23 item trong thử nghiệm.
- **Keyword, giá, diện tích, hướng, số phòng** không có tác dụng rõ ràng trên endpoint `p_sync` đã thử; nếu cần lọc sâu, phương án dự phòng là dùng `nowing_web_crawl` trên URL search hoặc lọc client-side trên kết quả list.

**Khuyến nghị:**

1. Triển khai `batdongsan.scrape` theo mẫu `reddit.scrape`, tận dụng API di động cho list, lưu `url` từng tin rao để làm provenance.
2. Phần engine fetcher đặt trong `nowing_backend/app/proprietary/platforms/batdongsan/` (BSL 1.1), phần capability wrapper đặt trong `nowing_backend/app/capabilities/batdongsan/scrape/` (Apache-2.0).
3. Thêm `BillingUnit.BATDONGSAN_ITEM`, tính phí theo item trả về, default micros = `3500` (có thể tune sau khi có số thật).
4. Thêm MCP tool `nowing_batdongsan_scrape` vào `nowing_mcp` và cập nhật catalog `app/mcp_tools.py`, marketing page `nowing_web`.
5. Cấu hình retry + proxy + rate limit theo mẫu `google_search`/`reddit`.
6. Viết test đơn vị cho schemas, parser, executor; test e2e với captured fixture từ API thật.

---

## 2. Kiến trúc scraper hiện tại của Nowing

Nowing tổ chức scraper theo **4 lớp** rõ ràng:

### 2.1. Capability registry (Apache-2.0)

Mỗi platform là một module con dưới `nowing_backend/app/capabilities/<platform>/`. Mỗi verb là `Capability` object đăng ký qua `register_capability()` khi module được import.

Ví dụ `reddit.scrape`:  
<ref_snippet file="/Users/luisphan/Documents/GitHub/nowing/nowing_backend/app/capabilities/reddit/scrape/definition.py" lines="1-23" />

`Capability` khai báo: `name`, `description`, `input_schema` (Pydantic), `output_schema`, `executor`, `billing_unit`, `docs_url`.  
<ref_snippet file="/Users/luisphan/Documents/GitHub/nowing/nowing_backend/app/capabilities/core/types.py" lines="51-73" />

Registry là in-process dict:  
<ref_snippet file="/Users/luisphan/Documents/GitHub/nowing/nowing_backend/app/capabilities/core/store.py" lines="1-20" />

Các capability namespace được import có tác dụng phụ (side-effect) đăng ký trong `app/routes/__init__.py`:  
<ref_snippet file="/Users/luisphan/Documents/GitHub/nowing/nowing_backend/app/routes/__init__.py" lines="1-12" />

REST router `build_capabilities_router()` duyệt registry và tạo route `POST /workspaces/{id}/scrapers/{platform}/{verb}` cùng endpoint list capabilities, run history, SSE events:  
<ref_snippet file="/Users/luisphan/Documents/GitHub/nowing/nowing_backend/app/capabilities/core/access/rest.py" lines="121-309" />

### 2.2. Proprietary engine (BSL 1.1)

Logic fetch, parse, và anti-bot nằm trong `nowing_backend/app/proprietary/platforms/<platform>/`. Ví dụ Reddit gồm `fetch.py` (proxy, warm session, rotate), `parsers.py` (JSON → item), `schemas.py` (input/output Pydantic), `scraper.py` (orchestrator).

<ref_snippet file="/Users/luisphan/Documents/GitHub/nowing/nowing_backend/app/proprietary/platforms/reddit/scraper.py" lines="1-56" />

<ref_snippet file="/Users/luisphan/Documents/GitHub/nowing/nowing_backend/app/proprietary/platforms/reddit/fetch.py" lines="142-160" />

### 2.3. Billing seam

`app/capabilities/core/billing.py` ánh xạ `BillingUnit` → config key → micros/item:  
<ref_snippet file="/Users/luisphan/Documents/GitHub/nowing/nowing_backend/app/capabilities/core/billing.py" lines="32-72" />

Pre-flight `gate_capability` kiểm tra credits dựa trên `estimated_units`; post-execution `charge_capability` tính tiền theo `billable_units` từ output.

### 2.4. MCP surface

`nowing_mcp/mcp_server/features/scrapers/platforms/<platform>.py` định nghĩa tool, sử dụng `run_scraper` để gọi backend.  
<ref_snippet file="/Users/luisphan/Documents/GitHub/nowing/nowing_mcp/mcp_server/features/scrapers/platforms/reddit.py" lines="1-96" />

`run_scraper` gọi `POST /workspaces/{id}/scrapers/{platform}/{verb}`:  
<ref_snippet file="/Users/luisphan/Documents/GitHub/nowing/nowing_mcp/mcp_server/features/scrapers/capability.py" lines="16-38" />

Catalog tool names nằm ở `nowing_backend/app/mcp_tools.py`:  
<ref_snippet file="/Users/luisphan/Documents/GitHub/nowing/nowing_backend/app/mcp_tools.py" lines="24-55" />

---

## 3. Khảo sát nguồn dữ liệu batdongsan.com.vn

### 3.1. robots.txt và tình trạng chống bot

`https://batdongsan.com.vn/robots.txt` cho phép crawl hầu hết các đường dẫn, chỉ cấm một số đường dẫn nội bộ:  

```
User-agent: *
Allow: /
Disallow: /microservice-architecture-router/
Disallow: /microservice-architecture-router-mobile
Disallow: /HandlerWeb/UserHandler.ashx?type=mobile&redirectUrl=
Sitemap: https://batdongsan.com.vn/sitemap.xml
```

Tuy nhiên, thử nghiệm `curl` với trang HTML chính (`/nha-dat-ban-ha-noi`) trả về trang **Cloudflare "Just a moment..."**. HTML scraping trực tiếp đòi hỏi trình duyệt stealth + proxy residential Việt Nam.

### 3.2. API di động `apimap.batdongsan.com.vn/api/p_sync`

Nguồn: phân tích từ StackOverflow "Request return gzip (Vietnam Characters)" và thử nghiệm trực tiếp.

- **Endpoint:** `POST https://apimap.batdongsan.com.vn/api/p_sync`
- **Headers bắt buộc:**
  - `Content-Type: application/x-www-form-urlencoded`
  - `Origin: https://batdongsan.com.vn`
  - `Accept: application/json`
  - `User-Agent: Dalvik/2.1.0 (Linux; U; Android 8.0.0; SM-G9500 Build/R16NW)` (hoặc một UA Android khác)
  - `Host: apimap.batdongsan.com.vn`
- **Tham số quan trọng:**
  - `ptype`: loại giao dịch. `38` = bán, `49` = cho thuê.
  - `cate`: danh mục. `0` hoạt động cho cả hai. Giá trị khác thử nghiệm trả về rỗng.
  - `city`: mã tỉnh/thành phố (ví dụ `HN`, `SG`, `HP`, `CT`).
  - `dist`: ID số quận/huyện (ví dụ `2` = Ba Đình, HN).
  - `ward`, `street`: ID phường/đường. `-1` = tất cả.
  - `room`, `direct`: số phòng, hướng. `-1` = tất cả.
  - `minprice`, `maxprice`, `minarea`, `maxarea`: trong thử nghiệm chưa có tác dụng rõ ràng.
  - `projectid`: `-1` = tất cả.
  - `sort`: `0` = mặc định.
  - `page`: số trang.
  - `pagesize`: kích thước trang (thực tế tối đa ~23–30).
  - `searchType`: `0` trong thử nghiệm.
  - `client=android`, `m=list`.

Tham số ví dụ:

```
ptype=38&cate=0&city=HN&dist=2&maxarea=0&minarea=0&maxprice=0&minprice=0&ward=-1&street=-1&room=-1&direct=-1&projectid=-1&sort=0&page=1&searchType=0&client=android&m=list&pagesize=20
```

### 3.3. Giải mã phản hồi API

Phản hồi trả về theo trình tự sau (đã xác minh bằng script Python):

1. **gzip** — có thể là `Content-Encoding: gzip`; nếu không, server vẫn trả raw bytes.
2. **base64** — sau khi giải nén gzip, nội dung là một chuỗi base64.
3. **nibble-swap** — mỗi byte sau khi base64 decode được đổi chỗ nibble cao/thấp: `new_byte = ((old_byte & 0x0F) << 4) | (old_byte >> 4)`.
4. **Latin-1 → JSON** — chuỗi sau nibble-swap được decode bằng `latin-1` rồi `json.loads`.

Minh họa Python:

```python
import gzip, base64, json

raw = response.content
if raw[:2] == b"\x1f\x8b":
    raw = gzip.decompress(raw)

decoded = base64.b64decode(raw)
swapped = bytes(((b & 0x0F) << 4) | (b >> 4) for b in decoded)
data = json.loads(swapped.decode("latin-1"))
```

### 3.4. Cấu trúc item trả về

Mỗi phần tử trong `data[]` có dạng:

```json
{
  "title": "...",
  "address": "...",
  "avatar": "https://file4.batdongsan.com.vn/crop/200x200/...",
  "price": "19.8 Tỷ",
  "lat": 21.0286146035022,
  "lon": 105.812719675434,
  "id": 46122640,
  "area": "75 m²",
  "cat": "Bán nhà riêng",
  "date": "31/07/2026",
  "room": 18,
  "url": "https://batdongsan.com.vn/nha-dat-ban-ba-dinh/...-pr46122640"
}
```

### 3.5. Các hạn chế nguồn dữ liệu

| Hạn chế | Mức độ | Ghi chú |
|---|---|---|
| Không lọc keyword qua `p_sync` | Trung bình | Có thể lọc client-side hoặc dùng URL search + `web.crawl` |
| Không lọc giá/diện tích | Trung bình | Tương tự, cần xác minh thêm hoặc dùng URL mode |
| Mã quận/huyện (`dist`) là số | Thấp | Cần mapping hoặc expose dưới dạng `district_id` |
| Mã thành phố không theo slug chuẩn | Thấp | Cần map `HN`/`SG`/`HP`/`CT` |
| API có thể thay đổi | Cao | Không có tài liệu chính thức; cần test fixture và degrade gracefully |
| Cloudflare trên HTML | Cao | Detail page cần browser/proxy nếu muốn lấy mô tả/SĐT đầy đủ |

---

## 4. Phương án tích hợp đề xuất

### 4.1. Tổng quan

Triển khai `batdongsan.scrape` theo đúng mẫu `reddit.scrape`:

- **Proprietary engine** (`app/proprietary/platforms/batdongsan/`): fetcher gọi `p_sync`, decode, retry/proxy, parsers chuyển JSON thành item.
- **Capability wrapper** (`app/capabilities/batdongsan/scrape/`): input/output Pydantic, executor map từ API-friendly input sang proprietary input, emit progress, tính `estimated_units` / `billable_units`.
- **Billing**: thêm `BillingUnit.BATDONGSAN_ITEM` và rate key `BATDONGSAN_SCRAPE_MICROS_PER_ITEM`.
- **MCP**: thêm `nowing_batdongsan_scrape` vào `nowing_mcp`.
- **REST/Marketing**: import namespace, cập nhật catalog.

### 4.2. Input schema đề xuất (MCP / capability)

```python
class ScrapeInput(BaseModel):
    listing_type: Literal["buy", "rent"] = "buy"
    city: str = Field(..., description="Mã thành phố: HN, SG, HP, CT, ...")
    district_id: int | None = None
    max_items: int = Field(default=10, ge=1, le=100)
    max_pages: int = Field(default=5, ge=1, le=20)
    # optional, YAGNI v1:
    # keyword: str | None = None
    # min_price, max_price, ...
```

`listing_type` map: `buy` → `ptype=38`, `rent` → `ptype=49`. `cate=0`.

### 4.3. Output schema đề xuất

```python
class BatdongsanItem(BaseModel):
    dataType: Literal["batdongsan_listing"] = "batdongsan_listing"
    id: int
    url: str
    title: str | None = None
    address: str | None = None
    city: str | None = None
    district: str | None = None
    price: str | None = None
    area: str | None = None
    category: str | None = None
    rooms: int | None = None
    latitude: float | None = None
    longitude: float | None = None
    published_at: str | None = None
    image_url: str | None = None
    scrapedAt: str
```

`billable_units` = `len(items)`.

---

## 5. Danh sách file cần tạo/sửa

### 5.1. File mới (proprietary — BSL 1.1)

| File | Mục đích |
|---|---|
| `nowing_backend/app/proprietary/platforms/batdongsan/__init__.py` | Export public surface: `BatdongsanScrapeInput`, `BatdongsanItem`, `scrape_batdongsan`, errors. |
| `nowing_backend/app/proprietary/platforms/batdongsan/schemas.py` | Pydantic input/output models nội bộ (raw API shape + item shape). |
| `nowing_backend/app/proprietary/platforms/batdongsan/fetch.py` | `fetch_listings(...)` gọi `p_sync`, decode gzip/base64/nibble, xử lý retry/proxy. |
| `nowing_backend/app/proprietary/platforms/batdongsan/parsers.py` | Parse raw JSON → `BatdongsanItem`; rút city/district từ `title`/`address` nếu cần. |
| `nowing_backend/app/proprietary/platforms/batdongsan/scraper.py` | Orchestrator: paginate, collect, cap `max_items`, emit progress. |

### 5.2. File mới (capability — Apache-2.0)

| File | Mục đích |
|---|---|
| `nowing_backend/app/capabilities/batdongsan/__init__.py` | `from .scrape import definition as _scrape` |
| `nowing_backend/app/capabilities/batdongsan/scrape/__init__.py` | Module docstring. |
| `nowing_backend/app/capabilities/batdongsan/scrape/schemas.py` | `ScrapeInput` (MCP-friendly) + `ScrapeOutput`; `estimated_units`, `billable_units`. |
| `nowing_backend/app/capabilities/batdongsan/scrape/executor.py` | Map `ScrapeInput` → `BatdongsanScrapeInput`, gọi `scrape_batdongsan`. |
| `nowing_backend/app/capabilities/batdongsan/scrape/definition.py` | `Capability(..., name="batdongsan.scrape", billing_unit=BillingUnit.BATDONGSAN_ITEM)`. |

### 5.3. File sửa (billing/config)

| File | Thay đổi |
|---|---|
| `nowing_backend/app/capabilities/core/types.py` | Thêm `BATDONGSAN_ITEM = "batdongsan_item"` vào `BillingUnit`. |
| `nowing_backend/app/capabilities/core/billing.py` | Thêm `BATDONGSAN_ITEM` vào `_PLATFORM_RATE_KEYS` và `_UNIT_NOUNS`. |
| `nowing_backend/app/config/__init__.py` | Thêm `BATDONGSAN_SCRAPE_MICROS_PER_ITEM` (default 3500). |
| `nowing_backend/.env.example` | Thêm dòng `# BATDONGSAN_SCRAPE_MICROS_PER_ITEM=3500`. |

### 5.4. File sửa (routing/registration)

| File | Thay đổi |
|---|---|
| `nowing_backend/app/routes/__init__.py` | Thêm `import app.capabilities.batdongsan` cùng các import khác. |

### 5.5. File mới/sửa (MCP)

| File | Thay đổi |
|---|---|
| `nowing_mcp/mcp_server/features/scrapers/platforms/batdongsan.py` | Tool `nowing_batdongsan_scrape` gọi `run_scraper(platform="batdongsan", verb="scrape")`. |
| `nowing_mcp/mcp_server/features/scrapers/__init__.py` | Thêm `batdongsan` vào `_REGISTRARS`. |
| `nowing_backend/app/mcp_tools.py` | Thêm `{"name": "nowing_batdongsan_scrape", "group": McpToolGroup.SCRAPER}`. |
| `nowing_web/app/(home)/mcp-server/page.tsx` | Thêm `nowing_batdongsan_scrape` vào `TOOL_GROUPS[0].tools` và cập nhật `metaDescription`. |

### 5.6. File mới (test)

| File | Mục đích |
|---|---|
| `nowing_backend/tests/unit/capabilities/batdongsan/scrape/test_schemas.py` | Validate input/output schemas. |
| `nowing_backend/tests/unit/capabilities/batdongsan/test_registry.py` | Kiểm tra capability được đăng ký với đúng billing. |
| `nowing_backend/tests/unit/platforms/batdongsan/test_parsers.py` | Test parser với fixture JSON từ API thật. |
| `nowing_backend/tests/unit/platforms/batdongsan/test_fetch_decode.py` | Test decode nibble-swap với sample bytes. |
| `nowing_backend/tests/unit/platforms/batdongsan/test_scraper.py` | Mock fetcher, kiểm tra pagination/cap. |
| `nowing_backend/scripts/e2e_batdongsan_scraper.py` | Chạy thực tế với API (flag `--live`). |

---

## 6. Chi tiết thiết kế kỹ thuật

### 6.1. `fetch.py` — gọi API và decode

Sử dụng `scrapling.fetchers.AsyncFetcher.post` (đã dùng trong `youtube/innertube` và `amazon/fetch.py`) với `proxy`, `stealthy_headers`.

Thuật toán decode:

```python
async def _decode_response(raw: bytes) -> dict:
    # 1. gzip nếu có
    if raw[:2] == b"\x1f\x8b":
        raw = gzip.decompress(raw)
    # 2. base64
    decoded = base64.b64decode(raw)
    # 3. nibble swap
    swapped = bytes(((b & 0x0F) << 4) | (b >> 4) for b in decoded)
    # 4. latin-1 JSON
    return json.loads(swapped.decode("latin-1"))
```

Retry/rotate:

- Nếu trả về `null`/rỗng hoặc status != 200, retry tối đa `_MAX_ATTEMPTS` lần.
- Sử dụng `app.utils.proxy.get_proxy_url()` / `get_sticky_proxy_url()` và rotate theo mẫu Reddit/YouTube.
- Đặt timeout ngắn (`_REQUEST_TIMEOUT_S = 15`) vì API nhanh.
- Pacing: giữa các request cách nhau ~0.5–1s để tránh rate-limit.

### 6.2. `scraper.py` — phân trang và collect

Mẫu từ `reddit.scraper`: async generator `iter_batdongsan` và collector `scrape_batdongsan(limit)`. Mỗi `page` là một request `p_sync`; dừng khi:

- Đạt `max_items`.
- Trang trả về ít hơn `pagesize` (hết dữ liệu).
- Lỗi sau retry.

Emit progress: `starting` → `scraping` theo item.

### 6.3. `parsers.py` — chuyển đổi JSON → item

- `parse_listing(raw: dict) -> BatdongsanItem`: chuyển `id`, `title`, `address`, `price`, `area`, `cat` → `category`, `lat`/`lon` → `latitude`/`longitude`, `date` → `published_at`, `avatar` → `image_url`, `url` gốc.
- Trích city/district từ `address` hoặc `title` nếu cần.
- `to_output()` giữ `extra` mở để mở rộng.

### 6.4. `executor.py` — capability wrapper

```python
async def execute(payload: ScrapeInput) -> ScrapeOutput:
    internal = BatdongsanScrapeInput(
        ptype=38 if payload.listing_type == "buy" else 49,
        cate=0,
        city=payload.city,
        dist=payload.district_id or 0,
        page=1,
        pagesize=20,
        # ...
    )
    items = await scrape_batdongsan(internal, limit=payload.max_items)
    return ScrapeOutput(items=items)
```

`estimated_units` = `max_items`. `billable_units` = `len(items)`.

---

## 7. Billing và Metering

Thêm `BATDONGSAN_ITEM` vào enum và billing map tương tự `REDDIT_ITEM`.

Cấu hình mặc định (có thể tinh chỉnh sau khi có số liệu thực tế):

```python
BATDONGSAN_SCRAPE_MICROS_PER_ITEM = int(
    os.getenv("BATDONGSAN_SCRAPE_MICROS_PER_ITEM", "3500")
)
```

Tương đương `$0.0035 / listing`. Lý do chọn 3500:

- API di động rẻ (không cần browser).
- Ngang bằng `REDDIT_SCRAPE_MICROS_PER_ITEM=3500` làm khởi điểm.
- Có thể điều chỉnh sau khi đo proxy cost thực tế.

---

## 8. MCP Tool và Frontend

### 8.1. MCP tool

File `nowing_mcp/mcp_server/features/scrapers/platforms/batdongsan.py` mirror `reddit.py`:

```python
@mcp.tool(name="nowing_batdongsan_scrape", title="Scrape Batdongsan listings", annotations=SCRAPE)
async def batdongsan_scrape(
    listing_type: Annotated[Literal["buy", "rent"], Field(...)] = "buy",
    city: Annotated[str, Field(...)] = "HN",
    district_id: Annotated[int | None, Field(...)] = None,
    max_items: Annotated[int, Field(ge=1, le=100)] = 10,
    ...
) -> str:
    ...
```

### 8.2. Catalog

Thêm vào `MCP_TOOL_CATALOG`:

```python
{"name": "nowing_batdongsan_scrape", "group": McpToolGroup.SCRAPER},
```

### 8.3. Marketing page

Thêm `nowing_batdongsan_scrape` vào `TOOL_GROUPS[0].tools` trong `nowing_web/app/(home)/mcp-server/page.tsx` và cập nhật `metaDescription` để nhắc đến BĐS Việt Nam.

---

## 9. Test Strategy

| Lớp | Test | Phương pháp |
|---|---|---|
| Schema | `tests/unit/capabilities/batdongsan/scrape/test_schemas.py` | Valid/invalid input; đảm bảo `estimated_units`/`billable_units`. |
| Registry | `tests/unit/capabilities/batdongsan/test_registry.py` | `get_capability("batdongsan.scrape").billing_unit == BillingUnit.BATDONGSAN_ITEM`. |
| Decoder | `tests/unit/platforms/batdongsan/test_fetch_decode.py` | Fixture bytes → JSON đúng. |
| Parser | `tests/unit/platforms/batdongsan/test_parsers.py` | Fixture JSON → item; kiểm tra `price`, `lat`, `url`. |
| Scraper | `tests/unit/platforms/batdongsan/test_scraper.py` | Mock `fetch_listings` trả nhiều trang; kiểm tra cap, dedupe, progress. |
| Executor | `tests/unit/capabilities/batdongsan/scrape/test_executor.py` | Inject fake `scrape_batdongsan`, kiểm tra mapping input/output. |
| E2E | `scripts/e2e_batdongsan_scraper.py` | Chạy thực với `city=HN`, `pagesize=5`, in JSON. |

Fixture capture: dùng script Python gọi API thật, lưu raw response bytes vào `tests/fixtures/batdongsan_listing.bin` và `tests/fixtures/batdongsan_listing.json` đã decode.

---

## 10. Rủi ro, hạn chế và lưu ý pháp lý

### 10.1. Rủi ro kỹ thuật

| Rủi ro | Mức độ | Mitigation |
|---|---|---|
| API `p_sync` thay đổi/bị đóng | Cao | Viết decoder tách biệt; dễ dàng degrade sang `web.crawl`; giữ fixture; monitor e2e. |
| Rate limiting / IP block | Trung bình | Sử dụng proxy rotation (`get_proxy_url`/`get_sticky_proxy_url`); pace request; retry. |
| Cloudflare trên detail page | Trung bình | V1 chỉ list; detail dùng `nowing_web_crawl` hoặc Playwright nếu khách yêu cầu. |
| Dữ liệu thiếu `description`, SĐT, agent | Trung bình | API list không có; cần detail. Ghi rõ trong docs/MCP description. |
| Mã `dist`/`city` không ổn định | Thấp | Expose `district_id` thô; document mapping; có thể bổ sung lookup sau. |

### 10.2. Pháp lý và ToS

- `robots.txt` không cấm thu thập dữ liệu công khai, nhưng điều khoản sử dụng của `batdongsan.com.vn` (PropertyGuru) có thể hạn chế tự động hóa.
- Nên ghi nhận nguồn (`url`) và không thu thập thông tin liên hệ cá nhân (SĐT, email) nếu chưa rõ pháp lý.
- BSL 1.1 áp dụng cho `app/proprietary/platforms/batdongsan/`. Không bán riêng scraper engine; chỉ dùng như một capability của Nowing.

---

## 11. Lộ trình triển khai đề xuất

1. **Story 1 — Proprietary fetcher + decoder (P0):**
   - Tạo `app/proprietary/platforms/batdongsan/{fetch,parsers,schemas,scraper}.py`.
   - Viết unit test decode + parser với fixture.

2. **Story 2 — Capability wrapper (P0):**
   - Tạo `app/capabilities/batdongsan/scrape/`.
   - Đăng ký capability, update `app/routes/__init__.py`.

3. **Story 3 — Billing (P0):**
   - Thêm `BillingUnit.BATDONGSAN_ITEM`, update `billing.py`, `config/__init__.py`, `.env.example`.

4. **Story 4 — MCP + catalog (P0):**
   - Tạo `nowing_mcp/mcp_server/features/scrapers/platforms/batdongsan.py`.
   - Cập nhật `_REGISTRARS`, `app/mcp_tools.py`, `nowing_web` page.

5. **Story 5 — E2E + tune (P1):**
   - `scripts/e2e_batdongsan_scraper.py`, verify rate/latency/proxy.
   - Tune `BATDONGSAN_SCRAPE_MICROS_PER_ITEM`.

6. **Story 6 — Detail / keyword nâng cao (P2):**
   - Tích hợp `nowing_web_crawl` hoặc Playwright để lấy detail nếu cần.
   - Bổ sung district/city lookup.

---

## 12. Tài liệu tham khảo

1. StackOverflow — "Request return gzip (Vietnam Characters)" — hướng dẫn decode nibble-swap: https://stackoverflow.com/questions/59318810/request-return-gzip-vietnam-characters
2. Apify actor — "Batdongsan $1 Search By URLs and Keywords API" — mô tả input/output và proxy VN residential: https://apify.com/abotapi/batdongsan-com-vn-scraper/api
3. GitHub — `trannguyenhan/batdongsan.com.vn-crawler-python` — selectors HTML crawl: https://github.com/trannguyenhan/batdongsan.com.vn-crawler-python
4. DataFlirt — Batdongsan scraper service — gợi ý Cloudflare, VN proxy, Playwright: https://dataflirt.com/scraper/batdongsan/
5. `batdongsan.com.vn/robots.txt` — chính sách crawl.
6. Nowing codebase (các file `reddit.scrape`, `proprietary/platforms/reddit`, `mcp_server/features/scrapers/platforms/reddit.py`, `app/capabilities/core/billing.py`, `app/capabilities/core/types.py`, `app/capabilities/core/access/rest.py`, `app/mcp_tools.py`, `nowing_web/app/(home)/mcp-server/page.tsx`) — patterns triển khai.

---

**Kết luận:** Tích hợp `batdongsan.com.vn` là khả thi và phù hợp với kiến trúc scraper hiện tại. Giải pháp tối ưu là sử dụng API di động nội bộ cho list, tận dụng mẫu `reddit.scrape` cho capability/MCP/billing, và để detail/keyword nâng cao cho các sprint sau. Nếu bạn muốn, tôi có thể chuyển sang tạo story/spec hoặc implement trực tiếp bắt đầu từ Story 1.
