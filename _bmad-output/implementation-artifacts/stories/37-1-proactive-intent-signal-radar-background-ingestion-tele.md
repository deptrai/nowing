---
story_key: 37-1-proactive-intent-signal-radar-background-ingestion-tele
status: done
baseline_commit: '205236aa6dc57356855d2e64202104cd90cace68'
epic: 37
priority: P1
target_codebase: nowing_backend
architectural_invariants: [AD-115]
---

# Story 37.1: Proactive Intent Signal Radar (Background Ingestion & Telegram Stream Matcher)

**Status:** `ready-for-dev`  
**Epic:** Epic 37: Nowing Revenue Engine — Unified Outbound Workstation  
**Priority:** P1  
**Target Codebase:** `nowing_backend`  
**Architectural Alignment:** Extends `SignalDetectionService` (`app/lead_intelligence/signals/service.py`), `LeadAssignmentService` (`app/services/lead_assignment_service.py`), and Telegram stream pipeline (`stream:telegram:raw_events`).

## Story

As a Growth / RevOps Engineer,  
I want a background daemon and stream listener that proactively scans hiring spikes, newly registered tax codes, and Telegram buy-requests,  
So that buying-intent leads are captured into the workspace matrix without requiring manual query triggers.

## Acceptance Criteria

- **AC-1 (Periodic Signal Scanner):** Celery Beat task `scan_high_intent_companies_periodic` executes every 6 hours, scanning hiring surges ($\ge 3$ new job postings in 7 days across TopCV/VietnamWorks) and newly incorporated tax codes from `masothue.com`/`dangkykinhdoanh.gov.vn`, persisting `SignalEvent` records with `intent_score >= 0.75`.
- **AC-2 (Aho-Corasick Telegram Stream Intent Matcher):** A consumer worker listening to Redis stream `stream:telegram:raw_events` runs an in-memory compiled Aho-Corasick keyword trie ($O(n)$) per AD-115 to pre-filter messages matching purchase intent patterns ("cần tìm nhà cung cấp", "báo giá", "tìm agency", "thuê ngoài"), extracts contact info, and creates an enriched `Lead` assigned round-robin via `LeadAssignmentService`.
- **AC-3 (Zero-Credit Penalty for Missing Contact):** If a Telegram intent message contains NO extractable phone or email, the system creates an Unqualified Signal Lead with `status='pending_enrichment'` and does NOT deduct workspace credits until contact data is resolved.
- **AC-4 (Budget Guardrails & Rate Limits):** Background scanning enforces AD-115 budget caps: maximum 100 scans per workspace per day, pausing automatically if credit balance falls below 50 credits.

## Review Triage Log

**2026-09-22 — 3 layers (blind-hunter / edge-case-hunter / verification-gap), ~35 findings sau dedup.**

| Finding | Verdict | Route | Evidence |
|---|---|---|---|
| `xgroup_create(id="0")` replays toàn bộ backlog lần đầu | high | patch | `id="$"` — group mới chỉ đọc message mới |
| `company_name` fallback → hmac collapse mọi sender trong 1 channel thành 1 lead | high | patch | fold `sender_id`/`message_id` vào hmac material khi thiếu sender name |
| `enriched=has_contact` — không VerifiedContact, downstream skip waterfall | medium | patch | `enriched=False`, `needs_enrichment=True` luôn; waterfall materialize contact |
| Workspace enum không filter archived/paused | medium | patch | `archived_at`/`scrape_paused_at IS NULL` |
| Dedupe check sau `_incr_scan_count` + scrape → đốt budget | medium | patch | reorder dedupe trước scan/scrape |
| Undated `posted_at` tính vào "≥3 trong 7 ngày" | medium | patch | chỉ count dated-in-window (AC fidelity) |
| Incorporation loop bị hiring starve + `_persist` không try/except + name >200 ValidationError | medium | patch | incorporation trước, per-item try/except, truncate 200 |
| `_resolve_workspace_id` tin tưởng explicit id + `.limit(1)` không ORDER BY | medium | patch | `session.get` validate + `order_by` deterministic |
| Scan counter fail-open khi Redis lỗi + INCR/EXPIRE non-atomic | medium | patch | fail-closed (return MAX) + `SET NX EX` + `INCR` |
| DKKD names↔tax_codes index pairing misalign | low | patch | chỉ pair khi len bằng nhau, else None |
| DKKD fetch thiếu User-Agent; masothue empty-parse silent | low | patch | UA header + `empty_parse` degradation reason |
| Matcher: multi-space miss; non-string source_url; `client_id=None` vs `"default"`; entities non-list; `batch_size<=0`; `lookback_days=0`; consent hardcode; trie fail-link dedupe; billing docstring | low | patch | từng cái 1–3 dòng |
| Throughput ceiling ~10msgs/30s | medium | patch | `batch_size=100, max_loops=3` (~300/tick) |
| Vacuous assignment test (lead.id None), thiếu test: workspace-resolve positive, DLQ+xack, `detect("incorporation")` | medium | patch | +5 tests, `_FakeSession.flush` gán uuid |
| Pool guard (workspace) vs debit (user wallet) — 2 hệ credit | medium | defer | cần policy: pool nào là "workspace credits"; record_signal_scan theo convention hiện có |
| Broadcast incorporation listing tới mọi workspace không relevance filter | low | defer | AC-literal; revisit nếu spam |
| Thiếu lag/DLQ-depth metric; word-boundary matching; overlap-scan race; `record_signal_scan` commit giữa scan | low | defer | observability/hardening sau |
| `-NNN` branch suffix truncate trong `_TAX_CODE_RE` | false | reject | intentional — capture group ngoài suffix |
| `stream:telegram:raw_events` không có producer in-repo | — | note | AC-2 consumer inert tới khi producer ngoài push; environmental |

**Verification post-patch:** ruff clean (touched files); 59/59 tests pass (27 radar + 28 signal detection + 4 telegram listener).

## Live Verification (2026-09-22)

`scripts/verify_intent_radar_37_1.py` chạy trên **Redis 6380 + Postgres thật**: **17/17 PASS**.

- Matcher 8/8 cases + 12 patterns compiled; Celery tasks registered, beat 6h + 30s đúng.
- Consumer E2E: 3 messages thật vào `stream:telegram:raw_events` → 2 leads persist (`new` có phone, `pending_enrichment` không contact), activity logs + extracted phone đúng, stream acked hết, DLQ rỗng.
- AC-4: `paused_low_credit` (ws 0 credits) + `budget_exhausted` (100/day) đúng.
- `fetch_new_incorporations` live HTTP: **25 công ty thật** từ masothue (URL đã fix: `/tra-cuu-ma-so-thue-doanh-nghiep-moi-thanh-lap` — URL cũ `/tra-cuu-ma-so-thue-moi` trả 404); DKKD vẫn 404 → degradation reason `dkkd.http_404`, không crash.
- Scan happy path: 2 `SignalEvent` incorporation (conf ≥75) persist thật + signal memories, cleanup sạch.

**Env drift phát hiện & đã fix (pre-existing, không phải story code):** `.env.local` pin `EMBEDDING_MODEL=ollama/nomic-embed-text` (768-dim) nhưng 4 cột config-derived (`memories`/`documents`/`chunks`/`social_posts`) được migrate dưới model 384-dim → mọi write fail. Đã repair bằng `scripts/fix_embedding_dim_drift.py`: alter 384→768 + re-embed **1453 vectors thật** qua ollama nomic (memories 5, documents 19, chunks 1429) + recreate 4 HNSW indexes. Verify re-run **17/17 PASS không workaround**.
