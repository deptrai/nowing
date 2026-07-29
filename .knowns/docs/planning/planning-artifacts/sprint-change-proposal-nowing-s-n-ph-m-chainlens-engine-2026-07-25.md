---
title: Sprint Change Proposal — Nowing = Sản phẩm, ChainLens = Engine (2026-07-25)
description: ''
createdAt: '2026-07-28T12:47:48.265Z'
updatedAt: '2026-07-28T15:17:33.288Z'
tags:
  - bmad
  - bmad-source-bmad-output-planning-artifacts-sprint-change-proposal-2026-07-25-chainlens-engine-boundary-md
---

# Sprint Change Proposal — Nowing = Sản phẩm, ChainLens = Engine (2026-07-25)

**Workflow:** `bmad-correct-course` (batch mode)
**Project:** Nowing
**Date:** 2026-07-25
**Author:** Mary (Business Analyst) + Luisphan (PO)
**Status:** ✅ **ADOPTED** (PO Luisphan, 2026-07-25) — xem §8 cho 4 quyết định (D1–D4)

**Loại thay đổi:** Strategic pivot / market change + cross-repo misalignment

**Đối ứng với:** `chainlens-research/_bmad-output/planning-artifacts/sprint-change-proposal-2026-07-25-v4-nowing-microservice.md` (✅ ADOPTED) và `architecture/ADR-CHAINLENS-AS-NOWING-MICROSERVICE.md` (✅ ACCEPTED)

**Artifacts bị ảnh hưởng:**
- `_bmad-output/planning-artifacts/prds/prd-Nowing-2026-07-22/prd.md`
- `_bmad-output/planning-artifacts/epics.md`
- `_bmad-output/planning-artifacts/architecture/architecture-Nowing-2026-07-22/ARCHITECTURE-SPINE.md`
- `_bmad-output/implementation-artifacts/sprint-status.yaml`
- (thứ cấp) `README.md`, `docs/`, `docker/`, `.env.example`

---

## 1. Issue Summary

ChainLens đã tự tái định vị thành **deep-research microservice cho Nowing** (SCP v4 + ADR, ADOPTED 2026-07-25, ghi PO Luisphan). Nowing **chưa có quyết định đối ứng**: trong PRD/epics/architecture-spine của Nowing, ChainLens vẫn là `FR-24` — *một MCP tool*, nằm trong **Epic 2 "Connectors"**, ngang hàng scraper Reddit/YouTube, đã đóng `2-4-chainlens-research-mcp-tool: done`.

Song song, PO đã **loại** hướng "research app giống Perplexity + bán research data giống Exa + subscription-vì-rẻ" với hai lý do chịu lực:
1. **Không có owned index** → không thể bán data kiểu Exa. `epic-26-gate-tracking.md`: **0/7 gates passing**. ChainLens là orchestrator *mua* từ Exa/Tavily/Brave — bán lại thứ mình đang mua, ở giá đã commoditize (~$7/1k), đấu specialist có vốn (Tavily→Nebius $400M, 2/2026).
2. **Không có GTM muscle** (PO xác nhận 2026-07-24) → localization-wedge và consumer-parity đều cần cơ bắp bán/community mà team không có. `direction-decision-brief-2026-07-24.md` §9: *"Đừng chọn chiến lược cần cơ bắp bạn không có."* Decision matrix §10.3: Option B (OSS + hosted) thắng **3.75**; global-consumer-OSS = red ocean (Perplexity bỏ paywall Comet FREE; Perplexica/Vane = bản sinh đôi ChainLens).

**Quyết định đã chốt:** đường **OSS/PLG-led**. **Nowing = sản phẩm** (bề mặt người dùng, phân phối, billing, account). **ChainLens = engine** phía sau, không bán riêng. Lý do trả tiền = **memory + provenance + self-host/privacy + integration depth**, KHÔNG phải "rẻ hơn" và KHÔNG phải "bán data".

### 1.1 Bằng chứng đã thu (verifiable)

**Tài liệu:**
- `chainlens-research/.../sprint-change-proposal-2026-07-25-v4-nowing-microservice.md` — ✅ ADOPTED; boundary + contract; dropped Epic 34 billing / 40-9 onboarding / 41-1 social / 40-7 end-user auth / standalone distribution; *"Standalone Exa-like sale: ⏸️ defer"*.
- `chainlens-research/.../architecture/ADR-CHAINLENS-AS-NOWING-MICROSERVICE.md` — ✅ ACCEPTED; bảng IN/OUT boundary.
- `chainlens-research/.../epic-26-gate-tracking.md` — owned index **DEFERRED, 0 of 7 gates passing**; Gate 3 & 6: *"infrastructure doesn't exist"*.
- `chainlens-research/.../research/chainlens-direction-decision-brief-2026-07-24.md` §9–§11 — team capability = binding constraint; corpus moat không đáng xây (SO pay-per-crawl 2/2026 + a16z "Empty Promise of Data Moats"); MCP-server-as-product hầu như không kiếm được tiền.
- `chainlens-research/.../nfr6-final-20-8-v2-postfix.md` — verdict **FAIL**: Ask avg **57–136s** (target ≤8s), Reason 50–160s (≤35s), Research quality **198s** (>180s), citation **50–88%** (≥95%). Root cause: *"ag/ reasoning models inherently slow — model choice tradeoff, not a bug."*
- Nowing `epics.md` L68 — ChainLens nằm trong Epic 2 Connectors, `[DONE]`, cùng nhóm scraper.

