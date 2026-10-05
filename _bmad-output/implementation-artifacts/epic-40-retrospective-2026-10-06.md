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

Epic 40 "Trinity Master Integration" nhằm biến Nowing thành tầng điều phối/gateway duy nhất cho cào dữ liệu thông qua XActions (`:3001`), đóng gói Scraper Playground thành thin proxy có billing gate, decommission 22 internal crawler để giảm tải bảo trì + slim Docker ≥400MB, cắm tầng Jev (Epic 39) vào stream ingest để dedup + lọc PII, và gia cố timeout cho kết nối ChainLens S2S.

### Story Summary

| Story | Title | Spec Status | Đánh giá AC | Ghi chú |
|---|---|---|---|---|
| **40.1** | XActions Gateway Client & Streamable-HTTP Cutover | done (body: in-review) | ✅ ĐẠT | `circuit_breaker.py` (188d) + `mcp_client.py` wrap; 3 trạng thái CLOSED/OPEN/HALF_OPEN, 4s probe, 85/85 test pass |
| **40.2** | Scraper Playground Thin Proxy & Workspace Billing Gate | done | ⚠️ PARTIAL | Chỉ **topcv** qua `make_xactions_executor`; **15 executors vẫn gọi local scrape**, 3 OTHER. Mục tiêu "XActions sole engine" chưa đạt |
| **40.3** | Decommission 22 Crawlers & Docker Slim ≥400MB | done | ⚠️ PARTIAL | Chỉ *xác nhận* không phụ thuộc playwright/selenium trong pyproject; **chưa xóa 26 platform dirs**, chưa đo Docker image giảm ≥400MB |
| **40.4** | Jev Stream Dedup & PII Guardrail Pipeline | done | ✅ ĐẠT | `jev_guardrails.py` (`sanitize_pii_content` redact CCCD/CMND) + `social_stream_worker.py`; 5/5 test pass |
| **40.5** | ChainLens S2S Circuit Breaker & Timeout Hardening | done | ✅ ĐẠT | `asyncio.timeout(5.0)` + HTTP 504 fail-fast trong `chainlens_internal.py`; 2/2 test pass |

**Kết quả:** 3/5 stories đạt đầy đủ AC; 2/5 (40.2, 40.3) ở trạng thái "đặt nền móng/pattern" chứ chưa hoàn tất phạm vi.

---

## 2. What Went Well

1. **Resilience architecture đặt đúng chỗ:**
   - Circuit Breaker (`XActionsCircuitBreaker`) 3 trạng thái chuẩn, `_probe_in_flight` đảm bảo chỉ 1 probe trong HALF_OPEN, `stats` trả immutable snapshot, `reset()` cho test sạch.
   - ChainLens S2S có hard deadline 5.0s + HTTP 504 fail-fast — đúng intent chống cascade/hang giữa hai service.
   - Jev guardrail redact CCCD(12)/CMND(9) → `[REDACTED_ID]` trước khi bóc entity — bảo vệ PII đúng Nghị định 13/2023 PDPD.

2. **Backward compatibility được giữ nghiêm:**
   - `get_shared_client()` / `release_shared_client_for_loop()` / `_LOOP_CLIENTS` semantics không đổi — không phá hợp đồng với caller hiện có.
   - Playground REST contract `POST /workspaces/{id}/scrapers/{platform}/{verb}` giữ nguyên; UI `nowing_web` 100% không đổi.
   - Fallback sang tool legacy (`x_get_profile`, `x_crawl_post`…) khi `x_scrape` chưa sẵn sàng — hợp lý vì XActions Epic 46 chưa ship `x_scrape`.

3. **Billing gate chặt:** `gate_capability` soft-lock → `charge_capability` debit → refund khi anti-bot/failure. Đúng nguyên tắc `wallet_credit.py`.

---

## 3. Divergence / Gaps phát hiện (bằng chứng trên code)

| # | Vấn đề | Bằng chứng | Mức độ |
|---|---|---|---|
| **G1** | Story 40.2 chỉ hoàn tất 1/22 platform | `grep make_xactions_executor` → chỉ `topcv`; 15 executors LOCAL (`batdongsan, cafef, chotot, indeed, instagram, itviec, masothue, muaban_bds, reddit, tiktok, vietnamworks, vietstock, walmart, youtube`), 3 OTHER | Cao |
| **G2** | Story 40.3 chưa decommission thật | `ls app/proprietary/platforms/` vẫn còn **26 dirs**; mục tiêu "xóa fetch/crawler, giữ schema/parser" và "Docker ≥400MB" chưa được chứng minh bằng build/measurement | Cao |
| **G3** | Feature-flag drift | Spec 40.1 nói `NOWING_XACTIONS_USE_V2` nhưng code dùng `XACTIONS_USE_UNIFIED_DISPATCH` (`entities.py:106`, default `false`) — flag trong spec không tồn tại | Trung bình (doc drift) |
| **G4** | `PlatformError` không tồn tại | Spec yêu cầu `PlatformError(XACT_4001)` nhưng implement `XActionsMcpError`; `grep "class PlatformError"` rỗng — convention deviation, đã ghi residual risk | Thấp |
| **G5** | ~~`x_scrape` chưa tồn tại trên XActions~~ → **ĐÃ GIẢI QUYẾT (2026-10-06):** kiểm tra repo XActions cho thấy Epic 46 đã hoàn thành (`epic-46: done`, commit `51508005`), tool `x_scrape` + `x_actions_list` đã ship tại `src/mcp/server.js:2972/2950` với DESCRIPTORS phủ batdongsan/topcv/chotot/masothue/vietnamworks/tiktok/reddit/instagram/youtube/linkedin/zalo/shopee…; 18/18 test pass. Cutover giờ có thể **active thật** | Đã giải quyết |
| **G6** | Spec metadata lệch | spec-40-1 front-matter `status: done` nhưng Auto Run body ghi `Status: in-review` | Thấp (hygiene) |

