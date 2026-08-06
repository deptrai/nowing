# Validation Report — Story 13.1: Canonical Persistence, Tenancy & Convention

**Ngày kiểm tra:** 2026-08-07  
**Story:** 13.1  
**Epic:** Epic 13 — Canonical Entity Storage & Multi-Domain Indexing  
**Trạng thái:** done  
**Baseline commit:** `72806b18de0df53071d7f310c1c3f7706cb12f96`  
**Người kiểm tra:** BMAD `bmad-create-story` validate (Phase 4.2)

---

## Tóm tắt (Executive Summary)

Story 13.1 đã được implement đầy đủ và merge qua commit `72806b18d`. Code hiện tại khớp với acceptance criteria trong epics.md và story gốc. File story gốc ở `_bmad-output/implementation-artifacts/stories/13-1-canonical-persistence-tenancy-convention.md` thiếu nhiều context quan trọng cho dev agent (đường dẫn file, version thư viện, git intelligence, test commands, architecture guardrails, change log). File cải tiến đã được tạo tại `_bmad-output/implementation-artifacts/13-1-canonical-persistence-tenancy-convention.md` để khắc phục các khoảng trống này. Không có bug nghiêm trọng nào được phát hiện trong quá trình validate.

---

## Critical Issues Found

1. **Không có critical issue trong code.** Story đã hoàn thành, tất cả acceptance criteria đều được implement.

---

## Enhancements Applied

1. **Bổ sung `baseline_commit` và `Status: done`.** Story file gốc không ghi commit baseline, gây khó khăn khi truy vết lịch sử.
2. **Thêm `Tasks / Subtasks` với `[x]`.** BMAD template yêu cầu danh sách task; story gốc chỉ có AC và Validation.
3. **Thêm `Dev Agent Record`.** Ghi lại agent model, debug references, completion notes, file list theo template.
4. **Thêm `Change Log`.** Liệt kê commit chính `72806b18d` và mô tả.
5. **Bổ sung `Dev Notes` đầy đủ:**
   - Tuân thủ AD-2, AD-27, AD-28, AD-24, AD-25.
   - Cấu trúc file project cụ thể với line numbers (`app/db.py` lines 3714-3937).
   - Yêu cầu testing với pytest commands.
   - `Previous story intelligence` từ Epic 3 (memory tables, pgvector/HNSW/GIN, Zero publication).
   - Chi tiết RLS, partial HNSW index, embedding status lifecycle, source uniqueness move.
   - Phiên bản thư viện (`alembic>=1.13.0`, `pgvector>=0.3.6`, SQLAlchemy 2.x async).
   - Git intelligence: files changed, baseline commit, related commits (13.2a-e, 13.3).
6. **Tối ưu LLM context:**
   - AC được đánh số và `[x]` để dễ scan.
   - Thêm bảng file structure.
   - Thêm test commands chính xác.
   - Ghi rõ file paths cho mọi reference.

---

## LLM Optimizations

1. **Cấu trúc rõ ràng hơn:** Story mới tách rõ Story, AC, Tasks, Dev Notes, Dev Agent Record, Change Log, References.
2. **Token efficiency:** Dev Notes dùng bullet + bảng thay vì đoạn văn dài.
3. **Unambiguous signals:** AC có checkbox `[x]` và mapping sang file/line cụ thể.
4. **Anti-pattern prevention:** Ghi rõ "Do not add PII redaction in 13.1" và "AD-28 storage ships before plugin engine" để tránh dev agent mở rộng sai scope.
5. **Git + previous intelligence:** Giúp dev agent tránh tái tạo pattern đã có (memory tables, RLS, Zero publication).

---

## Gaps in Original Story File (Non-Critical, Documentation Only)