**Code (verified 2026-07-25):**

| Phát hiện | Vị trí | Hệ quả |
|---|---|---|
| `CHAINLENS_QUERY_MICROS_PER_CALL = 5000` → **$0.005 phẳng/call**, mọi mode | `nowing_backend/app/config/__init__.py:806` | Cost basis sai |
| `mode` default = **`"quality"`**; `sources` default `["web","academic"]` | `app/capabilities/chainlens/research/schemas.py:38,42` | Nowing mặc định gọi mode đắt nhất |
| ChainLens target cost: balanced **$0.0048** / quality **$0.0105** / deep **$0.0164** | ChainLens PRD §7.1 | **Under-meter 2.1× (quality), 3.3× (deep)** |
| Số trên tính trên **DeepSeek stack chưa vào prod**; `DEFAULT_MODEL_POLICY` = 100% `ag/` Gemini (output đắt hơn DeepSeek ~3.5×) | ChainLens `model-policy.ts` "DEEPSEEK GATE" | Gap rộng thêm sau Gemini runway |
| `grep -rn "costDollars\|cost_dollars" nowing_backend/` → **0 hits** | — | Không có cost thật để meter |
| Chỉ raise `CHAINLENS_TIMEOUT` sau 300s; **không có fallback** | `app/capabilities/chainlens/research/executor.py:192-198` | ChainLens chết → research hard-fail, dù Nowing có hybrid search riêng |
| Wired 2 đường, cả hai coi là "một tool": capability `chainlens.research` (`BillingUnit.CHAINLENS_QUERY`) + subagent `subagents/builtins/chainlens/` | `.../research/definition.py`, `.../subagents/builtins/chainlens/tools/index.py` | Governance sai tầng |

**Kết luận đo lường:** đây không chỉ là lệch tài liệu. Có **ba lỗi thương mại đang chạy trong production path**: cost basis sai 2–3×, không parse cost thật, không có degradation. Và **một hệ quả sản phẩm chưa được ghi ở bất kỳ PRD nào**: latency deep-research hiện **chưa validated** (baseline cũ FAIL nhưng phases 1-7 tối ưu đã ship mà chưa đo lại) → Nowing phải thiết kế đường **async deliverable** làm sàn, mở sync sau khi có số đo. Xem **§3.5** cho cải chính và framing hai trạng thái.

---

## 2. Epic Impact Assessment

| Check | Kết luận |
|---|---|
| **2.1** Epic hiện tại còn hoàn thành được? | **Có.** Không epic nào chết. `2-4` đã ship tool thật — giữ nguyên làm lịch sử, không revert. |
| **2.2** Thay đổi cấp epic | ChainLens **sai chỗ chứa** (Epic 2 Connectors). → **Thêm Epic 9** *(đặt tên 2026-07-25: "Deep Research đáng tin cậy — không vỡ, không treo, tính phí đúng"; tên ban đầu "Deep-Research Engine Integration" bị readiness Q-1 đánh là technical epic)*. Không sửa Epic 2 (đã `done`); **re-bind FR-24** sang Epic 9. |
| **2.3** Epic tương lai bị ảnh hưởng | **Epic 8** (ops/cost): `8-7-auto-extract-spend-budget-cap` = `ready-for-dev` — cùng họ vấn đề cost-control, nên chạy song song 9.2. **Epic 3**: `3-9-memory-recall-eval-gate` = `review` — không xung đột. |
| **2.4** Epic nào vô hiệu / cần mới? | Không vô hiệu epic nào. Cần **1 epic mới (Epic 9)**. |
| **2.5** Đổi thứ tự ưu tiên? | **Có.** `9.1a` (degradation) và `9.2` (cost metering) phải **trước** mọi việc pricing/monetization — định giá khi chưa biết cost là đoán. *(Story `9.1` sau đó đã tách thành `9.1a` degradation + `9.1b` contract guard — readiness Q-3, 2026-07-25.)* |

### Epic 9 — Deep Research đáng tin cậy: không vỡ, không treo, tính phí đúng [MỚI]

**Mục tiêu:** Quản trị ChainLens như một **external deep-research dependency hạng nhất**: contract ổn định, cost thật, degradation an toàn, và latency budget trung thực.