---

## 4. Action Items

| # | Action Item | Target | Priority | Status |
|---|---|---|---|---|
| **AI-40.1** | ~~Hoàn thiện thin-proxy cho 15 executors~~ → **ĐÃ XONG (2026-10-06, chiến lược proxy-first + local-fallback):** thêm `xactions_scrape_or_local()` + `_ProxyArgs` vào `xactions_proxy.py` — khi `XACTIONS_USE_UNIFIED_DISPATCH=true` thử `x_scrape` trước, `tool_not_found`/connectivity → fallback local, `XACT_4001` (circuit open) → fail-fast không hammer local. Đã chuyển **8 executors có descriptor trên XActions**: `batdongsan, chotot, masothue, vietnamworks, reddit, tiktok, instagram, youtube` (giữ nguyên anti-bot escalation, error mapping, billing, chainlens ingest). **7 executors giữ local vì XActions chưa có descriptor**: `cafef, indeed, itviec, muaban_bds, vietstock, walmart` (+3 OTHER: amazon/google_maps/google_search). 922/922 test capabilities pass; ruff clean | 40.2 — xactions_proxy.py + 8 executors | P0 | done (proxy-first + fallback; hard-cut chờ XActions phủ 7 platform còn lại) |
| **AI-40.2** | Decommission 22 crawler → **BLOCKED (2026-10-06, phụ thuộc thật):** `grep from app.proprietary.platforms` ngoài `capabilities/` = **86 file** — chủ yếu `lead_intelligence/adapters/` (batdongsan, chotot, itviec, masothue, muaban_bds, muasamcong, telegram, topcv, vietnamworks) + services + celery tasks gọi `scrape_*` trực tiếp, KHÔNG qua capability executor. Xóa platform dirs sẽ phá lead-generation (vừa verify live 2026-10-02). **Điều kiện decommission:** route lead adapters qua XActions trước, hoặc giữ module `platforms/` như thư viện scrape dùng chung cho cả executor + lead adapter. Docker ≥400MB chưa đo được | 40.3 — blocked by lead_intelligence coupling | P0 | blocked (needs lead-adapter reroute) |
| **AI-40.3** | Đồng bộ tên feature flag: quyết định chuẩn `XACTIONS_USE_UNIFIED_DISPATCH` (đang dùng) và cập nhật spec 40.1, hoặc thêm `NOWING_XACTIONS_USE_V2` alias | 40.1 — config/spec | P2 | open |
| **AI-40.4** | Chuẩn hóa error contract: thêm `PlatformError(XACT_4001)` hoặc cập nhật spec để dùng `XActionsMcpError` nhất quán | 40.1 — error envelope | P2 | open |
| **AI-40.5** | ~~Theo dõi XActions Epic 46~~ → **ĐÃ XONG (2026-10-06):** Epic 46 đã hoàn thành phía XActions (`epic-46: done`, `x_scrape` + `x_actions_list` đã ship, 18/18 test pass). Việc còn lại: bật `XACTIONS_USE_UNIFIED_DISPATCH=true` + verify end-to-end cutover live khi chạy XActions daemon `:3001` | Cross-repo handshake | P1 | resolved (verify live còn lại) |
| **AI-40.6** | Sửa metadata spec-40-1: Auto Run `in-review` → `done` cho nhất quán | 40.1 — spec hygiene | P3 | open |

---

## 5. Epic Close Gate Decision

- **Verdict:** ⚠️ **ACCEPTED WITH OPEN ITEMS**
- **Lý do:**
  - 3/5 stories (40.1, 40.4, 40.5) đạt đầy đủ AC với test coverage tốt và resilience đặt đúng chỗ — nền móng Trinity đã được đặt vững.
  - 2/5 stories (40.2, 40.3) ở trạng thái **đặt pattern** chứ chưa hoàn tất phạm vi tuyên bố ("22 platform", "Docker ≥400MB"). Đây là khác biệt giữa "infrastructure ready" và "mission accomplished" — cần action items P0 để đóng gap.
  - Không `rejected` vì code shipped ổn định, backward-compat giữ nguyên, và phần còn lại chủ yếu là *mở rộng pattern* + *dọn dẹp* + *external dependency* (XActions Epic 46) chứ không phải lỗi thiết kế.

**Điều kiện đóng hoàn toàn Epic 40:** hoàn thành AI-40.1 + AI-40.2 (đạt AC gốc) và AI-40.5 khi XActions `x_scrape` sẵn sàng.
