---
epic: 40
title: "Epic 40 — Unified Scraper Gateway & Trinity Pipeline Optimization Retrospective"
date: 2026-10-06
participants:
  - Luisphan (Project Lead)
  - Orchestrator (Autonomous Agent)
stories_total: 5
stories_done: 5
stories_fully_verified: 3
status: complete
verdict: accepted-with-open-items
---

# Retrospective — Epic 40: Unified Scraper Gateway & Trinity Pipeline Optimization

**Ngày:** 2026-10-06  
**Epic:** 40 — Unified Scraper Gateway & Trinity Pipeline Optimization  
**Commit:** `118710e6d` (squash, +2044/−56, 26 files)  
**Trạng thái:** 5/5 stories `done` — **ACCEPTED WITH OPEN ITEMS**

---

## 1. Epic Review

### Tổng quan

Epic 40 "Trinity Master Integration" nhằm biến Nowing thành tầng điều phối/gateway duy nhất cho cào dữ liệu thông qua Medirus (`:3001`), đóng gói Scraper Playground thành thin proxy có billing gate, decommission 22 internal crawler để giảm tải bảo trì + slim Docker ≥400MB, cắm tầng Jev (Epic 39) vào stream ingest để dedup + lọc PII, và gia cố timeout cho kết nối ChainLens S2S.

### Story Summary

| Story | Title | Spec Status | Đánh giá AC | Ghi chú |
|---|---|---|---|---|
| **40.1** | Medirus Gateway Client & Streamable-HTTP Cutover | done (body: in-review) | ✅ ĐẠT | `circuit_breaker.py` (188d) + `mcp_client.py` wrap; 3 trạng thái CLOSED/OPEN/HALF_OPEN, 4s probe, 85/85 test pass |
| **40.2** | Scraper Playground Thin Proxy & Workspace Billing Gate | done | ⚠️ PARTIAL | Chỉ **topcv** qua `make_medirus_executor`; **15 executors vẫn gọi local scrape**, 3 OTHER. Mục tiêu "Medirus sole engine" chưa đạt |
| **40.3** | Decommission 22 Crawlers & Docker Slim ≥400MB | done | ⚠️ PARTIAL | Chỉ *xác nhận* không phụ thuộc playwright/selenium trong pyproject; **chưa xóa 26 platform dirs**, chưa đo Docker image giảm ≥400MB |
| **40.4** | Jev Stream Dedup & PII Guardrail Pipeline | done | ✅ ĐẠT | `jev_guardrails.py` (`sanitize_pii_content` redact CCCD/CMND) + `social_stream_worker.py`; 5/5 test pass |
| **40.5** | ChainLens S2S Circuit Breaker & Timeout Hardening | done | ✅ ĐẠT | `asyncio.timeout(5.0)` + HTTP 504 fail-fast trong `chainlens_internal.py`; 2/2 test pass |

**Kết quả:** 3/5 stories đạt đầy đủ AC; 2/5 (40.2, 40.3) ở trạng thái "đặt nền móng/pattern" chứ chưa hoàn tất phạm vi.

---

## 2. What Went Well

1. **Resilience architecture đặt đúng chỗ:**
   - Circuit Breaker (`MedirusCircuitBreaker`) 3 trạng thái chuẩn, `_probe_in_flight` đảm bảo chỉ 1 probe trong HALF_OPEN, `stats` trả immutable snapshot, `reset()` cho test sạch.
   - ChainLens S2S có hard deadline 5.0s + HTTP 504 fail-fast — đúng intent chống cascade/hang giữa hai service.
   - Jev guardrail redact CCCD(12)/CMND(9) → `[REDACTED_ID]` trước khi bóc entity — bảo vệ PII đúng Nghị định 13/2023 PDPD.

2. **Backward compatibility được giữ nghiêm:**
   - `get_shared_client()` / `release_shared_client_for_loop()` / `_LOOP_CLIENTS` semantics không đổi — không phá hợp đồng với caller hiện có.
   - Playground REST contract `POST /workspaces/{id}/scrapers/{platform}/{verb}` giữ nguyên; UI `nowing_web` 100% không đổi.
   - Fallback sang tool legacy (`x_get_profile`, `x_crawl_post`…) khi `x_scrape` chưa sẵn sàng — hợp lý vì Medirus Epic 46 chưa ship `x_scrape`.