| Story | Nội dung | Bind | Ưu tiên |
|---|---|---|---|
| **9.1a** Research degradation & self-host independence | Contract regression test cho `POST /api/v1/search` SSE; ChainLens timeout/5xx/không-cấu-hình → degrade sang Nowing hybrid search + structured `partial`/`engine_unavailable`; self-host không có ChainLens vẫn dùng được Nowing | FR-24, FR-38, AD-15 | **P0 — TIỀN ĐỀ TRƯỚC KHI PUBLIC REPO** (D5), chạy trước 9.2 |
| **9.2** Cost metering thật | Parse `costDollars` từ SSE terminal event → `TokenUsage` (`usage_type="deep_research"`) → wallet debit; **bỏ** flat `CHAINLENS_QUERY_MICROS_PER_CALL` làm nguồn chân lý (giữ làm fallback khi engine không emit cost, có log warning) | FR-37, AD-8, AD-15 | **P0** |
| **9.3** Latency budget + State A/B gate | Đo p50/p95 per mode **từ phía Nowing** (không chờ ChainLens tự báo); build đường **async deliverable** (State A); định nghĩa **ngưỡng + cổng chuyển A→B** để bật sync chat-mode sau flag; apply mode default `quality`→`balanced` + validate trên `nowing_evals` | NFR-9 | **P1** |
| **9.4** Docs sync quan hệ Nowing↔engine | README/`docs/`/`docker/`/`.env.example`: Nowing = sản phẩm, engine hosted; bảng feature self-host vs cloud; **license đúng (Apache-2.0 core + BSL 1.1 crawler engine)** | AR-10 (mở rộng), D5, AD-16 | **P1** |
| **9.5** Metered endpoint cho self-host | Phase 2 của D5: `self-host → Nowing Cloud API (metered) → engine`. **Cấm** self-host gọi engine trực tiếp | D5, AD-15, AD-8 | *deferred — chưa phê duyệt* |
| **9.6** Memory→scraper-run provenance & re-validation | **Defect schema (phát hiện 2026-07-25):** `Memory.source_id` Integer vs `Run.id` UUID · không có writer cho `SCRAPER_RUN` · `RUNS_RETENTION_DAYS=30`. Tiền đề của differentiator *"nguồn sống, tự re-validate"* | **FR-39**, AD-11 | không chặn launch; **P0 nếu muốn kể câu chuyện re-validation** |

**Phụ thuộc ngoài (ChainLens team):** emit `costDollars` trong SSE terminal event — đã là item #2 trong "Next" của SCP v4. `9.2` cần nó; fallback flat-rate cho phép `9.2` ship trước.

---

## 3. Artifact Conflict & Impact Analysis

### 3.1 PRD (`prd-Nowing-2026-07-22/prd.md`)

| # | Section | Thay đổi | Lý do |
|---|---|---|---|
| **P1** | §1 Vision | Thêm đoạn: Nowing = sản phẩm/bề mặt phân phối + billing/account; ChainLens = engine deep-open-web-research phía sau (contract `POST /api/v1/search`). Nêu rõ lý do trả tiền: memory+provenance / self-host-privacy / integration depth — **OSS/PLG-led** | Vision hiện không nhắc engine boundary; "reason to pay" chưa nêu |
| **P2** | §2.2 Non-Users → thêm **§2.4 Non-Goals** | Tường minh, có ID để trace: **NG-1** không bán research data kiểu Exa / không owned index (Epic 26 0/7 gates; ChainLens *mua* từ Exa) · **NG-2** không đua parity consumer kiểu Perplexity, không lấy "rẻ hơn" làm lý do trả tiền (red ocean + cần GTM muscle team không có) · **NG-3** ChainLens không thành sản phẩm độc lập · **NG-4** giữ non-users cũ. NG-1 gắn `AD-DEFER-7`; NG-2 phân biệt rõ: loại **cách định vị/bán**, KHÔNG loại tính năng chat-có-citations (FR-13/14) | Chống re-litigate. Đã có 4 lần đổi hướng trong 4 ngày (07-22 → 07-25) |
| **P3** | §3 Glossary | Thêm **Deep-Research Engine (ChainLens)**, **Research Degradation** | Từ vựng chuẩn cho downstream |
| **P4** | §4.2 FR-24 → **§4.9 mới** | **Viết lại + chuyển section.** Từ "ChainLens Research MCP Tool" (một tool trong Connectors) → §4.9 Deep-Research Engine Integration; FR-24 = capability hạng nhất có contract/mode/cost/failure-mode | FR-24 hiện ngang hàng scraper Reddit — sai tầng kiến trúc |
| **P5** | §4.9 | **FR-37 Deep-Research Cost Metering** (mới) | Under-meter 2.1–3.3×; `costDollars` chưa parse |
| **P6** | §4.9 | **FR-38 Research Degradation & Self-Host Independence** (mới) | Executor chỉ raise timeout, không degrade |
| **P7** | §5 | **NFR-9 Deep-Research Latency & Availability Budget** (mới) — **hai trạng thái**: State A (hôm nay, latency chưa validated → async deliverable bắt buộc) / State B (khi Epic 43 `43-1`→`43-2`+`43-5` land và p95 đo được vượt ngưỡng → mở sync chat-mode sau flag). Xem §3.5 | Hệ quả sản phẩm lớn nhất, chưa nằm ở PRD nào |
| **P8** | §4.3 / §5 / §8 | Sửa stale: **FR-36 → RESOLVED** (`3-10a`: 178 chưa apply prod, alembic 174, `memory_md` rỗng, snapshot đã tạo → **không mất dữ liệu**; `3-10b` guard + backfill command + 5 test xanh). **NFR-8 → in-review** (`3-9`). **OQ-6 → partial** (`epics.md` đã tồn tại; còn docs sync) | PRD đang báo động đỏ về việc đã đóng |
| **P9** | §6.2 Out of Scope | Thêm: standalone research-data sale; owned web index / crawl-at-scale; Perplexity-parity consumer positioning | Đồng bộ với §2.4 và AD-DEFER-7 |
| **P11** *(bổ sung 2026-07-25 từ phiên brief)* | §1.1 + §4.9 | **§1.1:** bảng license ba tầng (Apache-2.0 / BSL 1.1 / closed-source hosted) + luật không gọi "open source" trần trụi · **§4.9 FR-38** reframe thành yêu cầu mô hình kinh doanh + hai phase + ràng buộc kiến trúc Phase 2 · **§4.9 FR-39 MỚI** — Memory→scraper-run provenance & re-validation (defect schema) | Verify code phát hiện: dual-license đã tồn tại nhưng không có trong artifact nào; và chuỗi provenance tới nguồn sống bị chặn ở schema |
| **P10** | §7 Success Metrics | Thêm **SM-11a** cost thật/deep-research call theo mode (+ tỷ lệ fallback flat-rate) · **SM-11b** p50/p95 latency per mode (cấp dữ liệu cho cổng State A→B) · **SM-11c** fallback/degradation rate (counter-metric: không nâng timeout để giấu lỗi). **Cố ý chưa đặt ngưỡng** — story 9.3 đặt sau khi có baseline. Sửa **SM-2** bỏ FR-24 (deep-research đo riêng, không gộp scraper run) | Không có metric nào theo dõi dependency; và đặt ngưỡng trước khi đo là lặp lại đúng lỗi NFR6 phía ChainLens |

