---
title: "OQ-7 — Nowing trả lời ChainLens (story 42-3)"
created: 2026-07-25
author: "Mary (Business Analyst) + Luisphan (PO), Nowing"
to: "ChainLens team — story 42-3 (verify Nowing endpoint needs)"
status: ready-to-send
unblocks: ["ChainLens 42-1 costDollars-in-SSE", "ChainLens 42-3", "Nowing 9-2", "Nowing 9-3"]
method: "đọc code cả hai repo 2026-07-25, không trả lời theo phỏng đoán"
---

# OQ-7 — Nowing trả lời ChainLens (story `42-3`)

**Bối cảnh:** `ADR-CHAINLENS-AS-NOWING-MICROSERVICE` §"Open questions" để ngỏ 3 câu hỏi cho Nowing. Nowing bổ sung câu thứ 4 (progress granularity) trong readiness check 2026-07-25.

**Cách trả lời:** đọc code **cả hai repo** trước khi kết luận. Ba trong bốn câu **lật so với giả định ban đầu** — chi tiết dưới.

---

## Q1 — Nowing có cần endpoint riêng (`reason` / `answer` variants) hay `/api/v1/search` là đủ?

### ✅ Trả lời: **`/api/v1/search` là đủ. Đừng thêm endpoint.**

**Lý do 1 — Nowing không cần lớp reasoning của engine.** Nowing có runtime multi-agent riêng (LangGraph/LangChain, `app/agents/chat/multi_agent_chat/`) làm việc tổng hợp, chọn tool, và sinh citation của chính nó. Nếu ChainLens expose `answer`/`reason` thì Nowing sẽ có **hai lớp reasoning xếp lên nhau** — engine reason rồi Nowing reason lại. Vừa đắt gấp đôi, vừa khó truy nguyên citation.

**Lý do 2 — Nowing chỉ cần một trục điều khiển, và nó đã có.** `ResearchInput` của Nowing (`app/capabilities/chainlens/research/schemas.py`) có đúng ba tham số: `query`, `mode` (`speed|balanced|quality|auto`), `sources` (`web|discussions|academic`). Độ sâu điều khiển bằng `mode`, không cần endpoint khác nhau.

**Lý do 3 — một contract là một quyết định kiến trúc đã ký.** `AD-15` (phía Nowing) và ADR của các bạn đều chốt **một** interface công khai. Thêm endpoint là mở lại quyết định đó, và mỗi endpoint mới là một bề mặt phải regression-guard.

**Nếu sau này Nowing cần độ sâu khác:** xin thêm **giá trị `optimizationMode` mới**, không phải endpoint mới.

---

## Q2 — Nowing có muốn geo-access (`41-2`) không?

### 🟡 Trả lời: **Không phải bây giờ. Và có phần trùng lặp cần bàn.**

**Trùng lặp:** Nowing **đã có** hạ tầng proxy/geo trong crawler riêng (`nowing_backend/app/proprietary/`, BSL 1.1): proxy provider registry + rotation (`app/utils/proxy/`), `PROXY_PROVIDER`/`PROXY_URLS`, `CRAWL_GEOIP_MATCH_ENABLED`, chặn WebRTC, ẩn canvas fingerprint, DNS-over-HTTPS, headed browser qua Xvfb, CAPTCHA solving. Tức với **8 nền tảng / 14 scraping verb** của Nowing, geo đã được giải ở phía Nowing.

Phần **không** trùng là provider chain của các bạn (Brave / Jina / Exa / Tavily / Perplexity Sonar / SearXNG) — Nowing không kiểm soát được geo ở đó.

**Đề nghị:** **đừng build speculatively.** Chưa có một khiếu nại cụ thể nào từ user Nowing về nguồn bị region-block. Khi có, Nowing sẽ gửi kèm URL + region cụ thể để các bạn đánh giá — lúc đó quyết định có căn cứ hơn.

**Ưu tiên thay thế:** ba việc dưới đây đáng làm trước `41-2` với Nowing: `42-1` (costDollars — đang chặn Nowing `9-2`), `43-1` (eval-harness GATE 0), `43-5` (cache hit-rate — đòn bẩy latency).

---

## Q3 — Format `costDollars` Nowing muốn parse thế nào?