| # | Gap | Tác động | Cách khắc phục trong file cải tiến |
|---|-----|----------|------------------------------------|
| 1 | Thiếu `baseline_commit` | Khó truy vết | Đã thêm |
| 2 | Thiếu `Tasks / Subtasks` checklist | BMAD template bị bỏ trống | Đã thêm với `[x]` |
| 3 | Không có `Dev Agent Record` | Không ghi lại quá trình implement | Đã thêm |
| 4 | Không có `Change Log` | Mất lịch sử thay đổi | Đã thêm |
| 5 | Thiếu file paths / line numbers | Dev agent phải tự tìm | Đã thêm trong Dev Notes và File List |
| 6 | Thiếu previous story intelligence | Có nguy cơ tái tạo pattern | Đã thêm từ Epic 3/memory tables |
| 7 | Thiếu test commands | Dev agent không biết verify | Đã thêm `pytest` + `ruff check` commands |
| 8 | Thiếu library versions | Có thể dùng sai version pgvector/SQLAlchemy | Đã thêm từ `pyproject.toml` |
| 9 | Thiếu architecture guardrails (AD-27/28) | Có thể mở rộng sai scope | Đã giải thích rõ ràng |

---

## Verification Performed

- [x] Đọc story gốc và epics.md (Epic 13, Story 13.1).
- [x] Đọc `app/db.py` canonical models (lines 3714-3937).
- [x] Đọc migration `193_add_canonical_entities.py`.
- [x] Đọc `app/canonical/tenant_context.py`, `canonical_persist_service.py`, `backfill_canonical_embedding.py`.
- [x] Đọc `app/services/bds_aggregator/dedupe.py`, `__init__.py`, `jobs_aggregator/dedupe.py`, `__init__.py`.
- [x] Đọc tests `tests/integration/canonical/test_canonical_persistence.py`, `test_canonical_embedding.py`, `tests/unit/canonical/test_canonical_conventions.py`.
- [x] Chạy `git log --oneline -15` để xác định baseline commit và related commits.
- [x] Kiểm tra `pyproject.toml` cho `pgvector`, `alembic`, SQLAlchemy versions.
- [x] Kiểm tra `app/zero_publication.py` cho canonical table columns.
- [x] Nghiên cứu web về `pgvector HNSW SQLAlchemy 2025` và `Alembic pgvector vector type migration`.
- [x] Đối chiếu với BMAD checklist `checklist.md`.
- [x] Không tạo file Python mới; chỉ tạo file markdown.

---

## Next Steps in Nowing Quality Pipeline

**Vừa xong:** `bmad-create-story` validate (Phase 4.2) — Story 13.1 đã done, chỉ validate lại tài liệu.

**Bước tiếp theo (BẮT BUỘC):**
- [x] 4.7 `bmad-dev-story` — Đã done cho 13.1 (baseline `72806b18d`).
- [x] 4.8 `bmad-code-review` — Đã được thực hiện trước khi merge (implied bởi trạng thái `done` trong sprint-status.yaml).

**Bước tiếp theo (recommended, có thể skip vì 13.1 đã done):**
- [ ] 4.3 `bmad-nowing-grill-me` — Recommended nếu story non-trivial (13.1 là P0, nhiều cross-domain nên có thể chạy để đảm bảo context đầy đủ). *(skip nếu chỉ làm documentation)*
- [ ] 4.4 `bmad-nowing-test-first-atdd` — Recommended cho story có AC. *(skip vì ATDD skeleton đã nằm trong test files từ baseline)*
- [ ] 4.6 `bmad-nowing-integration-test` — P0-gated; tests integration đã tồn tại và được chạy trong quá khứ. *(skip trừ khi chạy lại regression)*
- [ ] 4.10 `bmad-nowing-mutation-gate` — P0-gated; các file P0 đã chạm (RLS, pgvector) nên mutation gate đã áp dụng hoặc nên chạy lại khi có thay đổi code. *(không áp dụng vì chỉ thay đổi doc)*

**Còn lại trong pipeline:** Vì 13.1 đã done và chỉ cập nhật documentation, các bước 4.3-4.15 có thể coi là đã hoàn thành hoặc skip. Nếu cần regression, chạy `pytest tests/integration/canonical tests/unit/canonical -q` từ `nowing_backend/`.
