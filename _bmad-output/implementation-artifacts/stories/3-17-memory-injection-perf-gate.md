# Story 3.17: Memory Injection Bounded-Retrieval Performance Gate

**Epic:** 3 — Knowledge Base + Long-Term Memory
**Status:** done
**Governed by:** AD-18, NFR-1b

## Goal

A performance + regression gate proving `MemoryInjectionMiddleware` stays O(top-k), so that AD-18 is not silently regressed as the product accumulates memories.

## Acceptance Criteria

| AC | Description | Status |
|---|---|---|
| AC1 | DB query uses `ix_memories_embedding` (HNSW) or `ix_memories_content_search` (GIN) indexes with `top_k`/`LIMIT` bound; no full-scan `SELECT ... ORDER BY created_at` without `LIMIT` | ✅ Code verified — `search.py` uses `.limit()` on all 3 paths (semantic, keyword, recency) |
| AC2 | p95 DB time ≤ 150ms and p95 total time ≤ 300ms over 100 turns with 10,000 memory rows | ✅ PASS — benchmark on host Postgres 18.3, 10k rows, 100 samples |
| AC3 | Raw memory content > 8,000 chars → `render_bounded_memory_injection` truncates at 8,000 chars + emits `memory_injection_truncated` counter | ✅ Done — added `record_memory_injection_truncated` to `metrics.py`, emitted from middleware when `_MEMORY_WARNING` in rendered output |
| AC4 | Middleware exception → fallback to `None` + increment `memory_injection_failure` counter | ✅ Already done (Story 3.14 D8) — `record_memory_injection_failure` called at every failure stage |

## Implementation Notes

### AC3 — Truncation counter (new work)

**Files changed:**
- `app/observability/metrics.py` — added `_memory_injection_truncated` counter + `record_memory_injection_truncated(scope)` helper
- `app/agents/chat/multi_agent_chat/main_agent/middleware/memory/middleware.py` — import `record_memory_injection_truncated` + `_MEMORY_WARNING`; after successful render, check `if _MEMORY_WARNING in rendered:` and emit counter
- `tests/unit/agents/multi_agent_chat/middleware/memory/test_memory_injection_middleware.py` — 2 new tests: truncation emitted on overflow, not emitted when no truncation

**Design decision:** The `_MEMORY_WARNING` marker is only embedded in the truncated output path (renderer Rule 9 — memory body overflow). Checking for it in the middleware is the simplest reliable signal that truncation occurred, without changing the renderer's return type API.

### AC1 — Index usage (already satisfied)

`MemoryHybridSearch.search()` in `app/services/memory/search.py`:
- **Semantic CTE:** `order_by(distance.asc()).limit(candidate_limit)` — uses HNSW index
- **Keyword CTE:** `where(tsvector @@ tsquery).order_by(keyword_rank.desc()).limit(candidate_limit)` — uses GIN index
- **Recency path:** `order_by(created_at.desc()).limit(output_limit)` — bounded

### AC4 — Failure counter (already satisfied)

`record_memory_injection_failure` is called at every failure stage in `middleware.py`: query, embedding, session enter, search, session exit, render.

## Review Findings (2026-08-13)

### decision-needed

- [x] [Review][Decision] Truncation counter only fires on Rule 9 (memory-body) truncation, missing Rule 8 name shrink and name-only truncation — `middleware.py:304`, `renderer.py:184-194,329-343`  
  **Resolved: keep Rule-9-only.** `epics.md` AC3 says "raw memory content for a single turn would exceed 8,000 chars" — this is Rule 9. Rule 8 (display-name shrink/omit) and `_render_name_only` are not "raw memory content", so they correctly do not increment this counter. The `_MEMORY_WARNING` marker is the renderer's signal for Rule 9 and is safe because `html.escape(..., quote=True)` prevents user content from matching the literal marker text.

### patch

- [x] [Review][Patch] Add Python logger fallback in `record_memory_injection_truncated` for audit/debuggability — `app/observability/metrics.py:1043-1051`
- [x] [Review][Patch] Add unit test for `record_memory_injection_truncated` (logs + counter, disabled OTel) — `tests/unit/observability/test_memory_injection_telemetry.py`
- [x] [Review][Patch] Add unit test for `memory_injection_truncated` on team scope — `tests/unit/agents/multi_agent_chat/middleware/memory/test_memory_injection_middleware.py`
- [x] [Review][Patch] Add unit test for exact/edge `max_chars` boundary at middleware layer — `tests/unit/agents/multi_agent_chat/middleware/memory/test_memory_injection_middleware.py`
- [x] [Review][Patch] Add clarifying code comment in middleware explaining Rule-9 contract — `app/agents/chat/multi_agent_chat/main_agent/middleware/memory/middleware.py:300-305`

### dismiss

- Metric name `nowing.memory.injection.truncated` is past-participle vs. plural `failures` — naming convention is acceptable and consistent with existing `nowing.*.outcome` counters.
- Counter attributes only `scope` — AC does not require richer labels; matches minimal instrumentation contract.
- `_add` suppressed `BaseException` — follows project pattern; system-level exceptions should not be swallowed.
- Private marker `_MEMORY_WARNING` import — acceptable coupling for this story; cleaner renderer-signal refactor can be deferred.
- Counter instrument created before `_is_enabled()` check — `opentelemetry` returns no-op proxy when no provider is configured; safe.