3. **Billing gate chặt:** `gate_capability` soft-lock → `charge_capability` debit → refund khi anti-bot/failure. Đúng nguyên tắc `wallet_credit.py`.

---

## 3. Divergence / Gaps phát hiện (bằng chứng trên code)

| # | Vấn đề | Bằng chứng | Mức độ |
|---|---|---|---|
| **G1** | Story 40.2 chỉ hoàn tất 1/22 platform | `grep make_medirus_executor` → chỉ `topcv`; 15 executors LOCAL (`batdongsan, cafef, chotot, indeed, instagram, itviec, masothue, muaban_bds, reddit, tiktok, vietnamworks, vietstock, walmart, youtube`), 3 OTHER | Cao |
| **G2** | Story 40.3 chưa decommission thật | `ls app/proprietary/platforms/` vẫn còn **26 dirs**; mục tiêu "xóa fetch/crawler, giữ schema/parser" và "Docker ≥400MB" chưa được chứng minh bằng build/measurement | Cao |
| **G3** | Feature-flag drift | Spec 40.1 nói `NOWING_MEDIRUS_USE_V2` nhưng code dùng `MEDIRUS_USE_UNIFIED_DISPATCH` (`entities.py:106`, default `false`) — flag trong spec không tồn tại | Trung bình (doc drift) |
| **G4** | `PlatformError` không tồn tại | Spec yêu cầu `PlatformError(XACT_4001)` nhưng implement `MedirusMcpError`; `grep "class PlatformError"` rỗng — convention deviation, đã ghi residual risk | Thấp |
| **G5** | ~~`x_scrape` chưa tồn tại trên Medirus~~ → **ĐÃ GIẢI QUYẾT (2026-10-06):** kiểm tra repo Medirus cho thấy Epic 46 đã hoàn thành (`epic-46: done`, commit `51508005`), tool `x_scrape` + `x_actions_list` đã ship tại `src/mcp/server.js:2972/2950` với DESCRIPTORS phủ batdongsan/topcv/chotot/masothue/vietnamworks/tiktok/reddit/instagram/youtube/linkedin/zalo/shopee…; 18/18 test pass. Cutover giờ có thể **active thật** | Đã giải quyết |
| **G6** | Spec metadata lệch | spec-40-1 front-matter `status: done` nhưng Auto Run body ghi `Status: in-review` | Thấp (hygiene) |

---

## 4. Action Items

