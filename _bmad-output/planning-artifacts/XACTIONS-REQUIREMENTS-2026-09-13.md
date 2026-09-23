# XActions Requirements — Nowing Unified Connection Contract

**Ngày:** 2026-09-13
**Từ:** Nowing (Winston/BMAD architecture + spec run)
**Đến:** XActions team
**Nguồn contract:** `architecture-Nowing-2026-09-13/ARCHITECTURE-SPINE.md` (AD-1..10) + `spec-xactions-connection/SPEC.md`
**Bối cảnh:** XActions epic 25 đã ship unified `scrape(platform,action,args)` dispatcher + exports v2 + ACL/ET. Đây là **internal entry point** — chưa có MCP/service surface cho external caller. Nowing đã wire phía mình (`XActionsMcpClient` streamable-http + Celery beat + stream consumer) nhưng bị chặn bởi các gap dưới đây.

> Mục tiêu: biến `scrape()` dispatcher thành service-to-service contract mà nowing (và consumer khác) gọi được — control plane qua MCP, data plane qua Redis Stream. **Không** yêu cầu REST endpoint mới.

---

## REQ-X1 — Expose generic MCP tool `x_scrape` (BLOCKER, P1)

**Hiện trạng:** `x_scrape` không tồn tại trong `TOOLS` của `src/mcp/server.js`. Nowing `PLATFORM_TOOL_MAP` gọi `x_scrape` cho 9 loại VN target → tất cả fail `tool_not_found`.

**Yêu cầu:** thêm MCP tool `x_scrape` gọi thẳng `scrape()` dispatcher (epic 25).

```
inputSchema:
  platform: string      (required — canonical platform key trong DESCRIPTORS)
  action:   string      (required — canonical action từ ActionDescriptor)
  args:     object      (required — action args, object lồng KHÔNG phẳng)
  context:  object?     { targetId?, workspaceId? }  — forward nguyên vẹn vào stream event
  accountId: string?
  proxyUrl:  string?
  dryRun:    boolean?   (default true)
  artifactFormat: 'jsonl'|'csv'?
```

- Forward `args` vào `scrape(platform, action, args)`. Map "action not available" → `PlatformError XACT_4001` + `suggestedAction: use_x_actions_list`.
- Khi `REDIS_STREAM_ENABLED=true`, `x_scrape` trả **execution metadata + `data:[]`** (preview) — data đi qua stream, không trả full dataset trong response (tránh split-brain).
- `context` là phong bì multi-tenant caller truyền; XActions **không** dùng nó để scrape, chỉ forward vào stream event (xem REQ-X2).
- Mẫu tham chiếu: `executeCrawlPostTool` đã làm đúng pattern này — `x_scrape` là bản generic của nó.

**Done khi:** `x_scrape('masothue','search',{taxCode:...})` trả envelope thành công; `x_scrape('chotot','search_listings',{...})` chạy được.

---

## REQ-X2 — Stream-publish hook trong `AbstractCrawler` (P1 — data plane)

**Hiện trạng:** chỉ 8 social crawler `xAdd` vào `stream:social:raw_posts` (facebook/twitter/tiktok/reddit/bluesky/threads/medium/instagram). **15 VN/non-social crawler emit 0 event** — data kẹt ở MCP cap. `base-crawler.js` không có stream hook.

**Yêu cầu:** đưa stream-publish vào `AbstractCrawler` (base) sau `storeBatch`, để mọi crawler kế thừa tự động emit. Gate bởi `REDIS_STREAM_ENABLED`, `MAXLEN ~1M`.

**Event schema = snake_case** (khớp nowing `SocialPostEvent` — không camelCase):