### 3.2 Architecture Spine

| # | Thay đổi | Lý do |
|---|---|---|
| **A1** | **AD-15 mới — ChainLens là external deep-research dependency, KHÔNG phải scraper capability.** Rules: contract `POST /api/v1/search` SSE + Bearer service key, versioned + regression-guarded; cost lấy từ `costDollars` (flat-rate chỉ là fallback có log); failure → degrade sang hybrid search, không hard-fail; **KHÔNG merge vào monolith** (Python vs TS/NestJS — giữ service riêng, gọi qua HTTP) | Invariant cốt lõi của thay đổi này |
| **A2** | **AD-3 amend** — bỏ `FR-24` khỏi `binds`. Module code có thể ở lại `app/capabilities/chainlens/` (không bắt refactor), nhưng **governance chuyển sang AD-15** | AD-3 = "scraper capabilities tự đăng ký route"; ChainLens không còn là scraper |
| **A3** | **AD-8 amend** — ví credit nhận **cost thật** của ChainLens; cấm `BillingUnit.CHAINLENS_QUERY` flat-rate làm nguồn chân lý | Under-meter 2.1–3.3× |
| **A4** | **Capability map** — dòng "ChainLens Research": governed by `AD-3, AD-7` → **`AD-15, AD-7`** | Hệ quả A1/A2 |
| **A5** | **AD-DEFER-7 mới — Owned web index / crawl-at-scale = OUT of scope.** Reason + evidence: Epic 26 0/7 gates; a16z "Empty Promise of Data Moats"; SO pay-per-crawl 2/2026 (retroactive risk) | Chặn đề xuất lại "tự xây index để bán data" |

### 3.3 UI/UX

**N/A** — `ux-designs/ux-Nowing-2026-07-22/` chỉ có scaffold rỗng.

**Ghi nhận tiền đề (không chặn backend):** NFR-9 buộc UX pattern **async / progress-first** cho deep research (57–198s). Không được thiết kế như chat turn đồng bộ. Cần UX spec trước khi build UI deep-research.

### 3.4 Artifacts khác

| Artifact | Thay đổi |
|---|---|
| `README.md`, `docs/` | Vẫn pre-pivot ("NotebookLM alternative"). Mở rộng **AR-10** thêm mục quan hệ Nowing↔ChainLens (Nowing = sản phẩm, ChainLens = engine) |
| `docker/`, `.env.example` | ~~document self-host: chạy ChainLens hoặc chấp nhận degradation~~ → **sửa theo D5:** engine closed-source nên self-host **không thể chạy nó**. Docs phải ghi Nowing chạy đầy đủ **không cần** engine; deep research là **năng lực cloud** (Phase 1) và trả `engine_unavailable` nếu không cấu hình (FR-38). `CHAINLENS_API_URL` default `http://localhost:3001` chỉ dành cho môi trường dev nội bộ |
| `sprint-status.yaml` | Thêm `epic-9` + 4 story entries (`backlog`) |
| Testing | Contract regression test cho SSE (story 9.1) — hiện chỉ có `tests/unit/capabilities/chainlens/research/test_executor.py` |

### 3.5 NFR-9 — Latency: cải chính và framing hai trạng thái

**Cải chính (PO phản biện 2026-07-25, đã verify):** con số baseline mình dùng ban đầu (Ask 57–136s, quality 198s) **có thể đã stale**. `technical-deep-research-quality-latency-roadmap-2026-07-25.md` §0 ghi rõ:

> *"ChainLens **ĐÃ tối ưu latency rất nhiều nhưng CHƯA đo kết quả.** `ADR-DEEP-RESEARCH-SPEED` phases 1-7 **done** (budget tuning −37%, pipeline parallelization, speculative deepExtract prefetch, race Crawl4AI+Jina, precompute embeddings, cache TTL) — NHƯNG **20-0 (baseline Sentry spans) + 20-8 (final NFR6 benchmark) = backlog.**"*

