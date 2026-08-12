# Story 3.17 Acceptance Auditor Findings

## AC Findings

- **AC1 PASS — DB queries remain index-bound with a LIMIT** — AC violated: none. Evidence: `app/services/memory/search.py:165,199,214` calls `.limit(output_limit)` / `.limit(candidate_limit)` on all three query paths (recency, semantic, keyword); benchmark artifact `3-17-memory-performance-host.json` shows `no_seq_scan_on_memories: true` and `Index Scan` on `ix_memories_embedding` / `Bitmap Index Scan` on `ix_memories_content_search` for the `injection-personal-large` plan (e.g., line 40994). Severity: n/a.

- **AC2 PASS — p95 latency within gates for 10,000 rows** — AC violated: none. Evidence: `3-17-memory-performance-host.json` `gates` (lines 42256–42265) reports p95 DB time 26–38ms and p95 total time 40–53ms; top-level `"pass": true` at line 42340. Severity: n/a.

- **AC3 PASS — renderer truncates to ≤8,000 chars and emits `memory_injection_truncated` counter** — AC violated: none. Evidence: `app/services/memory/renderer.py:342-346` truncates the body and appends `_MEMORY_WARNING`; `app/agents/chat/multi_agent_chat/main_agent/middleware/memory/middleware.py:304-305` checks for the warning and calls `record_memory_injection_truncated`; `app/observability/metrics.py:1036-1051` creates the counter and helper; unit tests `test_truncation_counter_emitted_when_memory_overflows` and `test_truncation_counter_not_emitted_when_no_truncation` in `tests/unit/agents/multi_agent_chat/middleware/memory/test_memory_injection_middleware.py:539-565` pass. Severity: n/a.

- **AC4 PASS — exception paths fall back to `None` and increment `memory_injection_failure`** — AC violated: none. Evidence: `app/agents/chat/multi_agent_chat/main_agent/middleware/memory/middleware.py` records failure and returns `None` on query (lines 202–209), embedding (lines 215–220), session enter (lines 225–230), search (lines 242–250), session exit (lines 264–268), and render (lines 288–292). Existing D8 precedence tests in `test_memory_injection_middleware.py:378-468` cover the behavior. Severity: n/a.

## Conclusion

No AC violations found in the Story 3.17 diff. All acceptance criteria are satisfied.

> **Auditor note (non-AC):** The rendered diff inside `3-17-prompt-acceptance-auditor.md` contains two benign rendering artifacts (an extra `"user",` in a test assertion and a four-quote docstring) that do **not** appear in the actual committed files. The real `test_memory_injection_middleware.py:522` assertion is valid and the docstring in `app/observability/metrics.py:1044` is correctly triple-quoted; `ruff check` and the relevant pytest suite both pass.