| # | Action Item | Target | Priority | Status |
|---|---|---|---|---|
| **AI-40.1** | ~~Hoàn thiện thin-proxy cho 15 executors~~ → **ĐÃ XONG (2026-10-06, chiến lược proxy-first + local-fallback):** thêm `medirus_scrape_or_local()` + `_ProxyArgs` vào `medirus_proxy.py` — khi `MEDIRUS_USE_UNIFIED_DISPATCH=true` thử `medirus_scrape` trước, `tool_not_found`/connectivity → fallback local, `MEDIRUS_4001`/`XACT_4001` (circuit open) → fail-fast không hammer local. Đã chuyển **8 executors có descriptor trên Medirus**: `batdongsan, chotot, masothue, vietnamworks, reddit, tiktok, instagram, youtube` (giữ nguyên anti-bot escalation, error mapping, billing, chainlens ingest). **7 executors giữ local vì Medirus chưa có descriptor**: `cafef, indeed, itviec, muaban_bds, vietstock, walmart` (+3 OTHER: amazon/google_maps/google_search). 922/922 test capabilities pass; ruff clean | 40.2 — medirus_proxy.py + 8 executors | P0 | done (proxy-first + fallback; hard-cut chờ Medirus phủ 7 platform còn lại) |
| **AI-40.2** | Decommission 22 crawler → **DECIDED — WON'T DO AS SPECCED (2026-10-08, quyết định của PM):** giữ `app/proprietary/platforms/` làm **shared local scrape engine** vĩnh viễn. Lý do: (1) AI-40.1 ship kiến trúc proxy-first **+ local-fallback** (`medirus_scrape_or_local()` cố tình fallback local khi `tool_not_found`/connectivity) — xóa `platforms/` = xóa chính fallback, mâu thuẫn thiết kế vừa ship; (2) ~400MB thật sự nằm ở `scrapling install` (patchright Chromium) + Xvfb ở `nowing_backend/Dockerfile:126-129`, không phải 26 dirs (3.6MB source); (3) zero local scrape bất khả thi hôm nay — Medirus thiếu descriptor cho `cafef, indeed, itviec, muaban_bds, vietstock, walmart, amazon, google_maps, google_search`, `lead_intelligence/adapters` (86 file) + `web_crawler/site_crawler.py` gọi `scrape_*` trực tiếp, telegram/muasamcong không phải dạng scraper. Điều kiện revisit: Medirus đạt descriptor parity VÀ team chấp nhận bỏ local-fallback (hoặc tách fetch sang worker image riêng) → lúc đó lập epic mới, không phải open item | 40.3 — re-scoped | P0 | decided (won't-do; platforms/ = shared engine + fallback) |
| **AI-40.3** | Đồng bộ tên feature flag → **ĐÃ XONG (2026-10-08):** chốt canonical `MEDIRUS_USE_UNIFIED_DISPATCH`; spec 40.1 đã hiệu chỉnh (mọi `NOWING_MEDIRUS_USE_V2`/`XACTIONS_*` → `MEDIRUS_*`), không thêm alias | 40.1 — config/spec | P2 | done |
| **AI-40.4** | Chuẩn hóa error contract → **ĐÃ XONG (2026-10-08):** chốt `MedirusMcpError` là contract chuẩn (`PlatformError` không tồn tại trong codebase — không tạo class mới); spec 40.1 đã hiệu chỉnh toàn bộ. `XACT_4001`/`MEDIRUS_4001` đều được normalize ở client | 40.1 — error envelope | P2 | done |
| **AI-40.5** | ~~Theo dõi Medirus Epic 46~~ → **ĐÃ XONG (2026-10-06):** Epic 46 đã hoàn thành phía Medirus (`epic-46: done`, `medirus_scrape` + `medirus_list` đã ship — tool names đổi canonical `x_*`→`medirus_*` ở commit `f079d573`, shim legacy vẫn nhận `x_*`). **Verify live đã xong (2026-10-08):** daemon `localhost:3333/mcp` trả 12 tools `medirus_*`; call `medirus_scrape{platform:masothue,action:search,q:'0100109106'}` trả `success:true` 10 records /3.4s; nowing `MedirusMcpClient.call_tool('medirus_list')` OK. Còn lại: bật `MEDIRUS_USE_UNIFIED_DISPATCH=true` trong env deploy | Cross-repo handshake | P1 | resolved (verify live còn lại) |
| **AI-40.6** | Sửa metadata spec-40-1: Auto Run `in-review` → `done` → **ĐÃ XONG:** frontmatter spec-40-1 `status: done` | 40.1 — spec hygiene | P3 | done |

---

## 5. Epic Close Gate Decision

- **Verdict:** ⚠️ **ACCEPTED WITH OPEN ITEMS**
- **Lý do:**
  - 3/5 stories (40.1, 40.4, 40.5) đạt đầy đủ AC với test coverage tốt và resilience đặt đúng chỗ — nền móng Trinity đã được đặt vững.
  - 2/5 stories (40.2, 40.3) ở trạng thái **đặt pattern** chứ chưa hoàn tất phạm vi tuyên bố ("22 platform", "Docker ≥400MB"). Đây là khác biệt giữa "infrastructure ready" và "mission accomplished" — cần action items P0 để đóng gap.
  - Không `rejected` vì code shipped ổn định, backward-compat giữ nguyên, và phần còn lại chủ yếu là *mở rộng pattern* + *dọn dẹp* + *external dependency* (Medirus Epic 46) chứ không phải lỗi thiết kế.

**Điều kiện đóng hoàn toàn Epic 40:** AI-40.1 done; AI-40.2 decided (re-scoped — xem bảng trên); AI-40.3/40.4/40.6 done (spec hiệu chỉnh theo canonical `MEDIRUS_*`/`MedirusMcpError`); AI-40.5 đã verify live ở tool-level (`medirus_scrape` call thật qua daemon :3333 OK). Việc duy nhất còn lại là **ops action**: bật flag `MEDIRUS_USE_UNIFIED_DISPATCH=true` trong env deploy. Mục tiêu "Docker ≥400MB" của Story 40.3 chính thức **hủy** — giá trị đo được (deploy image size) không xứng chi phí cross-repo + mất fallback resilience.