→ Trạng thái đúng không phải **"chậm"** mà là **"chưa biết"** — theo cả hai chiều. Đó là lý do `43-1 eval-harness` được đánh **GATE 0** ở phía ChainLens.

**Kiểm chứng 4 đòn bẩy latency mà PO nêu:**

| Đòn bẩy | Vị trí trong backlog ChainLens | Verdict |
|---|---|---|
| Cache hit | Story **43-5** — *"tối ưu hit-rate >60% (top latency lever, **chưa đo**)"* | ✅ trong plan, chưa đo |
| Parallel subagent crawl | Story **43-2** planner-DAG — *"lever 1 (**LỚN NHẤT**)"*, parallel INDEPENDENT branches, không vi phạm anti-pattern ADR | ✅ đòn bẩy lớn nhất |
| Multi LLM model | Story **29-5 done** (cost routing) + FR51 target stack | ⚠️ routing xong; DeepSeek stack còn chờ G2–G4 |
| **Index data / index search** | **Epic 26 — DEFERRED, 0/7 gates** (Gate 1 demand ≥5K q/day: UNKNOWN) | 🔴 **KHÔNG nằm trên đường Epic 43** |

**Kết luận:** 70% reduction là **target khả tín cho ba đòn bẩy đầu** (cache + planner-DAG + model routing — đều đạt được **không cần** owned index). Đòn bẩy thứ tư (index search) phụ thuộc Epic 26 đang gated ở demand chưa tồn tại → **không phải near-term**, và trùng với `AD-DEFER-7` (owned index OUT of scope Nowing).

**Vì sao chọn framing hai trạng thái thay vì chọn một bên:**

**Async là superset của sync.** Nowing xây đường async → nếu latency giảm 70%, đường async vẫn chạy, chỉ là trả về nhanh. Nowing xây *chỉ* đường sync → nếu latency đứng ở 198s, sản phẩm vỡ. Nên "thiết kế cho async" là lựa chọn **không rủi ro bất kể ai đúng về con số 70%** — nó không cược vào giả định nào.

| | State A — hôm nay (bắt buộc) | State B — mục tiêu (mở khoá sau) |
|---|---|---|
| Giả định latency | **Chưa validated.** Không dựa vào baseline cũ *và* không dựa vào target 70% | p95 đo được vượt ngưỡng Nowing đặt |
| Nowing phải làm | Đường **async deliverable** cho deep research: submit → progress → notify → deliverable | Bật **sync chat-mode** sau feature flag |
| Điều kiện chuyển A→B | — | ChainLens `43-1` (GATE 0 eval-harness) → `43-2` + `43-5` land, **có số đo**, Nowing story `9.3` xác nhận p95 |
| Không phụ thuộc | — | **Không** phụ thuộc Epic 26 / owned index |

**Hệ quả cho story 9.3:** đổi từ "chốt async" thành "**thiết lập ngưỡng + đo p95 per mode từ phía Nowing**, và định nghĩa cổng chuyển A→B". Nowing đo độc lập, không chờ ChainLens tự báo.

---

## 4. Path Forward

| Option | Verdict | Effort | Risk |
|---|---|---|---|
| **1. Direct Adjustment** — thêm Epic 9, amend PRD/spine | ✅ **Viable** | Medium | Low-Med |
| **2. Rollback** — revert story đã xong | ❌ **Not viable** — không có gì để revert; ChainLens integration + memory layer đã ship và đang chạy | — | — |
| **3. PRD MVP Review** — thu/định nghĩa lại MVP | ✅ **Viable, cần một phần** | Low | Low |

### Đường được chọn: **Hybrid (Option 1 + Option 3 hẹp)**

**Justification:**
- **Option 1** lo phần cấu trúc: Epic 9 + AD-15 + FR-37/38 + NFR-9. Đây là phần *phải* làm vì có bug thương mại thật (cost basis, degradation), không chỉ dọn tài liệu.
- **Option 3 hẹp** lo phần *tuyên bố*: gỡ "bán data" + "Perplexity-parity" khỏi MVP, và **hạ deep research từ chat-feature xuống async deliverable**. Cái sau bắt buộc — latency 57–198s không thương lượng được ở tầng Nowing.
- **Không rollback.** MVP **không co lại về tính năng**; chỉ co lại về *lời hứa*.

**Trade-off đã cân:**
- *Chấp nhận:* thêm 1 epic vào lúc 4 epic đang `in-progress` (E3/E4/E6/E8). Bù lại: 9.1/9.2 là P0 nhỏ và chặn một khoản chảy máu margin đang chạy.
- *Chấp nhận:* xây đường async deliverable trước (State A) dù latency có thể giảm mạnh sau Epic 43. Lý do: **async là superset của sync** — xây async không mất gì nếu latency tốt lên, nhưng chỉ xây sync thì vỡ nếu latency không tốt lên. Không cược vào giả định nào (xem §3.5).
- *Từ chối:* refactor `app/capabilities/chainlens/` ra khỏi capabilities. Governance đổi (AD-15) là đủ; code layout không phải vấn đề, đổi nó là churn.

