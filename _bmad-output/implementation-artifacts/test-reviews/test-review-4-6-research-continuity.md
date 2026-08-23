# Test Quality Review — Story 4.6: Research Continuity

## Executive Summary

Test suite đáp ứng tốt các acceptance criteria AC-1..AC-4 của Story 4.6. Có unit test, integration test, và MCP tool test. Các trường hợp edge chính (cross-workspace, cross-thread, dedup, malformed marker, non-member, 404) đã được cover. Sau khi thêm unit test parser trong code review, coverage parser đã đủ.

**Kết luận:** **APPROVED** với 5 khuyến nghị bổ sung test/Assertion (low–medium), không block `done`.

## AC Coverage Mapping

| AC | File test | Evidence |
|---|---|---|
| AC-1: memories + citations | `test_research_continuity.py::test_continue_context_returns_memories_and_citations`, `test_continue_context_includes_chunk_citations_without_url` | Có assert `memories` và `citations` cùng trả về |
| AC-1: MCP memories + citations | `test_research_continuity.py` (MCP), `test_memory_tools.py::test_continue_research_reads_context_endpoint` | Kiểm tra render cả memory và citation URL |
| AC-2: missing thread 404, no implicit create | `test_research_continuity.py::test_continue_context_missing_thread_returns_404_and_creates_nothing`, `test_memory_tools.py::test_continue_research_missing_thread_surfaces_not_found` | 404 được assert và row count không đổi |
| AC-3: recall definition unchanged | `test_research_continuity.py::test_continue_context_recall_matches_recall_definition` | So sánh ID/order với `POST /memories/search` |
| AC-4: workspace/thread scoping | `test_research_continuity.py::test_context_denied_for_non_member`, `test_context_thread_scoped_to_workspace_returns_404`, `test_continue_context_citations_do_not_leak_across_threads` | 403, 404, và không leak giữa threads |
| AC-4: dedup + malformed skip | `test_research_continuity.py::test_continue_context_dedupes_and_skips_malformed_citations` | Chỉ có 1 dup URL, marker lỗi không crash |

## Strengths

- **Test pyramid hợp lý:** unit test parser (`test_parser.py`) + integration test endpoint (`test_research_continuity.py`) + MCP tool test (`test_research_continuity.py`, `test_memory_tools.py`).
- **Isolation được cover đầy đủ:** workspace, thread, member/non-member.
- **Edge cases:** dedup, malformed, cross-thread, chunk citations (`url=None`).
- **Không có flaky waits/network:** dùng ASGI client + fake client, không phụ thuộc browser.
- **Tên test và docstring rõ ràng**, map trực tiếp đến AC.

## Findings / Recommendations

| # | Vấn đề | Trạng thái |
|---|---|---|
| 1 | Thiếu integration test cho `RunCitationMarker` (medium) | **Đã giải quyết** — `test_continue_context_includes_run_citation` |
| 2 | `client_id` tenant filter chưa được kiểm chứng (medium) | **Đã giải quyết** — `test_continue_context_citations_filter_by_client_id` |
| 3 | Assertion ở `test_continue_context_returns_memories_and_citations` còn yếu (low) | **Đã giải quyết** — `len == 1`, assert `content`/`id`/`source_type`/`label` |
| 4 | `urlcite` placeholder chưa có end-to-end test (low) | **Accepted/đủ** — `test_drops_urlcite_placeholder` trong `test_parser.py` |
| 5 | Citation cap (50) chưa được kiểm chứng (low) | **Đã giải quyết** — `test_continue_context_citations_capped_at_limit` |

## Test Execution Status

- `tests/unit/agents/multi_agent_chat/shared/citations/test_parser.py`: **9 passed**
- `tests/integration/memory/test_research_continuity.py`: **11 passed** (đã thêm 3 tests)
- `tests/integration/memory/test_research_continuity.py` + `tests/integration/workspaces/test_memory_routes.py`: **37 passed**
- `nowing_mcp/tests/test_research_continuity.py` + `tests/test_memory_tools.py`: **17 passed**
- `ruff check` trên tất cả file test đã thay đổi: **clean**

## Next Steps

- Có thể merge `done` vì các khuyến nghị là low/medium và AC đã được cover.
- Nếu muốn harden thêm trước khi release, ưu tiên #1 (Run marker) và #2 (client_id isolation).