### ✅ Trả lời: **shape các bạn đã thiết kế là đúng. Cứ dùng nó.**

Tìm thấy trong repo các bạn — `apps/api/src/search/__tests__/fixtures/sse-contract-fixtures.ts:168`:

```json
{ "type": "usage", "costDollars": 0.0123, "tokens": { "total": 1280 } }
```

**Nowing xác nhận: đây đúng là thứ Nowing cần.** Ba lý do nó khớp:
1. **Event top-level, có `type` discriminator** — khớp cách parser Nowing dispatch (`event.get("type")`).
2. **Additive** — parser hiện tại của Nowing gặp `type` không biết thì **bỏ qua im lặng**, nên gửi sớm cũng không làm vỡ gì. Các bạn có thể ship `42-1` **trước** khi Nowing xong `9-2`.
3. `costDollars` là **số**, đơn vị USD, per-request — đúng hạt Nowing cần để meter (Nowing sẽ ghi vào `TokenUsage` với `usage_type="deep_research"`).

### Ba điều Nowing xin thêm

| Field | Vì sao |
|---|---|
**`resolvedMode`** | Nowing gửi `optimizationMode` nhưng với `auto` thì engine tự chọn. Nowing cần biết **mode thật đã chạy** để quy chi phí đúng theo mode (metric SM-11a của Nowing chia theo mode). Nếu `42-1` không có field này, Nowing phải suy đoán. |
**`estimated: boolean`** | Nowing cần phân biệt cost **đo được** vs **ước lượng**. Ảnh hưởng trực tiếp việc Nowing có dám chốt giá subscription hay không. |
**Vị trí event** | Xin đặt `usage` **trước** `{"type":"done"}`. Nowing coi `done` là mốc terminal; nếu `usage` đến sau, parser có thể đã dừng đọc. |

### ⚠️ Bối cảnh vì sao Nowing cần cái này gấp

Nowing hiện tính **giá phẳng $0.005/call** (`CHAINLENS_QUERY_MICROS_PER_CALL = 5000`) trong khi mặc định gửi `mode="quality"` — theo bảng cost của các bạn (PRD §7.1) là **$0.0105**, deep research **$0.0164**. ⇒ Nowing đang **under-meter 2.1–3.3×**. Đây là lý do `42-1` chặn cả `9-2` của Nowing lẫn việc Nowing chốt giá cloud.

---

## Q4 — Engine emit progress theo phase được không?

### 🔄 **Câu hỏi này Nowing XIN RÚT. Lỗi ở phía Nowing.**

Nowing đặt câu này vì nghĩ engine chỉ cho biết "bắt đầu" và "xong". **Sai — các bạn đã emit progress từ trước.** Verify code `apps/api/src/search/api.ts`:

```js
api.ts:414   session.emit('data', { type: 'progress', ...milestones })   // requestAcceptedAt, firstProgressAt
api.ts:1298  session.emit('data', { type: 'progress', ...milestones })   // + evidenceReadyAt
api.ts:221   session.emit('data', { type: 'progress', ...milestones })   // + firstFactualChunkAt
api.ts:1299  session.emit('data', { type: 'evidence_ready', ... })
```

**Vấn đề nằm ở parser của Nowing.** `_parse_sse` (`executor.py`) chỉ dispatch 4 type — `error`, `done`, `block`, `updateBlock` — và trong block thì chỉ đọc `text` + `source`. **Mọi thứ khác bị bỏ im lặng.**

### Nowing đang bỏ 6 loại event các bạn gửi

| Event các bạn gửi | Nowing xử lý? | Nowing mất gì |
|---|---|---|
`progress` (milestones) | ❌ bỏ | UX progress-first không có gì hiển thị trong 57–198s |
`insufficientEvidence` (`partial`, `reason`) | ❌ bỏ | **Nowing tự suy đoán lại trạng thái này — xem dưới** |
`partial` (`state`, `reason`) | ❌ bỏ | cùng vấn đề |
`synthesizing` | ❌ bỏ | mốc progress hữu ích |
`heartbeat` | ❌ bỏ | không phân biệt được "đang chạy" vs "đã chết" |
`noop` | ❌ bỏ | (vô hại) |

