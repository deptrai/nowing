# Nowing PO Follow-Up — ChainLens Research Commitments Confirmed (2026-08-05)

**To:** ChainLens Research Team  
**From:** Luisphan, Product Owner, Nowing  
**Re:** Xác nhận đã tiếp nhận commitments và đã implement phía Nowing  

---

Cảm ơn phản hồi nhanh. Nowing xác nhận đã tiếp nhận và **đã implement đối ứng** như sau:

## 1. Per-mode sync/async gating — DONE on Nowing side

`nowing_backend/app/capabilities/core/access/agent.py` và `rest.py` đã được update:

- `speed` / `balanced` → có thể sync khi `DEEP_RESEARCH_SYNC_CHAT_MODE_ENABLED=true`.
- `quality` / `deep-research` / `deep-reasoning` / `auto` → **luôn async** trong chat, dù flag bật.
- Tests pass:
  - `test_agent_tool_quality_remains_async_even_when_sync_enabled`
  - `test_agent_tool_auto_remains_async_even_when_sync_enabled`
  - `test_rest_quality_downgraded_to_async_when_sync_flag_enabled`
  - `test_rest_auto_downgraded_to_async_when_sync_flag_enabled`

Điều này đảm bảo không có ai vô tình bật sync cho mode đắt/chậm trước khi có số thật.

## 2. Parser `costDollars` / `estimated` / `resolvedMode` — DONE

`app/capabilities/chainlens/research/executor.py` đã đọc:
- `done.usage.costDollars`
- `done.usage.estimated` (boolean) → set `cost_basis = "estimated"` / `"actual"`
- `done.resolvedMode` (và fallback `done.resolved_mode`)
- `done.usage.{promptTokens, completionTokens, totalTokens}`

`TokenUsage.call_details` giờ có `cost_basis`, `mode_requested`, `resolved_mode`, `e2e_ms`, `ttfb_ms`.

## 3. ChainLens deliverables cần hoàn thành

| # | Item | Owner | Target | Block cho Nowing? |
|---|------|-------|--------|-------------------|
| 1 | **Story 34.1** full-pipeline cost telemetry | ChainLens | 2026-08-19 | Không block code, nhưng block cost/pricing ratification |
| 2 | **Rerun 29-5** với `deepseek-v3.2` | ChainLens | Sau 34.1 | Block NFR-9 State B ratify |
| 3 | **Live probe ≥ 10 calls** với `estimated: true/false` | ChainLens | Sau 34.1 | Block NFR-10 cost gate ratify |
| 4 | **Golden SSE fixture** cho contract test | ChainLens | Sớm nhất có thể | Giúp Nowing viết regression guard chuẩn |

## 4. Yêu cầu thêm từ Nowing

Để Nowing viết contract regression guard chính xác, vui lòng cung cấp (nếu chưa có):

1. **Một file fixture JSON** mẫu cho `done` event với:
   - `done.resolvedMode = "balanced"`
   - `done.usage.estimated = true`
   - `done.usage.costDollars = 0.0482`
   - `done.usage.promptTokens`, `completionTokens`, `totalTokens`, `model`
2. **Một file fixture tương tự** với `estimated = false` để test 34.1 path.
3. **Xác nhận `resolvedMode` sẽ luôn nằm ở top-level `done`**, không chỉ trong `usage`.
4. **Xác nhận model allow-list** cho `DEEPSEEK_DIRECT_MODELS` sẽ được đẩy vào một file JSON hoặc contract cụ thể mà Nowing có thể reference.

## 5. Timeline Nowing

- **2026-08-05:** per-mode sync gating + parser updates merged.
- **2026-08-06:** sẽ cập nhật `epics.md`, `prd.md`, `sprint-status.yaml` để phản ánh Story 2.10 Exa MCP (vừa done).
- **Chờ ChainLens 34.1 (2026-08-19):** Nowing sẽ integrate full-pipeline cost và chạy `nowing_evals` để ratify NFR-9 State B + NFR-10 cost/latency gate.

---

**Status:** Nowing implementation ready; blocked on ChainLens 34.1 + live probe data for final ratification.

**Signed:** Luisphan, PO Nowing  
**Date:** 2026-08-05
