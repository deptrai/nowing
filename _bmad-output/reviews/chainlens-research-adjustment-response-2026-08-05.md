# Nowing PO Response — ChainLens Research Adjustment Proposal (2026-08-05)

**From:** Luisphan, Product Owner, Nowing  
**To:** ChainLens Research Team  
**Re:** Phản hồi Adjustment Proposal — ChainLens Research v4 cost/latency/model contract (2026-08-05)  
**Status:** ✅ **APPROVED with bounded commitments**

---

## 1. Tóm tắt quyết định

Nowing chấp nhận đề xuất của ChainLens với các cam kết có ràng buốc:

| # | Yêu cầu Nowing | Quyết định PO |
|---|----------------|---------------|
| A1 | `costDollars` writer-only, thiếu `estimated` | **Chấp nhận tạm thời.** Nowing parser đã đọc `done.usage.estimated`; `cost_basis` sẽ là `"estimated"` khi flag `true`. ChainLens phải chuyển sang full-pipeline cost trong 1–1.5 sprint. |
| A2 | Full-pipeline token/cost telemetry (Epic 34.1) | **Approve promote 34.1 sang in-progress.** Nowing sẽ không ratify `chat/regression` cost gate cho đến khi có số thật. |
| A3 | Latency sync/async | **Approve:** `speed`/`balanced` = sync; `quality`/`deep-research` = **async-only**. NFR-9 State B vẫn tắt cho đến khi p95 `balanced` ≤ 30s. |
| A4 | Loại `deepseek-v4-pro` khỏi quality | **Confirmed.** Cần unit test + model allow-list contract. |
| A5 | Cost vượt 2× PRD | **Giải pháp = async-only cho mode đắt + rerun sau 34.1.** Không pricing `quality`/`deep` như sync cho đến khi cost thật ổn định. |
| A6 | `resolvedMode` + `estimated` trong `done` | **Confirmed.** Nowing parser đã đọc cả `done.resolvedMode` và `done.usage.estimated`. |

---

## 2. Xác nhận kỹ thuật — Nowing parser

Đã verify `nowing_backend/app/capabilities/chainlens/research/executor.py`:

- `costDollars` được đọc từ `done.usage.costDollars`, fallback `done.costDollars`.
- `estimated` được đọc từ `done.usage.estimated`, fallback `done.estimated`.
- `resolvedMode` được đọc từ `done.usage.resolvedMode`, fallback `done.resolvedMode` / `done.resolved_mode`.
- `tokens` được đọc từ `done.usage.tokens.total` hoặc `done.usage.totalTokens`.
- `cost_basis` = `"estimated"` nếu `estimated == true`, ngược lại `"actual"`.

Contract canonical mà Nowing mong đợi:

```json
{
  "type": "done",
  "chatId": "...",
  "resolvedMode": "balanced",
  "usage": {
    "promptTokens": 4273,
    "completionTokens": 3677,
    "totalTokens": 7950,
    "model": "gemini-3.6-flash",
    "costDollars": 0.0105,
    "estimated": true
  }
}
```

Nowing sẽ fallback 60,000 micros (~$0.06) khi `costDollars` thiếu hoặc malformed.

---

## 3. Phê duyệt chi tiết

### A1 — `costDollars` writer-only với `estimated: true`

**Chấp nhận tạm thời.** Nowing sẽ đánh dấu cost từ ChainLens là `"estimated"` cho đến khi full-pipeline aggregation sẵn sàng. Điều này bảo vệ wallet model khỏi under-meter nhưng vẫn thừa nhận số liệu chưa đầy đủ.

### A2 — Full-pipeline token/cost telemetry

**Approve promote Story 34.1 sang in-progress.**

Yêu cầu output tối thiểu từ ChainLens:
- `done.usage.promptTokens` / `completionTokens` / `totalTokens` tổng hợp toàn pipeline.
- `done.usage.costDollars` = full-pipeline, không chỉ writer.
- `done.usage.estimated = false` khi đo đủ.
- (Optional nhưng mong muốn) `done.usage.phases[]` với per-phase token/cost để Nowing có thể phân tích.