## Benchmark Results (AC2)

**Environment:** macOS Darwin 25.4.0, PostgreSQL 18.3 (Homebrew), pgvector 0.8.3, 384-dim embeddings
**Parameters:** `--small-corpus 100 --large-corpus 10000 --warmups 30 --samples 100 --freshness-samples 0`
**Evidence:** `_bmad-output/implementation-artifacts/evidence/3-17-memory-performance-host.json`
**Verdict:** PASS=True

| Cell | Rows | p95 DB (ms) | p95 Total (ms) | Gate DB ≤150ms | Gate Total ≤300ms |
|---|---|---|---|---|---|
| injection-personal-small | 100 | 26.3 | 40.0 | ✅ | ✅ |
| injection-personal-large | 10,000 | 28.8 | 44.2 | ✅ | ✅ |
| injection-team-small | 100 | 37.6 | 53.1 | ✅ | ✅ |
| injection-team-large | 10,000 | 32.7 | 43.3 | ✅ | ✅ |

Key observation: p95 DB time stays flat (26-38ms) from 100 → 10,000 rows, confirming O(top-k) behavior. The HNSW index ensures query time depends on `top_k` (5) + `candidate_limit` (15), not table size.

## Mutation Gate Results (2026-08-13)

Focused `cosmic-ray` runs executed against the changed code with targeted test files to keep the gate within CI time window.

| Module | Service path | Mutants run | Killed | Survived | Score | Verdict | P0 | P1 | P2 |
|---|---|---|---|---|---|---|---|---|---|
| `MemoryInjectionMiddleware` | `agents/chat/multi_agent_chat/main_agent/middleware/memory/middleware` | 386 / 412 | 267 | 119 | **69.17%** | `PASS_WITH_WARNINGS` | 0 | 119 | 0 |
| `metrics.py` | `observability/metrics` | 1664 / 1723 | 681 | 983 | **40.93%** | `FAIL` | 0 | 983 | 0 |

**Note on `observability/metrics`:** the focused run used only `tests/unit/observability/test_memory_injection_telemetry.py`, which covers `record_memory_injection_truncated`. Cosmic-ray mutates the entire `metrics.py` module, so mutants in unrelated helpers survive because the focused test suite does not exercise them. The 40.93% score is a module-level fail, not a P0-critical finding, and should be re-run with the full observability test suite for a representative verdict.

**Artifacts:**
- `_bmad-output/test-artifacts/mutation-nowing-agents-chat-multi_agent_chat-main_agent-middleware-memory-middleware-20260813T042800Z-final.json`
- `_bmad-output/test-artifacts/mutation-nowing-observability-metrics-20260813T042800Z-final.json`

## Traceability Matrix (2026-08-13)

- Matrix: `_bmad-output/test-artifacts/traceability-3.17.md`
- Verdict: **PASS** — all 4 ACs mapped to unit/benchmark tests and source code; no gaps.
- Next: NFR audit (4.12) → Human review gate (4.13)

## EXPLAIN Verification (AC1)

From the Docker benchmark evidence (`3-17-memory-performance.json`):

- **Semantic CTE:** `Index Scan` on `ix_memories_embedding` (HNSW) → `Incremental Sort` → `WindowAgg` → `Limit 15`
- **Keyword CTE:** `Bitmap Index Scan` on `ix_memories_content_search` (GIN) → `Bitmap Heap Scan` → `Sort` → `WindowAgg` → `Limit 15`
- **Final query:** `Nested Loop` + `Hash Join` (full outer join of semantic/keyword CTEs) → `Sort` → `Limit 15`
- **`no_seq_scan_on_memories: true`** — no sequential scan on the memories table in any path

## Verification Commands

```bash
# Unit tests (from nowing_backend/)
uv run pytest tests/unit/agents/multi_agent_chat/middleware/memory/test_memory_injection_middleware.py tests/unit/services/test_bounded_memory_injection_renderer.py -q

# Lint
uv run ruff check app/agents/chat/multi_agent_chat/main_agent/middleware/memory/middleware.py app/observability/metrics.py tests/unit/agents/multi_agent_chat/middleware/memory/test_memory_injection_middleware.py
uv run ruff format app/agents/chat/multi_agent_chat/main_agent/middleware/memory/middleware.py app/observability/metrics.py tests/unit/agents/multi_agent_chat/middleware/memory/test_memory_injection_middleware.py

# Benchmark (requires fresh Postgres with pgvector to avoid stale data)
# Create a clean DB:
psql -h localhost -U postgres -d postgres -c "DROP DATABASE IF EXISTS nowing_bench;" -c "CREATE DATABASE nowing_bench;"
psql -h localhost -U postgres -d nowing_bench -c "CREATE EXTENSION IF NOT EXISTS vector;"
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/nowing_bench .venv/bin/alembic upgrade head
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/nowing_bench .venv/bin/python scripts/benchmark_memory_story_3_14.py --small-corpus 100 --large-corpus 10000 --warmups 30 --samples 100 --freshness-samples 0 --output ../_bmad-output/implementation-artifacts/evidence/3-17-memory-performance-host.json
```
