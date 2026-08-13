---
baseline_commit: fd64d84f46ce4fb37566c50b032d60891299c88e
baseline_branch: develop
story_key: 9-2-deep-research-cost-metering
status: done
---

# Story 9.2: Deep-Research Cost Metering (cost thật, không giá phẳng)

**Status:** done
**Epic:** 9 — Deep Research đáng tin cậy: không vỡ, không treo, tính phí đúng
**Priority:** P0
**Requirements:** FR-37; AD-8(amended 2026-07-25); AD-15; SM-11a; OQ-7(3)
**Baseline:** `fd64d84f46ce4fb37566c50b032d60891299c88e` on `develop`
**Dependencies:** Story `9-1b` done (parser stable); ChainLens `42-1` (`costDollars` in SSE terminal event) — spec ready, can ship with fallback; PRD §4.9 FR-37, AD-8, AD-15.

## Story

Với tư cách PO định giá cloud,
tôi muốn cost mỗi deep-research call được ghi theo **cost thật engine báo về**, không theo hằng số env,
để pricing/subscription có cost basis thật thay vì phỏng đoán sai 2–3×.

## Current Reality

Tại baseline `fd64d84f46ce4fb37566c50b032d60891299c88e`:

- `CHAINLENS_QUERY_MICROS_PER_CALL = 5000` ($0.005 phẳng/call) trong `nowing_backend/app/config/__init__.py`, bất kể `mode`.
- `ResearchInput.mode` default = `"quality"` (`nowing_backend/app/capabilities/chainlens/research/schemas.py:75-77`), target cost cũ ChainLens quality = $0.0105, deep research = $0.0164 → under-meter 2.1–3.3× trước đây.
- `ResearchOutput.billable_units` trả `1` nếu có `answer` hoặc `sources`, `0` nếu không (`schemas.py:242-246`). `charge_capability` trong `nowing_backend/app/capabilities/core/billing.py:254-256` gọi `_charge_platform_meter` với `_platform_rate(BillingUnit.CHAINLENS_QUERY)` = `CHAINLENS_QUERY_MICROS_PER_CALL`.
- `grep -rn "costDollars\|cost_dollars" nowing_backend/` = **0 hits**. `_SSEParser` (`executor.py`) chưa parse bất kỳ `costDollars` nào.
- `TokenUsage` (`app/db.py:1129-1188`) có `usage_type` (String(50)), `cost_micros` (BigInteger), `call_details` (JSONB), `workspace_id`, `user_id`, `thread_id`, `message_id`.
- `record_token_usage` (`app/services/token_tracking_service.py:503-554`) ghi `usage_type`, `cost_micros`, `call_details`.
- `_charge_platform_meter` (`billing.py:265-293`) gọi `record_token_usage(usage_type=unit.value, cost_micros=cost_micros, call_details={"items": items, ...})` và `service.charge(owner_user_id, items, rate)`.
- OQ-7(3) (2026-07-25) xác nhận ChainLens đã thiết kế shape `{ "type": "usage", "costDollars": 0.0123, "tokens": { "total": 1280 } }` (`chainlens-research/apps/api/src/search/__tests__/fixtures/sse-contract-fixtures.ts:168`) và Nowing yêu cầu thêm `resolvedMode` + `estimated: boolean`, đặt `usage` **trước** `done`.
- Gate: **không chốt pricing/subscription** trước khi 9.2 + 8-7 có số đo thật (AD-8, SCP §5).

**Cập nhật 2026-08-02 — ChainLens benchmark `report-per-mode.md` (31 queries, tier/mode):**

| Mode | Tier | Avg Latency | Avg Cost |
|---|---|---|---|
| speed | ask | 21.8 s | $0.0258 |
| balanced | ask | 25.8 s | $0.0407 |
| quality | ask | 49.3 s | $0.1485 |
| speed | reason | 29.6 s | $0.0303 |
| balanced | reason | 47.7 s | $0.0507 |
| quality | reason | 49.9 s | $0.0750 |
| speed | research | 33.4 s | $0.0353 |
| balanced | research | 51.1 s | $0.0482 |
| quality | research | 49.1 s | $0.0671 |

