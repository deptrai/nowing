# Request to Medirus team — platform parity for unified `medirus_scrape`

> From: Nowing backend team (Epic 40 follow-up)
> Date: 2026-10-09
> Priority: P1 — chặn đường cutover `MEDIRUS_USE_UNIFIED_DISPATCH` cho 9 platform còn lại

## Bối cảnh

Nowing đã hoàn tất Epic 40 thin-proxy cutover: `medirus_scrape_or_local()` trong
`nowing_backend/app/capabilities/core/medirus_proxy.py` route 8 platform có descriptor
(`batdongsan, chotot, masothue, vietnamworks, reddit, tiktok, instagram, youtube`)
qua `medirus_scrape` khi `MEDIRUS_USE_UNIFIED_DISPATCH=true`, fallback local khi
`tool_not_found`/connectivity. Live smoke đã pass (masothue trả 10 record thật).

9 platform Nowing vẫn phải chạy local scraper vì Medirus **chưa có**
`src/scrapers/<platform>/` nào (kiến trúc Medirus `ARCHITECTURE-SPINE.md:488`
ghi cố ý defer "cho tới khi có epic cụ thể" — request này chính là epic đó).

## Yêu cầu

Viết scraper module chuẩn Medirus cho 9 platform, mỗi platform gồm
`client.js` + `crawler.js` + `descriptor.js` + `index.js` (+ normalizer/validator
nếu cần), đăng ký vào `DESCRIPTORS` trong `src/scrapers/index.js` và
`crawlerModuleMap` trong `src/mcp/server.js` (`executeScrapeTool`), theo đúng
pattern `src/scrapers/realestate/chotot/` và `src/scrapers/procurement/masothue/`.

### Platform cần implement (tham chiếu Python nguồn ở repo Nowing)

Nowing source: `nowing_backend/app/proprietary/platforms/<platform>/`
(fetch.py, scraper.py, parsers.py, schemas.py — tổng ~12K dòng; port logic
fetch+parse, KHÔNG port verbatim từng dòng).

| Platform | Category gợi ý | Actions Nowing cần | Args chính (schema nowing) |
|---|---|---|---|
| muaban_bds | realestate | `search_listings`, `listing_detail` | `province`, `district`, `keyword`, `listing_type`, `page`, `limit` |
| itviec | recruitment | `search_jobs`, `job_detail` | `keyword`, `location`, `limit` |
| cafef | finance/news | `search_news`, `ticker_news` | `keyword`/`ticker`, `limit`, `source_url` |
| vietstock | finance/news | `search_news`, `ticker_news` | `keyword`/`ticker`, `limit` |
| indeed | recruitment | `search_jobs` | `keyword`, `location`, `limit` |
| walmart | ecom | `search_products`, `product_detail` | `keyword` hoặc `url`, `limit` |
| amazon | ecom | `search_products`, `product_detail` | `categoryOrProductUrls`, `url`, `keyword` |
| google_maps | places | `search_places`, `place_reviews` | `url`/`searchStringsArray`, `categoryFilterWords`, `maxReviews` |
| google_search | web | `search` | `query`, filters (`site`, `dateRange`, `language`, `country`), `limit` |

Action names trên là gợi ý — Nowing sẽ adapt theo action map thực tế Medirus
định nghĩa, miễn là `descriptor.mapAction` resolve được từ alias phổ biến
(`search`, `search_listings`, `search_jobs`, `detail`, …) giống các descriptor
hiện có.

## Contract cần tuân thủ

- Response phải đi qua `wrapToolResult('medirus_scrape', …)` như các tool khác —
  Nowing đọc `result.data` (hoặc `result.preview` khi daemon chạy
  `REDIS_STREAM_ENABLED=true`; Nowing đã gửi `dryRun:true` để nhận full data
  in-band — đừng đổi semantics này).
- Mỗi record trả về có `platform`, `externalId`, `category`, `metadata` theo
  shape `posts[]` hiện có (normalize giống `normalize-chotot.js`).
- Lỗi dùng `PlatformError`/`actionNotAvailable` chuẩn; code `MEDIRUS_4001`
  (circuit), `MEDIRUS_4002` (invalid args), `tool_not_found` cho action chưa hỗ trợ.
- Crawler implement `listActions()` trả `requiredArgs` + `example` để
  pre-validation của `executeScrapeTool` hoạt động.

## Acceptance

- `medirus_list` trả đủ 9 platform mới với actions + requiredArgs.
- `medirus_scrape{platform, action:'search*', args}` trả `success:true` và
  `data`/`preview` non-empty cho query mẫu của từng site (verify live, có thể
  cần proxy VN cho cafef/vietstock/muaban_bds).
- Unit test per-platform đạt bar của suite `test/` hiện có (≥ test coverage
  của chotot/masothue descriptor).

## Nowing sẽ làm tiếp khi parity đạt

Route nốt 7 capability executors (`cafef, indeed, itviec, muaban_bds, vietstock,
walmart, amazon/google_maps/google_search` — các executor tương ứng) + 2 lead
adapters (`muaban_bds`, `itviec`) qua `medirus_scrape_or_local()` — thay đổi 1
dòng mỗi nơi, giữ nguyên fallback local. Revisit AI-40.2 (decommission) chỉ khi
parity + quyết định bỏ local-fallback.

## Câu hỏi mở cho Medirus team

1. amazon/google_maps/google_search — Medirus có muốn host 3 platform Mỹ/global
   này không, hay Nowing giữ local vĩnh viễn? (Retro Epic 40 đã ghi đây là
   "OTHER" tier, priority thấp nhất.)
2. Proxy pool: cafef/vietstock/muaban_bds cần VN residential proxy — Medirus
   `PROXY_URL` hiện có đủ cover chưa hay cần pool riêng?
