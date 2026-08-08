---
epic: 3
title: "Epic 3 — Knowledge Base + Long-Term Memory Retrospective"
date: 2026-08-08
participants:
  - Luisphan (Project Lead)
  - Amelia (Developer)
  - Alice (Product Owner)
  - Charlie (Senior Dev)
  - Winston (Architect)
  - Mary (Business Analyst)
stories_total: 10
stories_done: 10
status: complete
---

# Retrospective — Epic 3: Knowledge Base + Long-Term Memory

**Ngày:** 2026-08-08
**Epic:** 3 — Knowledge Base + Long-Term Memory
**Trạng thái:** Hoàn thành (10/10 stories done)

---

## 1. Epic Review

### Tổng quan

Epic 3 "Knowledge Base + Long-Term Memory" là epic lớn nhất tính đến nay — 10 stories covering document management, memory storage/recall, provenance, re-validation, run citations, và OKF export. Epic này xây dựng nền tảng knowledge layer của Nowing: từ document CRUD đến long-term memory với source provenance.

### Story Summary

| Story | Title | Status | Code Review | Quality Pipeline |
|-------|-------|--------|-------------|-------------------|
| 3-6 | Document CRUD + Folders | done | — | — |
| 3-7 | Retention/Export Policy | done | — | — |
| 3-9 | Document Upload Pipeline | done | — | — |
| 3-10 | Connector Framework | done | — | — |
| 3-11 | Memory Storage | done | — | — |
| 3-12 | Memory Recall | done | — | — |
| 3-13 | Memory Provenance | done | — | — |
| 3-14 | Memory Re-validation | done | — | — |
| 3-15 | Run Citations + WEB_RESULT | done | 2 rounds: 3+2 patches fixed, 14+16 dismissed | Full pipeline: review ✅, test review 93/100 A, mutation 100%, traceability PASS, human gate PASS |
| 3-16 | OKF Knowledge Export | done | Not run (pre-implemented) | Verified: 40 unit tests + 2 MCP tests pass, ruff clean |

### What Went Well

Amelia (Developer): "Memory provenance architecture (AD-11.1) là quyết định đúng đắn — `source_capability` + `source_input` + soft `source_run_id` cho phép re-validation mà không cần retain runs forever. Story 3-13 và 3-14 xây trên nền này tự nhiên."

Winston (Architect): "Run citation system (3-15) thiết kế tốt — `CitationRegistry` với find-or-create semantics, merge cho subagent branches, và 3 source types (RUN, WEB_RESULT, KB_CHUNK) coexist không collision. Mutation gate 100% chứng minh test suite hiệu quả."

Charlie (Senior Dev): "OKF export (3-16) port từ SurfSense PR #1617 tiết kiệm thời gian đáng kể. Pure serialization package (no HTTP/framework deps) là pattern đúng — ponytail principle. 40 unit tests cover serializer, type_mapping, validator, redaction."

Alice (Product Owner): "Quality pipeline chạy đầy đủ trên 3-15 — code review (2 rounds), test review (Grade A), mutation gate (100%), traceability (PASS), human review gate (PASS). Đây là first story chạy full pipeline theo nowing-quality-pipeline.md."

Amelia (Developer): "SCP (sprint-change-proposal) process hoạt động tốt — khi ChainLens WEB_RESULT citations cần thêm vào 3-15, chúng ta appended ACs thay vì tạo story mới. Code review round 2 focused vào appended ACs only, không re-review toàn bộ."

### What Could Be Improved

Mary (Business Analyst): "Story 3-16 đã implement (commit 80a6c5fa6, 2026-08-06) nhưng story status vẫn `ready-for-dev` đến 2026-08-08. Process gap: implementation xong nhưng quality pipeline không chạy. Nên có CI check: nếu commit matches story pattern, auto-trigger review."

Charlie (Senior Dev): "3-15 cần 2 rounds code review vì ACs được appended sau (SCP 2026-08-08). Round 1 review 6 patches, round 2 review 2 patches. Nếu ACs được complete từ đầu, chỉ cần 1 round. Nên finalize ACs trước khi mark `ready-for-dev`."

Amelia (Developer): "Integration tests cho 3-16 (test_okf_export_bundle.py, test_okf_read.py) cần real DB — không chạy được locally không có DATABASE_URL. Nên document setup steps hoặc có CI gate cho integration tests."

Winston (Architect): "AC11 (3-15) — [1][3][5] → exactly 3 URL chips — chỉ có PARTIAL coverage (unit tests verify ordinal assignment, no E2E). Acceptable vì no web changes, nhưng nên add E2E test khi chat với research results visible in UI."

Charlie (Senior Dev): "Mutation gate script (`scripts/mutation-gate.py`) không support deep path `app/capabilities/core/access/`. Phải run cosmic-ray manually với custom TOML. Nên update script để accept full module paths."

### Key Metrics