- `costDollars` **không còn $0**; ChainLens đã emit cost thực tế.
- Nowing dùng `tier=research`, nên cost tham chiếu chính: **speed $0.0353 / balanced $0.0482 / quality $0.0671**, trung bình toàn bộ **$0.0519 / call**.
- `CHAINLENS_QUERY_MICROS_PER_CALL` fallback đã cập nhật từ 5,000 ($0.005) → **60,000 micros (~$0.06)** để sát cost thực tế khi engine không emit `costDollars`.
- `ResearchInput.mode` default đã đổi `quality` → `balanced` (Story 9.3 done).

## Resolved Decisions

### D1 — Cost thật từ SSE `costDollars`, flat-rate chỉ là fallback

- ChainLens emit `costDollars` ở SSE terminal (`type: "usage"`, có thể trước `done`) **hoặc ngay trong payload `done`**. Parser chấp nhận cả hai vị trí defensive.
- `_SSEParser` phải parse event `usage`, lấy `costDollars` (float USD), `resolvedMode` (optional), `estimated` (optional), `tokens.total` (optional). Nếu `done` payload cũng chứa `costDollars`, parser ghi đè/lấy cuối.
- `ResearchOutput` thêm field `cost_micros: int | None` (làm tròn `costDollars * 1_000_000` bằng `Decimal` hoặc `round()` để tránh lỗi float 1 micro) và `cost_basis: Literal["actual", "estimated", "fallback"]` (optional). `resolved_mode` cũng ghi để SM-11a.
- `billing.py` thêm `_charge_chainlens` riêng, dùng `wallet_credit.apply_debit` để debit **cost_micros thật**, không đi qua `PlatformScrapeCreditService.charge(items, rate)`. `charge_capability` dispatch sang `_charge_chainlens` khi `unit is BillingUnit.CHAINLENS_QUERY`.
- `TokenUsage.usage_type` ghi `"deep_research"` cho mọi deep-research call (kể cả fallback), phân biệt bằng `call_details.cost_basis`. `BillingUnit.CHAINLENS_QUERY` vẫn là fallback meter cho `pricing_meters` preview, không dùng để debit.

### D2 — `BillingUnit.CHAINLENS_QUERY` xuống hạng fallback

- `CHAINLENS_QUERY_MICROS_PER_CALL` chỉ dùng khi engine không emit `costDollars` hoặc phiên bản cũ.
- Mỗi lần fallback phải log warning (`logger.warning`) với degradation reason để đo tần suất fallback.
- `pricing_meters` vẫn dùng `_platform_rate(BillingUnit.CHAINLENS_QUERY)` cho UI preview khi chưa có số thật; không dùng để debit.
- Khi fallback, `usage_type` vẫn là `"deep_research"`, `cost_basis = "fallback"`, `call_details` ghi rõ `fallback_rate_micros` và lý do.

### D3 — Wallet debit dùng cost thật qua `_charge_chainlens`

- `charge_capability` dispatch sang `_charge_chainlens(output, ctx)` khi `unit is BillingUnit.CHAINLENS_QUERY`.
- `_charge_chainlens`:
  - Resolve `owner_user_id` từ `ctx.workspace_id`.
  - Kiểm tra `output.status`: nếu `engine_unavailable` và không có câu trả lời/sources (không có fallback có giá trị), **không debit**.
  - Nếu `output.cost_micros` có, debit đúng số đó qua `wallet_credit.apply_debit`.
  - Nếu `output.cost_micros` None, tính fallback từ `CHAINLENS_QUERY_MICROS_PER_CALL` (1 unit * rate), log warning, đặt `cost_basis="fallback"`.
  - Gọi `record_token_usage(usage_type="deep_research", cost_micros=cost_micros, call_details={...})`.
- `record_token_usage` ghi `call_details` bao gồm `resolved_mode`, `estimated`, `cost_basis`, `mode_requested`, `cost_dollars` gốc.

### D4 — Mode & source của cost

- Nếu `resolvedMode` có, ghi vào `call_details["resolved_mode"]`; nếu không, dùng `payload.mode`.
- `estimated` = `true` thì `cost_basis = "estimated"`; `false` hoặc thiếu thì `"actual"`; fallback flat-rate là `"fallback"`.
- SM-11a: cost thật/call **theo mode** đo được + tỷ lệ fallback; nối vào dashboard NFR-7 khi có.

### D5 — Không đổi `ResearchOutput` schema theo hướng phá vỡ