### Rủi ro cần theo dõi

| Rủi ro | Đối sách |
|---|---|
| **Pivot velocity** — 4 lần đổi hướng trong 4 ngày. Team dev không converge được khi spec đổi nhanh hơn sprint | SCP này ghi §2.4 Non-Goals tường minh để **đóng** các nhánh đã loại. **Freeze positioning 30 ngày** (tới 2026-08-24) — xem §8 quyết định D3. **Không** freeze engine work. |
| **Latency giả định sai theo cả hai chiều** — dựa vào baseline stale (quá bi quan) hoặc vào target 70% chưa đo (quá lạc quan) | NFR-9 hai trạng thái (§3.5): không cược vào giả định nào. Story `9.3` đo độc lập từ phía Nowing. |
| `costDollars` phụ thuộc ChainLens team | `9.2` ship với fallback flat-rate + log warning; không block |
| Auto-extract cost bleed (`8-7`) cộng dồn với ChainLens under-meter | Chạy `8-7` song song `9.2`; cả hai vào cùng một bảng cost |

---

## 5. PRD MVP Impact & Action Plan

**MVP có bị ảnh hưởng?** Có, nhưng **không co scope tính năng**.

**Vào MVP (mới):** FR-37 (cost metering), FR-38 (degradation), NFR-9 (latency budget) — vì cả ba đều là điều kiện để *bán* được, không phải nice-to-have.

**Ra khỏi MVP / non-goal (vĩnh viễn):** bán research data; owned web index / crawl-at-scale; Perplexity-parity consumer positioning.

**Hoãn có điều kiện (không phải non-goal):** deep research như **chat turn đồng bộ** — là **State B** của NFR-9, mở khoá khi ChainLens `43-1`→`43-2`+`43-5` land và story `9.3` xác nhận p95. MVP xây State A (async deliverable) làm sàn.

**Không đổi:** memory layer MVP (semantic facts + 4 MCP tools + eval gate), beachhead agent-builder → team, OSS self-host free / cloud paid.

### Sequencing

```
9.1 (contract + degradation)  ← TIỀN ĐỀ TRƯỚC KHI PUBLIC REPO (D5)
        │
        ├─→ public repo (Phase 1: deep research = cloud-only)
        │
9.2 (cost metering)           ──┬─→ 9.3 (latency budget + State A/B) ─→ 9.4 (docs sync)
8-7 (auto-extract spend cap)  ──┘
        │
        ├─→ [GATE] Không làm pricing/monetization trước khi 9.2 + 8-7 có số thật
        └─→ [GATE] Không mở Phase 2 (metered self-host) trước khi có số self-host thật + 9.2

3-9 (recall eval gate, review) — song song
        └─→ [GATE] Không launch ồn ào trước khi eval gate đóng
```

**Thứ tự cứng (D5, cập nhật 2026-07-25 sau khi tách story):** **`9.1a`** → public repo → `9.1b` + `9.2` + `8-7` → `9.3` → `9.4` → *(tuỳ chọn)* `9.6a` → `9.6b`. **Chỉ `9.1a` chặn public repo** — vì lý do mô hình kinh doanh, không phải kỹ thuật. `9.1b` (contract guard) là P0 nhưng không chặn.

---

## 6. Agent Handoff Plan

