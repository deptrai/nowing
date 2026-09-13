---
id: SPEC-xactions-connection
companions:
  - '../planning-artifacts/architecture/architecture-Nowing-2026-09-13/ARCHITECTURE-SPINE.md'
sources: []
---

> **Canonical contract.** This SPEC and the files in `companions:` are the complete, preservation-validated contract for what to build, test, and validate. The adopted architecture spine carries the invariants (AD-1..10, AD-SOC-1..11) and the How; this kernel carries the What/Why.

# Kết nối Nowing ↔ XActions

## Why

Nowing ủy quyền toàn bộ scraping đa nền-tảng cho XActions (AD-SOC-1), nhưng kết nối hiện tại gãy ở 4 điểm đã kiểm chứng trên code: `x_scrape` generic chưa tồn tại phía XActions nên 9 loại VN-domain target fail `tool_not_found`; 15 crawler non-social không emit vào Redis Stream nên data kẹt ở MCP 30-record cap; `PLATFORM_TOOL_MAP` của nowing sai cả tên action lẫn tên arg so với descriptor thật; và stream event thiếu `workspace_id`/`content` khiến consumer drop 100% bài hợp lệ. Đây là pain vận hành — SDR/lead-gen teams không nhận được lead từ VN domain dù pipeline đã wire Celery beat đầy đủ.

## Capabilities

- **CAP-1**
  - **intent:** Nowing ra lệnh scrape bất kỳ platform/action nào qua một tool MCP generic duy nhất, không cần biết tên 150+ per-platform tool.
  - **success:** Mọi `SocialMonitoredTarget.platform` (gồm chotot, shopee, topcv, masothue, batdongsan, vietnamworks, linkedin, b2b, tiktok, zalo) dispatch thành công — không `tool_not_found`, không `XACT_4001` do sai tên action.

- **CAP-2**
  - **intent:** Dữ liệu scrape chảy liên tục cường độ cao qua Redis Stream, không qua MCP response.
  - **success:** Mọi crawler (kể cả VN/non-social) emit thin event vào `stream:social:raw_posts`; consumer nowing tạo `social_posts` + `Lead` với 0% drop trên event hợp lệ (đủ `workspace_id` + `content_snippet`).

- **CAP-3**
  - **intent:** Nowing resolve `platform → {action, requiredArgs}` động từ catalog canonical của XActions.
  - **success:** XActions thêm/đổi action không cần sửa nowing; action không tồn tại → target đánh dấu `unsupported` thay vì retry vô hạn.

- **CAP-4**
  - **intent:** XActions chỉ cào phần gap thời gian (delta), không re-crawl toàn bộ mỗi scheduled run.
  - **success:** Run thứ 2 của cùng target gọi ít request hơn run 1 (early-termination khi page toàn duplicate); DB không nhận duplicate.

- **CAP-5**
  - **intent:** Nhiều workspace/target ingest đồng thời qua một consumer `nowing` duy nhất, tenant phân biệt bằng args.
  - **success:** N workspace chạy song song không tăng session/RAM tuyến tính; mỗi post gán đúng `workspace_id` của nó.

- **CAP-6**
  - **intent:** Nowing tôn trọng governor/quota của XActions và phản ứng thống nhất với error envelope.
  - **success:** `XACT_4291` → retry đúng `retry_after`; hibernation/proxy-exhausted → pause target; không chuỗi account chết vì over-rate.

## Constraints

- Transport đã chốt (kế thừa AD-SOC-4): MCP streamable-http `:3001` = control plane, Redis Stream = data plane. Không chuyển sang REST — `/api/platform` cần JWT user, `/api/ai` cần x402 payment, cùng governor nên không tăng throughput.
- `stream:social:raw_posts` có **một writer duy nhất là XActions**; nowing chỉ consume. `ingest_raw_post_to_stream` hiện tại của nowing phải loại bỏ.
- Stream event schema = **snake_case** theo `SocialPostEvent` của consumer: `{platform, external_post_id, content_snippet, author_id, author_name, post_url, crawled_at, storage_ref, target_id, workspace_id, schema_version}`. Thiếu `workspace_id`/`content_snippet` → drop.
- `action`/`args` trong `x_scrape` dùng **tên canonical từ `x_actions_list`** (`search_listings`, `search_products`, `search_jobs`, `detail`, `company_profile`…) — nowing không tự đặt `posts`/`lookup`/`company`.
- `x_crawl_post` fallback bắt buộc truyền `platform`; `x_scrape.args` là object lồng (không phẳng).
- MCP client nowing là **loop-scoped cache** (Celery `new_event_loop()` + `loop.close()` mỗi task), không phải process singleton.
- Idempotency nowing: `UNIQUE(workspace_id, platform, external_post_id)` — scoped per workspace.

## Non-goals

- Nowing không re-implement scraper, proxy pool, fingerprint/signer — domain của XActions (AD-SOC-1/2/3).
- Không build REST internal endpoint mới; không thay MCP bằng REST.
- Không truyền full content qua stream thin event — chỉ `content_snippet` ≤4000 chars + `storage_ref`; full payload qua artifact.
- Không per-user MCP session, không per-workspace `X-Consumer-Id` — một consumer `nowing` duy nhất.

## Success signal

Một `SocialMonitoredTarget` VN-domain (vd `chotot_category`) được nowing dispatch qua `x_scrape`, XActions emit thin event đủ `workspace_id`+`content_snippet` vào stream, consumer nowing tạo `social_post` + `Lead` đúng workspace — end-to-end không drop, không `tool_not_found`, không cần sửa tay `PLATFORM_TOOL_MAP` khi XActions đổi action.

## Assumptions

- `ingest_raw_post_to_stream` của nowing chỉ là bridge tạm chờ XActions emit — giả định không còn caller cần nó sau khi single-writer áp dụng.

## Open Questions

- Artifact >100 records: nowing đọc qua shared volume `XACTIONS_ARTIFACT_ROOT` hay presigned URL? (Q1)
- Consumer group name + DLQ `stream:social:failed` + `schema_version` đã thống nhất 2 đầu chưa? (Q2)
- Topo deploy prod: `xactions` cùng network nowing (http nội bộ) hay cross-cluster cần TLS? (Q3)