Nowing sẽ không ratify `chat/regression` cost gate và không bật `DEEP_RESEARCH_SYNC_CHAT_MODE_ENABLED` cho đến khi 34.1 deliver.

### A3 — Latency sync/async

**Approve:**
- `speed` và `balanced` được phép sync trong chat, với target ChainLens đề xuất: ask ≤ 60s, reason ≤ 90s, research ≤ 120s.
- `quality` và `deep-research` / `deep-reasoning` **async-only** trong chat.
- `mode=auto` phải resolve rõ ràng; `resolvedMode` trong `done` frame cho Nowing biết request đã resolve thành mode nào để route UX.

Nowing đã implement State A (async deliverable) làm default. `DEEP_RESEARCH_SYNC_CHAT_MODE_ENABLED = false` cho đến khi `balanced` p95 ≤ 30s được chứng minh.

### A4 — `deepseek-v4-pro`

**Confirmed removed from quality allow-list.** ChainLens cần cung cấp:
- `model-policy.ts` diff.
- Unit test rõ ràng loại `v4-pro`/`v4-flash` khỏi default quality.
- Published "model allow-list per mode" contract mà Nowing có thể depend on.

### A5 — Cost vượt 2× PRD

**Giải pháp = async-only cho mode đắt + đo lại sau 34.1.**

Nowing sẽ không định giá sync `quality`/`deep` cho đến khi:
- 34.1 full-pipeline cost telemetry có số thật.
- Re-run 29-5 với `deepseek-v3.2` (nếu ChainLens recommend) hoặc stack rẻ hơn có kết quả.

Nếu cost vẫn vượt 2× sau khi có full telemetry, Nowing sẽ giữ async-only cho mode đắt và/hoặc điều chỉnh pricing/credits.

### A6 — `resolvedMode` + `estimated`

**Confirmed implemented on ChainLens side and parsed on Nowing side.**

Nowing test fixture `tests/unit/capabilities/chainlens/research/test_cost_metering.py` đã cover:
- `done.usage.costDollars` + `estimated: true`.
- `done.resolvedMode`.
- Fallback khi `costDollars` thiếu/malformed.

---

## 4. Điều kiện tiên quyết trước khi Nowing ratify baseline

Before `4-8d` và `9.x` chuyển `done`, ChainLens cần deliver:

1. **Story 34.1 in-progress + sprint-status.yaml cập nhật.**
2. **Unit test + live probe** cho `done.usage.estimated` + `done.usage.costDollars` (ít nhất 10 calls).
3. **Latency report** cho `speed`/`balanced` sync từ ChainLens harness, với p50/p95.
4. **Model allow-list contract** (documented) loại `deepseek-v4-pro` khỏi quality.
5. **Async-only contract** documented cho `quality`/`deep`.

---

## 5. Hành động tiếp theo của Nowing

1. Cập nhật `prd.md` / `epics.md` để phản ánh async-only contract và `estimated` flag.
2. Giữ `4-8d` ở `ready-for-dev` cho đến khi `chat/regression` cost/latency gates ratify được với số thật.
3. Giữ `DEEP_RESEARCH_SYNC_CHAT_MODE_ENABLED=false` cho đến khi ChainLens chứng minh p95 `balanced` ≤ 30s.
4. Không enable `quality`/`auto` deep-research sync trong production cho đến khi A3, A4, A5 thỏa.
5. Sẵn sàng integrate 34.1 output khi ChainLens deliver.

---

## 6. Yêu cầu phản hồi từ ChainLens

Vui lòng xác nhận:

1. PO Nowing approve promote 34.1 và sẽ cập nhật `sprint-status.yaml` / story file trong repo ChainLens.
2. Target timeline cho 34.1 (estimate 1–1.5 sprint có vẻ hợp lý).
3. ChainLens đồng ý với contract canonical `done.usage.{costDollars, estimated, promptTokens, completionTokens, totalTokens, model}` + `done.resolvedMode`.
4. ChainLens sẽ rerun 29-5 với `deepseek-v3.2` sau 34.1 để đo cost/latency chính xác.

---

**Signed:** Luisphan, Product Owner, Nowing  
**Date:** 2026-08-05