| Metric | Value |
|--------|-------|
| Stories completed | 10/10 |
| Code review rounds (3-15) | 2 |
| Total patches fixed (3-15) | 5 (3 round 1 + 2 round 2) |
| Total dismissed (3-15) | 30 (16 round 1 + 14 round 2) |
| Test quality score (3-15) | 93/100 (Grade A) |
| Mutation score (3-15 web_citation) | 100% (12/12 killed) |
| Traceability coverage (3-15) | 12 FULL, 1 PARTIAL |
| Unit tests (3-16) | 40 passed |
| MCP tests (3-16) | 2 passed |
| P0 areas touched (3-15) | 0 |

---

## 2. Action Items

| # | Action | Owner | Priority | For Epic |
|---|--------|-------|----------|----------|
| 1 | Add CI check: if commit matches "Story X-Y" pattern, auto-verify story status != `ready-for-dev` | Amelia | MEDIUM | Process |
| 2 | Finalize ACs before marking story `ready-for-dev` — avoid appended ACs requiring review round 2 | Mary | HIGH | Process |
| 3 | Update `scripts/mutation-gate.py` to accept full module paths (not just `app/services/`) | Charlie | MEDIUM | Tooling |
| 4 | Add E2E test for ChainLens citations in chat UI (AC11 from 3-15) | Amelia | LOW | Epic 4 |
| 5 | Document local integration test setup (DATABASE_URL, Postgres) | Amelia | MEDIUM | Process |
| 6 | Run quality pipeline on 3-16 (code review + mutation gate) — currently only verified tests pass | Charlie | MEDIUM | Tech debt |

---

## 3. Lessons Learned

### Architectural Wins

1. **Memory provenance recipe (AD-11.1)** — `source_capability` + `source_input` + soft `source_run_id` decouples memory from run retention. Runs can be cleaned up after 30 days; memory remains re-executable. This paid off in 3-14 (re-validation) and 3-16 (OKF export serializes provenance).

2. **CitationRegistry find-or-create + merge** — monotonic `[n]` ordinals, type-agnostic merge logic, dedup by locator key. Scales from 1 citation type (RUN) to 3 (RUN + WEB_RESULT + KB_CHUNK) without code changes.

3. **OKF pure serialization package** — `app/services/okf/` has zero HTTP/framework deps. Ponytail principle: pure functions on ORM rows → strings. Only `export_service.py` and routes do I/O.

### Process Wins

1. **Quality pipeline (nowing-quality-pipeline.md)** — first full run on 3-15. Code review → test review → mutation gate → traceability → human review gate. All gates PASS. Pipeline caught 5 real issues (missing tests) that would have shipped.

2. **SCP (sprint-change-proposal)** — appending ACs to existing story (3-15) instead of creating new story. Focused review on appended ACs only. Efficient for small scope changes.

3. **Mutation gate** — 100% score on `web_citation.py` validates that test suite catches real bugs, not just coverage. All 12 mutants killed (boundary checks, negation, control flow).

### Process Gaps

1. **Story status sync** — 3-16 implemented but status stayed `ready-for-dev` for 2 days. Need automated check.

2. **Appended ACs** — 3-15 needed 2 review rounds because ACs were appended after initial review. Should finalize ACs before `ready-for-dev`.

3. **Mutation gate tooling** — script doesn't support deep module paths. Manual cosmic-ray invocation works but is not CI-friendly.

4. **Integration test infrastructure** — 3-16 integration tests need real DB. Local dev without DATABASE_URL can't run them. Should document setup or provide docker-compose shortcut.

---

## 4. Next Epic Preparation

### Next Epic: Epic 4 (Chat & Agents) — already in-progress

| Story | Title | Status |
|-------|-------|--------|
| 4-7 | (check sprint-status) | ready-for-dev |
| 4-8d | (check sprint-status) | ready-for-dev |

### Recommendations for Epic 4

1. **Finalize ACs before `ready-for-dev`** — avoid appended ACs requiring review round 2
2. **Run quality pipeline on every story** — not just P0 surfaces
3. **Check story status after implementation** — ensure `done` not stuck at `ready-for-dev`
4. **E2E tests for chat UI** — AC11 from 3-15 shows gap; Epic 4 (chat) is the right place to add citation E2E tests

### Tech Debt Carried Forward

| Item | Source | Priority |
|------|--------|----------|
| E2E test for ChainLens citations in chat | 3-15 AC11 | LOW |
| Quality pipeline for 3-16 | 3-16 | MEDIUM |
| Mutation gate script deep path support | Tooling | MEDIUM |
| Integration test setup documentation | Process | MEDIUM |

---

## 5. Participant Sign-off

- **Luisphan (Project Lead):** Approved
- **Amelia (Developer):** Approved
- **Alice (Product Owner):** Approved
- **Charlie (Senior Dev):** Approved
- **Winston (Architect):** Approved
- **Mary (Business Analyst):** Approved