- Các field mới là additive: `cost_micros`, `cost_basis`, `resolved_mode`, `tokens_total`. Không xóa field hiện có.
- `billable_units` vẫn tính dựa trên answer/sources; `_charge_chainlens` không dùng `billable_units` để quyết định debit mà dùng `cost_micros` + `status`. Fallback rate áp dụng khi `cost_micros` None và `status` khác `engine_unavailable`.

### D6 — Làm tròn `costDollars` bằng `Decimal` hoặc `round()`

- Không dùng `int(cost_dollars * 1_000_000)` vì float có thể ra `12299.999999999998`.
- Ưu tiên `Decimal(str(cost_dollars)) * Decimal("1000000")` với `ROUND_HALF_UP`, hoặc `round(cost_dollars * 1_000_000)` nếu muốn đơn giản hơn.
- Test bao phủ `0.0123`, `0.1`, `0.0001`, `0.000001` (1 micro), `0.999999` (làm tròn 1 triệu micro).

### D7 — Chỉ debit khi call có nội dung billable

- `_charge_chainlens` không debit khi `output.status == "engine_unavailable"` và `output.answer`/`output.sources` rỗng (không có fallback có giá trị).
- Các trạng thái `complete`, `partial`, `insufficient_evidence`, `timeout` có thể debit nếu `cost_micros` hoặc fallback rate > 0.

### D8 — Tôn trọng `PLATFORM_SCRAPE_BILLING_ENABLED`

- `_charge_chainlens` phải check `config.PLATFORM_SCRAPE_BILLING_ENABLED` trước khi gọi `wallet_credit.apply_debit`.
- Khi billing disabled (self-host / OSS default), vẫn gọi `record_token_usage` với `cost_micros` để có số đo, nhưng không debit wallet.
- Không được gọi `PlatformScrapeCreditService.charge` nếu đã bypass nó.

### D9 — Post-charge balance check & malformed cost

- Trước khi `apply_debit`, `_charge_chainlens` gọi `wallet_credit.check_balance(ctx.session, owner_user_id, cost_micros)`.
- Nếu balance không đủ, raise `InsufficientCreditsError` (fail-closed) — kể cả khi `cost_micros` thật lớn hơn số đã reserve ở `gate_capability`.
- `costDollars` malformed (string, null, object, negative, NaN) → parser coi như không có, fallback về flat-rate và log warning.

## Acceptance Criteria

1. **Parse `costDollars` từ SSE `done.usage` (hoặc `usage` event / `done` payload cũ), chống malformed** (FR-37, D1, D6, D9)
   - **Given** ChainLens emit data-only frame `{"type":"done","usage":{"costDollars":0.0123,"totalTokens":7950,...},"resolvedMode":"balanced"}` (hoặc các vị trí cũ/tạm: top-level `costDollars` trong `done` hoặc standalone `usage` event),
   - **When** `_SSEParser.feed_line` nhận frame,
   - **Then** parser lưu `cost_dollars = 0.0123`, `tokens_total = 7950` (từ `totalTokens` trong `usage`), `resolved_mode`, `estimated` vào parser state ngay lập tức,
   - **And** `ResearchOutput.finalize()` trả về `cost_micros = 12300` (làm tròn `Decimal`/`round`), `cost_basis = "actual"` (hoặc `"estimated"` nếu `estimated=true`), `resolved_mode`.
   - **And** khi `costDollars` malformed (string/null/object/negative/NaN) hoặc `usage` đến sau `done`, parser fallback về flat-rate với log warning.

2. **Cost ưu tiên thật, fallback về flat-rate có warning** (AD-8, D2, D3, D8, D9)
   - **Given** `ResearchOutput.cost_micros` có giá trị, `output.status != "engine_unavailable"`, `config.PLATFORM_SCRAPE_BILLING_ENABLED=True`, và wallet đủ balance,
   - **When** `charge_capability(output, BillingUnit.CHAINLENS_QUERY, ctx)` chạy,
   - **Then** `_charge_chainlens` gọi `wallet_credit.check_balance` rồi debit đúng `output.cost_micros` qua `wallet_credit.apply_debit`,
   - **And** `TokenUsage.usage_type = "deep_research"`, `TokenUsage.cost_micros = output.cost_micros`, `call_details` có `cost_dollars` gốc, `resolved_mode`, `mode_requested`, `cost_basis = "actual"` (hoặc `"estimated"`),
   - **And** `User.credit_micros_balance` bị trừ đúng số.
   - **When** `config.PLATFORM_SCRAPE_BILLING_ENABLED=False`, **Then** `TokenUsage` vẫn được ghi nhưng wallet không bị trừ.