### 🔴 Hệ quả nặng nhất — Nowing suy đoán lại thứ các bạn đã nói rõ

Các bạn gửi tường minh:
```js
session.emit('data', { type: 'partial', state: 'insufficient_evidence', reason })
```

Nowing lại **đoán** bằng heuristic (`executor.py`):
```python
if not answer and not sources:
    if saw_done: status = "insufficient_evidence"
    else:        status = "timeout"
```

Tức Nowing đang gộp *"tìm không ra bằng chứng"* và *"stream chết giữa đường"* vào một phép đoán, trong khi engine **đã phân biệt sẵn** kèm `reason`. Đây là defect phía Nowing, đã ghi vào story **`9.1a`** (degradation) — chính là story mà FR-38 của Nowing cần trạng thái `partial`/`engine_unavailable` tường minh.

**Việc của Nowing, không phải của các bạn.** Không cần các bạn làm gì thêm cho Q4.

---

## 🎁 Ngoài lề — hai điều tìm thấy trong repo các bạn, đáng ghi nhận

### 1. `42-2` của các bạn đã làm đúng cách khó nhất
`apps/api/src/search/__tests__/fixtures/nowing-sse-parser.ts` là **bản mirror parser của Nowing**, và nó **dùng chính `rfc6902 applyPatch`** mà `session.ts updateBlock` dùng — nên parity là chính xác, không phải xấp xỉ. Cách này tốt hơn hẳn viết assertion tay.

**Đề nghị:** Nowing sẽ tham chiếu fixture này trong story `9.1b` (contract guard phía Nowing) thay vì viết fixture thứ hai lệch dần theo thời gian. Nếu các bạn export nó thành một file JSON golden dùng chung được thì càng tốt.

### 2. ⚠️ Contract được **document sai** ở phía Nowing — và Nowing sẽ tự sửa
Docstring `nowing-sse-parser.ts` của các bạn ghi rõ:
> *"NestJS `@Sse()` emits data-only frames — there is NO separate `event:` line"*
> *"the real terminal marker is a `{ "type": "done" }` json payload — NOT a bare `data: [DONE]` sentinel"*

**Các bạn đúng.** Nhưng tài liệu Nowing (PRD §4.9 FR-24, `AD-15`, SCP §3) đều mô tả contract là *"block-based SSE (`event:`/`data:`…)"*. Nowing có một nhánh xử lý `event:` **không bao giờ chạy**.

Không phải lỗi của các bạn, nhưng nó nguy hiểm: ai viết regression test theo tài liệu Nowing sẽ test một format không tồn tại. Nowing sẽ sửa tài liệu trong `9.1b`. **Ghi ở đây để hai bên cùng biết đâu là contract thật.**

---

## Tóm tắt cho ChainLens team

| Câu | Trả lời | Các bạn cần làm gì |
|---|---|---|
**Q1** endpoint riêng? | **Không.** `/api/v1/search` đủ. Cần độ sâu khác → thêm giá trị `optimizationMode` | Không gì. Đóng câu này. |
**Q2** geo-access `41-2`? | **Không phải bây giờ.** Nowing đã có proxy/geo cho crawler riêng. Chưa có khiếu nại cụ thể | **Hạ ưu tiên `41-2`.** Ưu tiên `42-1` → `43-1` → `43-5` |
**Q3** format `costDollars`? | **Shape các bạn đã thiết kế là đúng.** Xin thêm `resolvedMode` + `estimated`, và đặt `usage` **trước** `done` | **Ship `42-1`.** Additive nên không cần chờ Nowing |
**Q4** progress theo phase? | **Nowing xin rút — các bạn đã emit rồi.** Lỗi ở parser Nowing | Không gì. Nowing tự sửa trong `9.1a`/`9.3` |

**Đường găng:** `42-1` là thứ duy nhất trong bốn câu mà các bạn còn phải làm, và nó đang chặn `9-2` của Nowing lẫn việc Nowing chốt giá cloud.

---

*Soạn bởi Mary (BA, Nowing) — 2026-07-25. Verify bằng code cả hai repo. Companion: `prd-Nowing-2026-07-22/prd.md` §4.9 OQ-7, `ARCHITECTURE-SPINE` AD-15/AD-17, `implementation-readiness-report-2026-07-25.md` U-3.*
