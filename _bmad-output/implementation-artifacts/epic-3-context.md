# Epic 3 Context: Knowledge Base + Long-Term Memory

<!-- Compiled from planning artifacts. Edit freely. Regenerate with compile-epic-context if planning docs change. -->

## Goal

Xây dựng và vận hành lớp dữ liệu tri thức của workspace: tài liệu, thư mục, hybrid search, citation, và long-term research memory. Đảm bảo người dùng tìm được thông tin đã lưu, trích dẫn đúng nguồn, và agent có bối cảnh domain để trả lời chính xác mà không bị nhiễu hoặc rò rỉ cross-tenant.

## Stories

- Story 3.6: Citation Scroll-to-Highlight in Full Document Editor
- Story 3.7: Memory Retention, Right-to-Delete & Legal Readiness
- Story 3.7-followup: Retention Hardening
- Story 3.9: Memory Recall Eval-Gate
- Story 3.10: Legacy Memory Data Safety
- Story 3.11: Memory Dedupe & Confidence Tuning
- Story 3.12: Memory Security
- Story 3.13: First-Run Value
- Story 3.14: Memory Injection Bounded Retrieval
- Story 3.15: Run Citations
- Story 3.16: OKF Export
- Story 3.17: Memory Injection Perf Gate
- Story 3.18: Projects Persistent Workspace & Modular Skills Hub

## Requirements & Constraints

- Documents và folders thuộc workspace, có lifecycle với `archived_at` soft-delete.
- Hybrid search kết hợp vector (pgvector HNSW) và full-text (GIN) trên `documents` và `chunks`.
- Memory phải multi-tenant an toàn, có audit log cho write, và không rò rỉ cross-tenant.
- Memory cần provenance recipe (`source_capability`, `source_input`, `source_run_id`) theo AD-11.1; nội dung redacted nằm ở `content`/`embedding`.
- First-run value: research/scrape run phải có khả năng sinh memory để `nowing_recall` không rỗng trong session đầu.
- Memory injection phải bounded theo token/char limit (NFR-1b) và sử dụng index đã có.
- Cost & credit tracking phải ghi nhận mọi memory operation có tính phí.

## Technical Decisions

- **AD-1**: backend là monolith module hóa, không microservice; nghiệp vụ nội bộ không tách service riêng.
- **AD-2**: pgvector + GIN cho hybrid search.
- **AD-11**: long-term memory là first-class persistence layer; memory tự chứa recipe, không phụ thuộc lifecycle của `Run`.
- **AD-11.1**: memory recipe (`source_capability` + `source_input` + `source_run_id`) immutable, không redacted, không embedded, không gửi engine.
- **AD-12**: MCP server expose memory tools.
- **AD-18**: memory injection dùng retrieval có chặn trên, tách hai đường recall nóng/lạnh.
- **AD-112**: Skills Hub có thể đăng ký skill như LangGraph subgraph hoặc DSH mission template; agent có thể gọi DSH mission làm skill.
- Migrations phải backwards-compatible và có backfill khi xóa cột legacy.

## UX & Interaction Patterns

- Workspace tree (`Folder` + `Document`) render 1 lần mỗi lượt, bounded bởi `MAX_TREE_ENTRIES` và `MAX_TREE_TOKENS`.
- Editor hỗ trợ scroll-to-chunk và highlight khi mở citation.
- Chat UI cần hiển thị project context, pinned docs, và skill suggestions khi user ở trong project.

## Cross-Story Dependencies

- 3.18 phụ thuộc vào 3.13 (memory extraction), 3.14 (bounded retrieval), và Epic 4/18 (chat runtime + agent registry).
- 3.18 cung cấp bối cảnh domain cho agent trong Epic 4, 6, 9, 21.
- Skills Hub (`skill_type='workflow'`) dùng `LangGraphMissionExecutor` từ Epic 26.