3. **Fallback flat-rate khi engine không emit cost** (D2, D3)
   - **Given** engine cũ hoặc lỗi không emit `costDollars`, nhưng call trả về nội dung có thể bill (`status != "engine_unavailable"`),
   - **When** `_charge_chainlens` chạy,
   - **Then** nó dùng `CHAINLENS_QUERY_MICROS_PER_CALL` làm `cost_micros`, đặt `cost_basis = "fallback"`, log warning với lý do fallback,
   - **And** `TokenUsage.usage_type` vẫn là `"deep_research"`, `BillingUnit.CHAINLENS_QUERY` không còn là nguồn chân lý cho cost thật.

4. **Aggregate cost per mode** (SM-11a, D4)
   - **Given** đã có nhiều `TokenUsage` rows với `usage_type="deep_research"` và `call_details.resolved_mode`,
   - **When** truy vấn aggregate,
   - **Then** tính được average/min/max/p50/p95 cost per `resolved_mode` (speed/balanced/quality/auto) và tỷ lệ fallback,
   - **And** có test/unit hoặc query mẫu chứng minh.

5. **Gate chặn chốt giá** (AD-8, SCP §5)
   - **Given** story 9.2 done và 8-7 có số thật,
   - **When** ai đó đề xuất chốt giá subscription,
   - **Then** pricing có thể định hình dựa trên cost thực tế (ChainLens 2026-08-02: research speed $0.0353 / balanced $0.0482 / quality $0.0671, avg $0.0519), nhưng vẫn giữ margin dự phòng 1.5–2.5× cho full-pipeline cost aggregation.

## Open Questions / Risks

1. ChainLens `42-1` đã ship với `costDollars` trong `done.usage`. Parser Nowing đã cập nhật, snippet contract chạy mẫu OK. Benchmark 2026-08-02 (`report-per-mode.md`, 31 queries) đã ghi nhận cost thực tế: research speed **$0.0353** / balanced **$0.0482** / quality **$0.0671**, trung bình **$0.0519** — không còn $0. **Tuy nhiên full-pipeline cost aggregation là task 6 "LATER"**; ChainLens dự kiến tạo story/PRD follow-up (42-1b/42-3) tuần này, trình sprint planning tuần tới, land **~2–4 sprint** sau khi benchmark + pipeline ổn định. ChainLens ước tính full-pipeline cost cao hơn **1.5–2.5×** writer cost. Pricing/margin cần để lại dự phòng cho đến khi full-pipeline cost land.
2. `TokenUsage` table đang có partial unique index trên `message_id` khi not null. `chainlens.research` call từ agent/REST không nhất thiết có `message_id`; `message_id` nullable, không vấn đề.
3. `wallet_credit.apply_debit` tự `commit()`. `record_token_usage` phải stage trước khi gọi `apply_debit` để audit row cùng commit. Caller (REST/agent door) không nên commit riêng sau `charge_capability`.
4. `costDollars` đến sau `done`: parser cần lưu `cost_dollars` ngay khi nhận `usage`, không chờ `finalize`; `done` payload chỉ ghi đè nếu chưa có.
5. Post-charge `check_balance` có thể raise `InsufficientCreditsError` sau khi output đã sản xuất xong. Caller phải xử lý để user vẫn nhận được output nhưng bị báo hết credit (pattern giống `gate_capability` pre-check).
6. `record_token_usage` exception trước `apply_debit`: cần fail-open (vẫn debit) hay fail-closed (không debit nếu không ghi được audit)? Story chọn fail-open để tránh nghẽn P0, nhưng risk mất audit. Có thể xem xét log error và continue.

## Files to Touch

- `nowing_backend/app/capabilities/chainlens/research/executor.py`
  - `_SSEParser.__slots__` thêm `cost_dollars`, `cost_basis`, `resolved_mode`, `estimated`, `tokens_total`.
  - `feed_line` xử lý `event_type == "usage"`.
  - `finalize` truyền các trường mới vào `ResearchOutput`.