| Owner | Task | Acceptance |
|---|---|---|
| **PO (Luisphan)** | ✅ **Xong** — D1–D4 ghi ở §8. Còn lại: giữ freeze positioning tới 2026-08-24; trả lời `42-3` cho ChainLens team | Quyết định đã ghi §8 |
| **PM** | Apply P1–P10 vào PRD | PRD không còn stale (FR-36/NFR-8/OQ-6); có §2.4 + §4.9 |
| **Architect (Winston)** | Viết AD-15, AD-DEFER-7; amend AD-3/AD-8; sửa capability map | Spine mirror được ADR phía ChainLens |
| **Backend** | Story 9.1 + 9.2 | Contract regression test xanh; `TokenUsage` ghi cost thật; degradation có test |
| **Backend** | Story 8-7 (đã `ready-for-dev`) | Spend cap + wallet pre-check |
| **ChainLens team** | Emit `costDollars` trong SSE terminal event (SCP v4 "Next" #2); contract regression-guard | Nowing parse được cost/request |
| **Tech Writer (Paige)** | Story 9.4 — AR-10 mở rộng | README/docs/docker phản ánh Nowing=sản phẩm, ChainLens=engine |
| **UX (Sally)** | UX spec async deep-research (tiền đề, không chặn) | Flow progress-first có mockup |

---

## 7. Change Navigation Checklist Status

| Section | Check-item | Status |
|---|---|---|
| 1.1 | Triggering context: ChainLens SCP v4 ADOPTED + PO loại framing C | [x] Done |
| 1.2 | Core problem: strategic pivot + cross-repo misalignment | [x] Done |
| 1.3 | Evidence: 6 tài liệu + 7 phát hiện code verified | [x] Done |
| 2.1 | Epic hiện tại còn hoàn thành được | [x] Done |
| 2.2 | Epic-level changes: thêm Epic 9, re-bind FR-24 | [x] Done |
| 2.3 | Epic tương lai: E8 (8-7) song song; E3 (3-9) không xung đột | [x] Done |
| 2.4 | Không epic nào vô hiệu; cần 1 epic mới | [x] Done |
| 2.5 | Resequence: 9.1/9.2 trước pricing | [x] Done |
| 3.1 | PRD conflicts: P1–P10 | [x] Done |
| 3.2 | Architecture conflicts: A1–A5 | [x] Done |
| 3.3 | UI/UX: N/A (scaffold rỗng) + tiền đề async | [x] N/A |
| 3.4 | Artifacts khác: README/docs/docker/sprint-status/testing | [x] Done |
| 4.1 | Direct Adjustment | [x] Viable |
| 4.2 | Rollback | [N/A] Not viable |
| 4.3 | MVP Review | [x] Viable |
| 4.4 | Selected: Hybrid (1 + 3 hẹp) | [x] Done |
| 5.1–5.5 | Proposal components | [x] Done |
| 6.1–6.2 | Review + accuracy | [x] Done |
| 6.3 | **User approval** — D1–D4 ghi ở §8 | [x] **Done** |
| 6.4 | Update `sprint-status.yaml` (epic-9 + 4 story) | [x] Done |
| 6.5 | Confirm next steps + handoff | [x] Done |

---

## 8. Approval

**Approved by:** Luisphan (PO)
**Date:** 2026-07-25
**Decision:** [x] **Approved for implementation**

### Quyết định đã ghi

**D1 — Đường đi (PO).** ✅ Approved. OSS/PLG-led: **Nowing = sản phẩm**, **ChainLens = engine**. Lý do trả tiền = memory + provenance + self-host/privacy + integration depth. Đóng vĩnh viễn: bán research data kiểu Exa; parity consumer kiểu Perplexity.

**D2 — Deep research async? (PO phản biện → sửa thành hai trạng thái).**
PO nêu: latency ở version cuối của ChainLens có thể giảm ~70% nhờ cache hit, index data/index search, parallel subagent crawl, multi LLM model.
Đã verify backlog (§3.5): **ba đòn bẩy đầu có thật và trên đường Epic 43** (43-5 cache, 43-2 planner-DAG = "lever LỚN NHẤT", 29-5 routing done). **Đòn bẩy thứ tư (index search) KHÔNG trên đường 43** — là Epic 26, DEFERRED 0/7 gates.
Đồng thời **cải chính từ phía BA:** baseline 57–136s có thể stale — `ADR-DEEP-RESEARCH-SPEED` phases 1-7 done nhưng 20-0/20-8 backlog → latency đang là **"chưa biết"**, không phải "chậm".
→ **Quyết định:** NFR-9 **hai trạng thái**. State A (async deliverable) = sàn bắt buộc, vì async là superset của sync và không cược vào giả định nào. State B (sync chat-mode sau flag) mở khi có số đo. Story `9.3` đo độc lập từ Nowing.

**D3 — Mode default (PO giao BA quyết).** ✅ **Đổi `quality` → `balanced`.**
Lý do: Nowing đang âm thầm gọi mode đắt nhất + chậm nhất cho **mọi** call (`schemas.py:38`). `balanced` $0.0048 vs `quality` $0.0105 = **2.2×**. `quality` chuyển thành **opt-in tường minh** (user/agent yêu cầu deep-research hoặc deliverable).
Guard: story `9.3` validate chất lượng trên `nowing_evals` trước khi khoá; reversible qua env var. Nếu eval cho thấy `balanced` hồi quy chất lượng đáng kể → revert về `quality` và ghi lại.

**D4 — Freeze (PO giao BA quyết).** ✅ **Freeze 30 ngày, scoped tới positioning — KHÔNG freeze engine.**
Freeze tới **2026-08-24**, áp dụng cho: PRD §1 Vision · §2 Target User · §2.4 Non-Goals · §6 MVP Scope. Đổi các mục này phải qua SCP mới.
**Không freeze:** Epic 9 (integration), Epic 43 phía ChainLens (quality+latency), Epic 3/4/6/8 đang chạy. Lý do: cái churn 4 lần trong 4 ngày là *"bán gì cho ai"*, không phải *"engine nhanh bao nhiêu"* — và câu trả lời D2 của PO cho thấy engine work đúng là chỗ nên đẩy.

**D5 — Ranh giới OSS / Cloud (bổ sung 2026-07-25, phát sinh từ phiên `bmad-product-brief`).**
PO chốt: **chỉ Nowing public; engine deep-research closed-source, hosted.** Hệ quả logic — chưa từng ghi ở PRD nào trước đó — **mọi self-host instance chạy ở trạng thái không có engine**, tức người self-host nhận toàn bộ sản phẩm **trừ** deep open-web research.

> **⚠️ Cải chính D5 (2026-07-25, sau khi verify code trong phiên `bmad-product-brief`).** Phát biểu *"chỉ Nowing public"* ở trên **không đủ chính xác**: repo **đã** dùng dual-license trong code. `LICENSE` (root) ghi `nowing_backend/app/proprietary/**` chịu **Business Source License 1.1**, phần còn lại **Apache-2.0**. Ranh giới thật là **ba tầng**:
> 1. **Apache-2.0** — core (memory, KB, chat, automations, deliverables, 5 client, billing)
> 2. **BSL 1.1** — crawler engine `app/proprietary/**` (84 file Python, ~16.6k dòng). *Không phải OSS.* Additional Use Grant: được dùng production; **cấm** đem chính nó (hoặc sản phẩm mà giá trị chủ yếu bắt nguồn từ nó) bán cho bên thứ ba như commercial product hoặc hosted/managed service. Change Date: 4 năm → Apache-2.0
> 3. **Closed-source, hosted** — deep-research engine (không nằm trong repo)
>
> **Hệ quả bắt buộc:** mọi tài liệu công khai **không** được gọi cả sản phẩm là "open source" — sai về license. Dùng *"Apache-2.0 core + BSL 1.1 crawler engine"*. Ràng buộc kiến trúc: **`AD-16`** (mới). Luật messaging: `briefs/brief-Nowing-2026-07-25/brief.md` §5.1 + §7. PRD §1.1 đã cập nhật.
>
> **~~Tác dụng phụ tích cực:~~ 🔴 CẢI CHÍNH 2026-07-25 — lập luận này đã bị RÚT.** Bản gốc ghi: *"BSL làm luận điểm moat data-acquisition mạnh hơn — nó vừa khó xây vừa có rào pháp lý"*. **Không đứng được.** Nowing là **fork của SurfSense** và `app/proprietary/` **87% byte-identical** với upstream (73/84 file giống hệt; 26/16.600 dòng khác và chỉ là đổi chuỗi tên). "Khó xây" là đúng với **SurfSense**, không phải Nowing. Và "rào pháp lý" hiện là **rủi ro pháp lý**: `Licensor: Nowing` được đặt trên code kế thừa, attribution bị **thay** chứ không bổ sung, không có `NOTICE`. Đây là **cổng thứ hai trước public repo** — readiness `L-1`, `AD-16.1`, action item `AI-2026-07-25-7`. Cần luật sư. **Phần còn giữ được của D5:** ranh giới BSL vẫn là ranh giới kỹ thuật hợp lý (`AD-16` chiều import một phía vẫn áp dụng); chỉ **luận điểm marketing dựa trên nó** là phải gỡ.

- **Phase 1 (trong scope MVP):** cloud-only. Self-host gọi deep research → `engine_unavailable`. Không cần build gì mới ngoài chính FR-38.
- **Phase 2 (post-MVP, chưa phê duyệt):** endpoint có metering cho self-host, bắt buộc theo đường `self-host → Nowing Cloud API (metered) → engine (vẫn 1 service key)`. **CẤM** `self-host → engine trực tiếp` — cách đó phá `ADR-CHAINLENS-AS-NOWING-MICROSERVICE` §4/§5 (engine không phải public multi-tenant SaaS, không có end-user auth). Mở khi có số self-host thật + `9-2` cho số cost.
- **Đã loại:** binary/Docker closed-source của engine cho self-host.
- **Vì sao 1 trước 2:** Phase 1 → Phase 2 là cộng thêm, không phải viết lại. Cam kết Phase 2 ngay là mở multi-tenant surface trước khi biết có ai self-host thật và trước khi có số cost để định giá.

**⚠️ D5 đổi độ ưu tiên trong §5 Sequencing: `9.1a` chạy TRƯỚC `9.1b`/`9.2`.**
Trước D5, `9.1` là P0 vì *reliability*. Sau D5 nó là P0 vì **mô hình kinh doanh**: thiếu degradation thì self-host không dùng được và đường OSS/PLG sụp. ⇒ **`9.1a`** là **điều kiện tiên quyết trước khi public repo**, xếp trước `9.2` dù `9.2` có giá trị tài chính trực tiếp hơn. *(Readiness Q-3 sau đó tách `9.1` → `9.1a` degradation *(chặn)* + `9.1b` contract guard *(không chặn)*, vì chỉ phần degradation mới thật sự chặn public repo.)*

Đã propagate: PRD §1.1 (bảng self-host vs cloud) · PRD §4.9 FR-38 (reframe + hai phase + ràng buộc kiến trúc Phase 2) · PRD §6.1/§6.2 · `AD-15` · `epics.md` · `sprint-status.yaml`. Nguồn messaging: `briefs/brief-Nowing-2026-07-25/brief.md` §5.1 + §7.

### Notes
- FR-36 (data-loss) đóng nhờ `3-10a`/`3-10b` — không mất dữ liệu. PRD đang báo động đỏ về việc đã xong; sửa ở P8.
- Phụ thuộc ChainLens: `42-1 costDollars-in-SSE` (*spec ready*) cho story `9.2`; `43-1 eval-harness` (GATE 0, *spec ready*) cho cổng State A→B.
- Cần trả lời `42-3` phía ChainLens (ADR open questions): Nowing có cần endpoint reason/answer riêng? có muốn geo-access 41-2? format `costDollars` parse thế nào?

---

*`bmad-correct-course` (batch) by Mary — 2026-07-25. Đối ứng SCP v4 phía ChainLens. Companion: `prfaq-Nowing-distillate.md`, `chainlens-direction-decision-brief-2026-07-24.md`, `epic-26-gate-tracking.md`, `nfr6-final-20-8-v2-postfix.md`.*
