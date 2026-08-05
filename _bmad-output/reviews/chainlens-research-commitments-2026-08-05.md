# ChainLens Research — Bounded Commitments Log (2026-08-05)

**Project:** Nowing ↔ ChainLens Research v4 integration  
**Date:** 2026-08-05  
**Status:** ✅ Commitments received from ChainLens; Nowing PO approved

---

## Commitments from ChainLens

| # | Item | Commitment | Target / Evidence |
|---|---|---|---|
| 1 | **Story 34.1 full-pipeline cost telemetry** | Promoted to `in-progress` | Target completion: **2026-08-19** |
| 2 | **Canonical SSE `done` contract** | Approved and locked | `done.resolvedMode` top-level; `done.usage.{promptTokens, completionTokens, totalTokens, model, costDollars, estimated}` |
| 3 | **`estimated` semantics** | Locked | `estimated: true` = partial/writer-only; `estimated: false` = full-pipeline |
| 4 | **DeepSeek allow-list** | `DEEPSEEK_DIRECT_MODELS` default = `deepseek-v3.2` only | `deepseek-v4-pro` and `deepseek-v4-flash` removed; model allow-list contract published |
| 5 | **Async-only for expensive modes** | `quality` / `deep-research` / `deep-reasoning` async-only in Nowing chat | Until cost/latency targets are met |
| 6 | **Rerun 29-5** | Will rerun DeepSeek-direct kill-test with `deepseek-v3.2` | After 34.1 delivers, to collect G2 cost + G3 latency + G4 quality |
| 7 | **Live probe** | ≥ 10 calls | Will run immediately after 34.1 implementation |

---

## Nowing-side tracking

- **FR-37** parser now reads `done.usage.costDollars`, `done.usage.estimated`, and `done.resolvedMode`.
- **`cost_basis`** is `"estimated"` while ChainLens 42-1 emits writer-only cost; will switch to `"actual"` when 34.1 emits `estimated: false`.
- **State A** remains default: `DEEP_RESEARCH_SYNC_CHAT_MODE_ENABLED = false`.
- **State B** gate remains unratified pending:
  1. ChainLens 34.1 completion (target 2026-08-19)
  2. Rerun 29-5 with `deepseek-v3.2`
  3. Nowing e2e benchmark confirming p95 `balanced` ≤ 30s
  4. Cost per mode within 2× of PRD targets or async-only documented

---

## Blockers lifted / remaining

**Lifted:**
- Async-only contract for `quality`/`deep` agreed.
- `estimated` flag contract agreed; Nowing parser ready.
- `deepseek-v4-pro` removed from allow-list.

**Remaining:**
- ChainLens 34.1 delivery by 2026-08-19.
- Live probe ≥ 10 calls after 34.1.
- Rerun 29-5 with `deepseek-v3.2`.
- Nowing `chat/regression` and NFR-9 State B baseline ratification.

---

**Reference:**
- Nowing PO response: `chainlens-research-adjustment-response-2026-08-05.md`
- ChainLens proposal: `chainlens-research-adjustment-proposal-2026-08-05.md`