- `nowing_backend/app/capabilities/chainlens/research/schemas.py`
  - `ResearchOutput` thêm `cost_micros: int | None = None`, `cost_basis: Literal["actual", "estimated", "fallback"] | None = None`, `resolved_mode: str | None = None`, `tokens_total: int | None = None`.

- `nowing_backend/app/capabilities/core/billing.py`
  - Thêm `_charge_chainlens(output, ctx)`: resolve owner, kiểm tra `status`, debit `output.cost_micros` qua `wallet_credit.apply_debit`, hoặc fallback `CHAINLENS_QUERY_MICROS_PER_CALL` với warning.
  - `charge_capability` dispatch sang `_charge_chainlens` khi `unit is BillingUnit.CHAINLENS_QUERY`.
  - Đảm bảo `record_token_usage` nhận `usage_type="deep_research"` và `call_details` đầy đủ.

- `nowing_backend/app/capabilities/core/types.py`
  - Không cần đổi enum; `BillingUnit.CHAINLENS_QUERY` vẫn là fallback meter.

- `nowing_backend/tests/unit/capabilities/chainlens/research/test_executor.py`
  - Thêm test parse `usage` event, fallback khi thiếu cost, rounding, `cost_basis`.

- `nowing_backend/tests/unit/capabilities/test_billing.py`
  - Thêm test `charge_capability` với `ResearchOutput` có `cost_micros`, test fallback, test `TokenUsage` ghi đúng.

- `nowing_backend/tests/integration/capabilities/chainlens/research/test_research_fallback.py`
  - Bổ sung test cost thật trong integration.

## Verification

- `pytest tests/unit/capabilities/chainlens/research/test_executor.py -q`
- `pytest tests/unit/capabilities/test_billing.py -q`
- `pytest tests/integration/capabilities/chainlens/research/test_research_fallback.py -q`
- `ruff check nowing_backend/app/capabilities/chainlens/research/executor.py nowing_backend/app/capabilities/chainlens/research/schemas.py nowing_backend/app/capabilities/core/billing.py`
- Kiểm tra `TokenUsage` row mới trong integration với `cost_micros > 0` và `usage_type = "deep_research"`.

## References

- <ref_file file="/Users/luisphan/Documents/GitHub/nowing/.knowns/docs/planning/planning-artifacts/nowing-epic-breakdown.md" /> §Story 9.2
- <ref_file file="/Users/luisphan/Documents/GitHub/nowing/_bmad-output/planning-artifacts/oq7-answers-to-chainlens-2026-07-25.md" /> Q3 format `costDollars`
- <ref_file file="/Users/luisphan/Documents/GitHub/nowing/.knowns/docs/planning/planning-artifacts/sprint-change-proposal-nowing-s-n-ph-m-chainlens-engine-2026-07-25.md" /> §3.2 A3, §8 D1–D5
- <ref_file file="/Users/luisphan/Documents/GitHub/nowing/.knowns/docs/planning/planning-artifacts/architecture/architecture-Nowing-2026-07-22/architecture-spine-nowing.md" /> AD-8 amendment
- <ref_file file="/Users/luisphan/Documents/GitHub/nowing/nowing_backend/app/capabilities/chainlens/research/executor.py" />
- <ref_file file="/Users/luisphan/Documents/GitHub/nowing/nowing_backend/app/capabilities/chainlens/research/schemas.py" />
- <ref_file file="/Users/luisphan/Documents/GitHub/nowing/nowing_backend/app/capabilities/core/billing.py" />
- <ref_file file="/Users/luisphan/Documents/GitHub/nowing/nowing_backend/app/services/token_tracking_service.py" />
- <ref_file file="/Users/luisphan/Documents/GitHub/nowing/nowing_backend/app/db.py" />

---

## Challenge Log (grill-me)

### Q1 — Already implemented?

- **No duplicate found.** `grep -rn "costDollars\|_charge_chainlens\|deep_research" nowing_backend/` chỉ trả về 2 hits không liên quan (`report_style` và prompt text).
- Không có logic nào parse `costDollars` từ ChainLens SSE, thêm `cost_micros` vào `ResearchOutput`, hoặc debit cost thật hiện tại.
- `wallet_credit.apply_debit` và `record_token_usage` đã tồn tại và có thể reuse.

### Q2 — Simpler alternative?

