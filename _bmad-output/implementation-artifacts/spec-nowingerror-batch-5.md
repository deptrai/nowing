---
title: NowingError & Exception Narrowing — Batch 5 (Remaining Core Services)
type: refactor
created: '2026-09-13'
status: done
baseline_commit: e203b85254102216a43d17efee243994206536b2
review_loop_iteration: 0
context:
  - nowing_backend/app/exceptions.py
  - nowing_backend/app/services/ (remaining unannotated sites)
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** Sau Batch 1–4 (277 sites) vẫn còn 105 call-sites `except Exception` chưa annotate trên 45 files thuộc các core services còn lại: meeting minutes & presentation pipelines, aggregators (jobs/bds/scraper), auto-reply agent, social copilot, sequencer dispatch, indexing/TTS/export services, cùng 6 sites lọt lại từ các batch trước.

**Approach:** Refactor Batch 5 gồm 105 call-sites `except Exception` trên 45 files:
1. Meeting Minutes & Presentation (`meeting_minutes/`, `presentation/`): bắt lỗi diarization, LLM summarization, pptx/marp driver — trả về kết quả lỗi có cấu trúc, không crash pipeline.
2. Aggregators (`jobs_aggregator/`, `bds_aggregator/`, `scraper_*`): best-effort per-source/per-item failure; pipeline tiếp tục với các nguồn còn lại.
3. Auto-reply & sequencers (`auto_reply_agent`, `sequencer/`, `inbound_debounce`): lỗi một item không dừng dispatch loop.
4. Misc services (TTS, export, indexer, governance): narrow hoặc annotate rationale theo convention `except Exception:  # <lý do>`.

## Boundaries & Constraints

**Always:**
- Giữ nguyên business logic và return contracts.
- Per-item failures trong loop phải log và tiếp tục item kế tiếp.
- Critical path (DB persistence, billing) re-raise typed hoặc rollback.
- Chạy tests liên quan sau khi sửa.

**Never:**
- Không nuốt lỗi mà không có log/rationale.
- Không thay đổi public signatures.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|---------------|----------------------------|----------------|
| Diarization fail | Audio segment bad | Partial transcript với warning | Best-effort per-segment |
| Scraped item parse fail | Malformed HTML | Skip item, continue batch | Log warning, per-item |
| Sequencer dispatch fail | 1 enrollment lỗi | Enrollment marked failed, loop tiếp tục | Log + continue |
| TTS/provider fail | Upstream 5xx | Typed error hoặc fallback voice | Log rõ ràng |

</frozen-after-approval>

## Code Map

- `app/exceptions.py` — NowingError hierarchy.
- Files với nhiều sites nhất: `meeting_minutes/service.py` (7), `auto_reply_agent.py` (7), `scraper_rules_service.py` (6), `presentation/service.py` (6), `jobs_aggregator/orchestrator.py` (5), `docling_service.py` (5), `scraper_rule_metrics.py` (4), `bds_aggregator/orchestrator.py` (4) — còn lại 1–3 sites/file trên 37 files.

## Tasks & Acceptance

**Execution:**
- [x] Annotate/narrow 105 call-sites trên 45 files
- [x] Verify tests & ruff check

**Acceptance Criteria:**
- 100% call-sites `except Exception` trong `app/services/` được narrow hoặc annotate rationale.
- Tests liên quan pass; `ruff check` sạch trên files đã sửa.
