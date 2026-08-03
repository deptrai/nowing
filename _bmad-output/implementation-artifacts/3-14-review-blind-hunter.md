# Blind Hunter Review — Story 3-14

Reviewed the diff at `/Users/luisphan/Documents/nowing/_bmad-output/implementation-artifacts/3-14-in-review.diff`.

- `nowing_backend/app/services/memory/search.py` (diff lines 2047–2062): The production ranked query builds the FROM clause as `semantic.outerjoin(keyword, ...)` and then outer-joins `Memory` on `COALESCE(semantic.id, keyword.id)`. Because `semantic.outerjoin(...)` is a left outer join with `semantic` on the left, keyword-only rows that are not in the semantic top-15 can never appear. The benchmark's own `_ranked_query_sql` correctly uses `FULL OUTER JOIN`, but the real SQLAlchemy query does not, so the two paths diverge and recall is degraded.

- `nowing_backend/app/routes/research_threads_routes.py` (diff line 1317) and `nowing_backend/scripts/benchmark_memory_story_3_14.py` (diff line 3120): Both still extract `query_embedding = embeddings[0]` directly. `memories_routes.py` was updated to use `validate_single_embedding_result(embeddings)`, but these two call sites were skipped, so an empty or malformed embedding provider result can raise `IndexError` or pass bad data into search.

- `nowing_evals/src/nowing_evals/suites/memory/recall/runner.py` (diff lines 6355–6416): `_verify_backend_build_id` falls back to the local git HEAD when `/health` does not expose a `build_id`, and then returns `verified: True` for that git-filesystem match. A checkout matching the local git tree proves nothing about which backend is actually running; `verified` should only be `True` when the live `/health` endpoint returns the matching `build_id`.

- `nowing_backend/app/app.py` (diff lines 661–697): `_backend_build_id()` reads `NOWING_GIT_SHA`, falls back to reading `.git/HEAD` and ref files, and is called on every `/health` request. The docstring calls `/health` a "lightweight liveness probe", but the function performs filesystem I/O every call. The build id should be resolved once at startup and cached.

- `nowing_backend/app/agents/chat/multi_agent_chat/main_agent/middleware/memory/middleware.py` (old warning code removed at diff lines 358–400) and `nowing_backend/app/services/memory/renderer.py` (diff lines 1707–1761): The previous `MEMORY_SOFT_LIMIT` / `MEMORY_HARD_LIMIT` warning that told the agent its personal or team memory was approaching the hard limit has been removed. The new bounded renderer only emits a truncation warning when the 8,000-character injection budget is exceeded, so there is no longer any signal for overall memory size pressure.

- `nowing_backend/app/observability/metrics.py` (diff lines 1207–1218): `record_memory_injection_failure` logs the literal string `"memory_injection.failure"` with `extra={scope, stage, reason}`. Unless the deployed formatter is explicitly structured, the actual `scope`/`stage`/`reason` will not appear in the raw log line, making on-call debugging harder for an already error-path telemetry call.

- `nowing_backend/app/services/memory/search.py` (diff lines 1955–1958): The `top_k` guard uses `isinstance(top_k, int)`, which returns `False` for `numpy.int64` and other integer-like types. Internal callers that pass a numpy integer will get a misleading `ValueError` even though the value is a valid positive integer.

- `nowing_backend/app/agents/chat/multi_agent_chat/main_agent/middleware/memory/middleware.py` (diff lines 410–471): `abefore_agent` catches bare `Exception` around transcript building, embedding, session entry, search, and rendering, converts the failure to a single telemetry reason, and returns `None`. No stack trace or underlying exception is logged, so programming bugs in this hot path will be silently swallowed.

- `nowing_backend/app/observability/metrics.py` (diff lines 1215–1218): `record_memory_injection_failure` wraps both the logger call and the metric counter call in `contextlib.suppress(Exception)`. A broken logging or OpenTelemetry backend therefore fails completely silently, with no signal that failure telemetry is not being recorded.

- `nowing_backend/scripts/benchmark_memory_story_3_14.py` (diff lines 3082–3372): `_scope_sql_for_injection`, `_recency_query_sql`, `_semantic_cte_sql`, `_keyword_cte_sql`, and `_ranked_query_sql` build SQL with f-string interpolation for workspace ids, thread ids, and user ids. The values are internally controlled, but the pattern is brittle and unsafe; it should use bound parameters or at least robust escaping.

- `nowing_backend/app/schemas/memory.py` (diff lines 1373–1381): `MemorySearchHit.score` changed from a required `float` to `float | None = None` and a new `similarity` field was added. Any existing consumer that expects `score` to always be a number will now receive `null` for recency-style results. There is no backward-compatible shim or deprecation path for this contract change.

- `nowing_mcp/mcp_server/features/memory/annotations.py` (diff lines 7034–7039): The MCP `TopK` annotation uses `int` plus a `BeforeValidator` that only rejects booleans. It does not use `StrictInt` like `app/utils/strict_fields.py` does, so float and string inputs can still be coerced to integers before the `ge=1, le=5` check is applied, diverging from the validation behavior used for `MemorySearchRequest` and `ContinueResearchActionParams`.