- **Có sẵn helper `wallet_credit.apply_debit` trong `nowing_backend/app/services/wallet_credit.py:73-104`.** Nó debit `cost_micros` trực tiếp, commit, và fire auto-reload. Đây là primitive chuẩn để `_charge_chainlens` dùng.
- **Tuy nhiên `apply_debit` KHÔNG kiểm tra billing flag.** Nó ungated — tất cả các `PlatformScrapeCreditService`/`WebCrawlCreditService` đều gọi nó sau khi đã check `billing_enabled()`. `_charge_chainlens` phải tự check `config.PLATFORM_SCRAPE_BILLING_ENABLED` trước khi gọi `apply_debit`.
- Không nên reuse `PlatformScrapeCreditService.charge(owner, items, rate)` vì nó tính `items * rate`, không nhận `cost_micros` override.

### Q3 — Edge cases spec misses (Pattern 3)

- [ ] **Boundary:** `costDollars = 0.000001` (1 micro) → `cost_micros = 1`; `costDollars = 0.0` → `cost_micros = 0`, không debit.
- [ ] **Boundary:** `costDollars` có 7+ chữ số thập phân → làm tròn nửa lên đúng.
- [ ] **Boundary:** `costDollars` âm hoặc `NaN` → parser coi như 0 / fallback / bỏ qua (chưa specify).
- [ ] **Null/empty:** `usage` event không có `costDollars` → fallback; `tokens` thiếu → `tokens_total = None`.
- [ ] **Null/empty:** `resolvedMode` không có → dùng `payload.mode`; `estimated` thiếu → `actual`.
- [ ] **Ordering:** `usage` event xuất hiện **sau** `done` (defensive) — parser cần lưu ngay `cost_dollars` khi nhận `usage`, không chờ `finalize`.
- [ ] **Ordering:** `costDollars` xuất hiện trong cả `usage` và `done` — policy ghi đè nào lên? (đề xuất: `done` chỉ ghi đè nếu chưa có `usage`; `usage` sau `done` cũng ghi đè nếu chưa có).
- [ ] **Concurrent:** `gate_capability` pre-reserve `estimated_units * CHAINLENS_QUERY_MICROS_PER_CALL`; actual cost có thể lớn hơn. Cần policy khi `cost_micros > balance` ở post-charge (bên dưới).
- [ ] **Mode mismatch:** `resolvedMode` từ engine khác `payload.mode` (ví dụ `auto` → `quality`) → ghi `resolvedMode` trong `call_details` vẫn đúng.

### Q4 — Failure modes unspecified (Pattern 2, 4)

- [ ] **Billing disabled (`PLATFORM_SCRAPE_BILLING_ENABLED=False`):** `_charge_chainlens` không gọi `apply_debit` — hiện tại story chưa ghi rõ. Nếu quên, self-host bị tính tiền.
- [ ] **Insufficient balance at post-charge:** `apply_debit` không check balance, nên có thể tạo negative balance nếu gate đã reserve flat-rate nhưng cost thật cao hơn. Cần quyết định:
  - (a) `_charge_chainlens` gọi `wallet_credit.check_balance` trước `apply_debit` → raise `InsufficientCreditsError` mid-call (nên làm).
  - (b) Cho phép overdraft (hiện tại `apply_debit` cho phép).
- [ ] **User/owner not found:** `_resolve_workspace_owner` trả về `None` → return 0, không charge. `apply_debit` sẽ raise `ValueError` nếu user_id không tồn tại; `_charge_chainlens` phải validate trước.
- [ ] **Malformed `costDollars` (string, null, object):** parser nên ignore / fallback, không raise.
- [ ] **Record token usage fails before debit:** `record_token_usage` trả về `None` on exception; `apply_debit` vẫn chạy → mất audit row. Xem xét liệu có nên abort charge khi audit fail (fail-closed cho P0 tiền).
- [ ] **ChainLens `usage` event `estimated=true`:** `cost_basis = "estimated"`; subscription/pricing phải đối xử khác actual — chưa ghi rõ ở story.
- [ ] **Commit isolation:** `apply_debit` tự `commit()`. Nếu `charge_capability` được gọi trong transaction lớn hơn, `apply_debit` có thể commit sớm. Story cần ghi rõ: `record_token_usage` phải được stage trước `apply_debit` (như pattern hiện tại của `_charge_platform_meter`).

### Triage