```jsonc
{
  "id": "...",               // internal id
  "platform": "...",         // canonical platform
  "external_post_id": "...", // stable external id
  "category": "...",
  "author_id": "...",
  "author_name": "...",
  "post_url": "...",
  "crawled_at": "ISO8601",
  "storage_ref": "...",       // pointer to full payload / artifact
  "scraper_id": "...",
  "content_snippet": "...",   // <= 4000 chars — BẮT BUỘC (consumer extract lead từ đây)
  "target_id": "...",         // từ x_scrape context.targetId — forward nguyên vẹn
  "workspace_id": 0,          // từ x_scrape context.workspaceId — forward nguyên vẹn
  "schema_version": 1
}
```

- `content_snippet` + `target_id`/`workspace_id` là **bắt buộc** — thiếu → nowing consumer drop (workspace_id NOT NULL, content cần cho intent/lead extraction).
- Per-crawler chỉ override `platform` + field mapping; logic publish ở base.

**Done khi:** `scrape('shopee','search_products',...)` với `REDIS_STREAM_ENABLED` emit thin event đủ schema vào stream.

---

## REQ-X3 — `x_actions_list` cover mọi platform (P1 — discovery)

**Hiện trạng:** `executeActionListTool` (`src/scrapers/social/actions-list.js`) chỉ enumerate **5 social crawler** (facebook/threads/reddit/medium/instagram) — không có VN/non-social.

**Yêu cầu:** enumerate toàn bộ `DESCRIPTORS` registry (mọi platform epic-25 biết), trả `ActionDescriptor` cho mỗi action:

```
{ platform, action, description, requiredArgs[], optionalArgs[], example, outputType, requiresAuth }
```

- Tên trường cố định — nowing `UniversalScrapeTargetMapper` parse `requiredArgs` + `example` để build map, không hard-code.

**Done khi:** `x_actions_list` (không filter) trả actions cho shopee, topcv, masothue, chotot, batdongsan, vietnamworks, linkedin, b2b-registry, tiktok, zalo, youtube… — không chỉ 5 social.

---

## REQ-X4 — Canonical action/arg matrix doc (P2 — phụ thuộc REQ-X3)

**Hiện trạng:** nowing `PLATFORM_TOOL_MAP` đoán sai action (`chotot→posts`, `masothue→lookup`, `linkedin→company`) — thực tế chỉ có `search_listings`/`search`/`company_profile`/`detail`/`search_jobs`/`search_products`…

**Yêu cầu:** 1 bảng canonical `platform → {action, requiredArgs}` (có thể derive từ REQ-X3 `x_actions_list`). Đây là nguồn truth duy nhất 2 bên dùng — nowing validate `SocialMonitoredTarget.platform` + dispatch theo nó.

**Done khi:** nowing build được mapper hoàn toàn từ `x_actions_list` mà không hard-code action name nào.

---

## Phụ thuộc & non-goals

- **Không yêu cầu REST endpoint** — contract là MCP + Redis Stream (đã chốt AD-SOC-4).
- **Giữ `x_crawl_post`/`x_crawl_comments_tree`** — vẫn là fallback cho post-detail; `x_scrape` bổ sung, không thay thế.
- **Account/proxy:** nowing truyền `accountId`/`proxyUrl` trong args; XActions quản pool (AD-SOC-3/11). Không đổi.
- **Checkpoint/ACL:** nowing không truyền cursor — ACL epic 25.5/25.6 đã lo. Đảm bảo `x_scrape` không bắt buộc cursor.

## Traceability

| REQ | Spine AD | Spec CAP | Nowing phụ thuộc (Epic 36 story) |
|---|---|---|---|
| REQ-X1 | AD-1, AD-2 | CAP-1 | 36.1 (fallback), 36.6 (migrate to x_scrape) |
| REQ-X2 | AD-3, AD-4 | CAP-2, CAP-5 | 36.4 (single-writer), 36.7 (consumer) |
| REQ-X3 | AD-6, AD-7 | CAP-3 | 36.5, 36.6 |
| REQ-X4 | AD-2, AD-7 | CAP-1, CAP-3 | 36.6 |

**Thứ tự đề xuất:** REQ-X1 + REQ-X3 trước (unblock dispatch), REQ-X2 sau (data plane). REQ-X4 derive từ X3.