- **Critical — đã cập nhật vào story (D8, D9, AC1, AC2, Open Questions):**
  - Billing flag `PLATFORM_SCRAPE_BILLING_ENABLED` được `_charge_chainlens` tôn trọng.
  - Post-charge balance check `wallet_credit.check_balance` trước `apply_debit`.
  - Malformed `costDollars` parser fallback về flat-rate + warning.
- **Non-critical — thêm vào test skeleton:**
  - Rounding edge cases (Q3).
  - `usage`/`done` ordering and overwrite (Q3).
  - `estimated=true` and `resolvedMode` mapping (Q3/Q4).
- **Overall verdict:** Story đã bổ sung critical decisions. Có thể proceed `test-first-atdd`.

## Next Steps (post-creation)

1. ✅ Run `bmad-nowing-grill-me` — challenge xong, có critical findings đã sửa story.
2. ✅ Run `bmad-nowing-test-first-atdd` — ATDD checklist đã tạo.
3. ✅ Run `bmad-testarch-atdd` — red-phase unit test bodies đã viết; **16 tests đỏ** (mới), **27 tests xanh** (cũ).
4. ✅ Run `bmad-nowing-integration-test` — **5 integration tests đỏ** (Pattern 6 SQL) với Postgres thật.
5. ✅ Run `bmad-dev-story` để implement — tất cả unit (82) + integration (15) tests xanh, ruff xanh.
6. Run `bmad-code-review` → `bmad-nowing-mutation-gate` → `bmad-nowing-human-review-gate`.

## Review Findings (code review 2026-08-08)

Scope: commits `fd64d84f4`..`0ba407e10` — 8 files, 1186 lines (deep-research cost metering, P0 surface).

**decision-needed:** 0

**patch:** 0

**defer:** 0

**dismissed:** 8 (all findings false positives or by-design)
- Missing pre-flight gate for CHAINLENS_QUERY — FALSE POSITIVE. CHAINLENS_QUERY falls through to `_gate_platform` which calls `check_balance` with flat-rate. Two-phase design: pre-flight reserves flat-rate, post-charge uses real cost. D9 explicitly describes this.
- Wrong billing gate (PLATFORM_SCRAPE_BILLING_ENABLED) — FALSE POSITIVE. Story spec D8 explicitly says "tôn trọng PLATFORM_SCRAPE_BILLING_ENABLED". By design.
- Inconsistent NaN check (raw_cost != raw_cost) — FALSE POSITIVE. Current code uses `math.isfinite()` at executor.py:490. Blind Hunter looked at old diff.
- Cost race condition (first valid wins) — FALSE POSITIVE. Current code uses `cost_source == "done"` at executor.py:472. Done overwrites usage.
- AC-5 FAIL (no margin-based gate) — DISMISS. AC-5 is a process gate for PO decision-making, not code. Cost data IS available via TokenUsage.call_details.resolved_mode.
- Large costDollars no upper bound — DISMISS. `check_balance` catches over-limit costs.
- Config change mid-request — DISMISS. Fail-safe (billing disabled = no debit).
- Multiple usage events — DISMISS. First usage wins, done overwrites. Correct behavior.

**AC coverage:** AC-1 PASS, AC-2 PASS, AC-3 PASS, AC-4 PASS, AC-5 PASS (process gate, cost data available).

**Note:** Blind Hunter's 2 HIGH + 2 MEDIUM were all false positives — it reviewed an old diff snapshot, not the current code. The current code has `math.isfinite()` and `cost_source == "done"` which fix MEDIUM-1 and MEDIUM-2. HIGH-1 and HIGH-2 are by-design behavior documented in the story spec.

**Positive findings (correctly implemented):**
- Float precision: `Decimal(str(cost_dollars)) * Decimal("1000000")` with `ROUND_HALF_UP`
- Malformed input: non-numeric, negative, NaN, infinity all handled
- Billing gate: checked before debit, records usage even when disabled
- Engine unavailable: no-debit path correct
- Token usage: always recorded with `usage_type="deep_research"`
- Fallback: flat-rate with warning when no costDollars
- Post-charge balance check: fail-closed with `InsufficientCreditsError`

---

## Regression Fix — `Run.cost_micros` and chat turn token-usage when billing disabled (2026-08-13)

### Symptom
During real-data E2E verification of Story 12.9 (Job Market Alerts) the ChainLens API key was rotated. After updating `CHAINLENS_API_KEY` and restarting the backend, direct REST calls to `/api/v1/workspaces/11/scrapers/chainlens/research` returned correct `cost_micros` in the JSON body, but the persisted `Run` row showed `cost_micros: 0`. The same symptom appeared when the agent chat path invoked the `chainlens` subagent: `Run.cost_micros` was `0` and the chat turn's `token_usage` breakdown did **not** include the `chainlens.research` tool cost.

### Root cause
`_charge_chainlens()` in `nowing_backend/app/capabilities/core/billing.py` returned `0` when `config.PLATFORM_SCRAPE_BILLING_ENABLED` was `False`:

```python
if not billing_enabled:
    await _record_chainlens_cost_allocation(...)
    return 0
```

Callers `record_and_publish_sync_run` (REST sync door) and `record_run` (agent sync door) stored the return value as `Run.cost_micros`. The agent door also fed that `0` into `add_current_turn_tool_cost(...)`, which meant the chat turn token-usage SSE never saw the deep-research cost.

This did **not** affect wallet debits (billing disabled correctly skipped `wallet_credit.apply_debit`), and `TokenUsage` audit rows still recorded the real cost via `_record_chainlens_cost_allocation`. The bug was purely the cost value propagated upstream to `Run` and chat telemetry.

### Fix
Changed `_charge_chainlens` to return the real `total_cost_micros` even when billing is disabled, while keeping the wallet un-touched:

```python
if not billing_enabled:
    await _record_chainlens_cost_allocation(...)
    # ponytail: return the real engine cost even when billing is disabled so
    # Run.cost_micros and the chat turn token-usage SSE remain accurate.
    return total_cost_micros
```

This is the minimum surgical change: it preserves the existing billing-disable contract (no `apply_debit`) but gives callers the actual cost they need for `Run` metadata and chat turn accounting.

### Files changed
- `nowing_backend/app/capabilities/core/billing.py` — return `total_cost_micros` when `billing_enabled` is `False`
- `nowing_backend/tests/unit/capabilities/test_billing.py` — update `test_chainlens_billing_disabled_records_usage_without_debit` assertion from `charged == 0` to `charged == 12300`
- `nowing_backend/tests/integration/capabilities/chainlens/research/test_research_cost_metering.py` — update `test_charge_capability_records_usage_without_debit_when_billing_disabled` assertion from `charged == 0` to `charged == 12_300`

### Real-data verification (2026-08-13)

| Path | Run id | `Run.cost_micros` | `token_usage` chat breakdown | Wallet debit |
|---|---|---|---|---|
| REST sync `/scrapers/chainlens/research` | `run_14ad9732-afd4-487c-b021-eb9fb1f0281e` | `48635` | N/A | None (billing disabled) |
| Agent chat -> `chainlens` subagent | `run_d4ca86a0-6f0a-4ac9-965e-4aed938af36c` | `119270` | `chainlens.research: 119270` included | None (billing disabled) |

Example chat turn token-usage after fix:

```json
{
  "cost_micros": 204406,
  "model_breakdown": {
    "chainlens.research": { "cost_micros": 119270 },
    "agy/gemini-3.6-flash-high": { "cost_micros": 85136 }
  }
}
```

### Tests run
- `uv run pytest tests/unit/capabilities/test_billing.py -q` -> **86 passed**
- `uv run pytest tests/unit/capabilities/chainlens/research tests/unit/capabilities/access/test_agent_tools.py tests/unit/capabilities/access/test_rest_router.py -q` -> **283 passed, 1 skipped**
- `uv run pytest tests/integration/capabilities/chainlens/research/test_research_cost_metering.py -q` -> **5 passed**
- `uv run ruff check nowing_backend/app/capabilities/core/billing.py nowing_backend/tests/unit/capabilities/test_billing.py nowing_backend/tests/integration/capabilities/chainlens/research/test_research_cost_metering.py` -> **All checks passed**

### Note
`charge_capability` now returns the *real engine cost* in all cases; the wallet is still protected by `config.PLATFORM_SCRAPE_BILLING_ENABLED`. Callers that need the "amount actually debited" can compare `TokenUsage.call_details` or wallet history; `Run.cost_micros` should be interpreted as the *actual cost incurred by the engine*, which is what the product surface (runs log, chat token usage, analytics) needs.
