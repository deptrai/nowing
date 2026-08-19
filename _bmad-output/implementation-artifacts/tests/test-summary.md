# Test Automation Summary — Nowing Full Stack

**Date:** 2026-08-19  
**Engineer:** QA Automation Engineer (BMAD QA Workflow)  
**Target Scope:** Comprehensive Automated E2E & API Test Suites (Stories 7.8, 26.5, 26.4, 24.1, 11.3)

---

## 1. Generated & Verified Test Suites

### 🌐 Frontend E2E Test Suites (Playwright)
- [x] [`nowing_web/tests/i18n/vietnamese-locale-detection.spec.ts`](file:///Users/luisphan/Documents/GitHub/nowing/nowing_web/tests/i18n/vietnamese-locale-detection.spec.ts) — Story 7.8: Vietnamese i18n & Geo Locale auto-detection, timezone heuristics (`Asia/Ho_Chi_Minh`), language switching, and `localStorage` preference persistence.
- [x] [`nowing_web/tests/leads/two-tier-phone-unlock.spec.ts`](file:///Users/luisphan/Documents/GitHub/nowing/nowing_web/tests/leads/two-tier-phone-unlock.spec.ts) — Story 26.5: Smart confirmation popover, 1-click fast unlock session, 150ms flip animation, 5s undo relock toast, and bulk phone unlock.
- [x] [`nowing_web/tests/leads/mission-control-glass-box.spec.ts`](file:///Users/luisphan/Documents/GitHub/nowing/nowing_web/tests/leads/mission-control-glass-box.spec.ts) — Story 26.5: 4-stage stepper (Crawl -> Reasoning -> Extraction -> Ingest), token velocity sparkline/costs, PII-safe redacted control view, and shimmer skeleton rows.
- [x] [`nowing_web/tests/smoke/dashboard.spec.ts`](file:///Users/luisphan/Documents/GitHub/nowing/nowing_web/tests/smoke/dashboard.spec.ts) — Core Dashboard authentication & layout tracer-bullet smoke test.

### 🔌 Backend API & Integration Test Suites (Pytest)
- [x] [`nowing_backend/tests/integration/routes/test_pii_opt_out.py`](file:///Users/luisphan/Documents/GitHub/nowing/nowing_backend/tests/integration/routes/test_pii_opt_out.py) — Story 26.4: Decree 13 PII opt-out, Fernet-encrypted vault purging, 15% anti-fraud refund cap, and DNC synchronization.
- [x] [`nowing_backend/tests/integration/routes/test_contact_relock.py`](file:///Users/luisphan/Documents/GitHub/nowing/nowing_backend/tests/integration/routes/test_contact_relock.py) — Story 26.5: Accidental unlock refund, 60s window verification, idempotency, and audit log generation.
- [x] [`nowing_backend/tests/integration/routes/test_dsh_mission_control.py`](file:///Users/luisphan/Documents/GitHub/nowing/nowing_backend/tests/integration/routes/test_dsh_mission_control.py) — Story 26.5: DSH public list and redacted control endpoints.
- [x] [`nowing_backend/tests/integration/routes/test_sequence_routes.py`](file:///Users/luisphan/Documents/GitHub/nowing/nowing_backend/tests/integration/routes/test_sequence_routes.py) — Story 24.1: Sequence CRUD, quiet-hour calculation, step ordering validation, and tenant scoping.
- [x] [`nowing_backend/tests/unit/services/test_sequencer_service.py`](file:///Users/luisphan/Documents/GitHub/nowing/nowing_backend/tests/unit/services/test_sequencer_service.py) — Story 24.1: Inbound interruption, quiet-hour formula (`08:00 - 21:30 VN Time`), and consent gating.
- [x] [`nowing_backend/tests/unit/gateway/test_telegram_commands.py`](file:///Users/luisphan/Documents/GitHub/nowing/nowing_backend/tests/unit/gateway/test_telegram_commands.py) — Story 11.3: `/status`, `/run <name>`, permission checks (`AUTOMATIONS_READ`, `AUTOMATIONS_EXECUTE`), and onboarding replies.
- [x] [`nowing_backend/tests/integration/gateway/test_telegram_inbox.py`](file:///Users/luisphan/Documents/GitHub/nowing/nowing_backend/tests/integration/gateway/test_telegram_inbox.py) — Story 11.3: Inbound event processor, callback queries (`view_run:`, `rerun:`), and `answer_callback_query` guarantees.

---

## 2. Coverage Metrics

| Feature / Story | Area | Test Types | Key Acceptance Criteria Covered |
|---|---|---|---|
| **Story 7.8**: Vietnamese i18n & Geo Locale | Frontend Web | Playwright E2E | `vi-VN` auto-detect, VN timezone auto-detect, LanguageSwitcher, `localStorage` persistence |
| **Story 26.5**: Split Canvas Glass Box & Phone Unlock | Fullstack | Playwright E2E + Pytest Integration | 4-stage stepper, token velocity, Smart popover, fast-unlock session, 5s undo relock, bulk unlock |
| **Story 26.4**: PII Vault & Decree 13 Opt-Out | Backend Core | Pytest Integration | AES-256 Fernet purge, HMAC deduplication, 15% refund limit, DNC record sync |
| **Story 24.1**: Drip Outreach Sequence Engine | Backend Core | Pytest Unit + Integration | Quiet hours (`08:00 - 21:30`), Redis lock CAS, BillingEvent ledger, Inbound STOP opt-out |
| **Story 11.3**: Telegram Interactive Bot & Webhook | Backend Gateway | Pytest Unit + Integration | `/status`, `/run`, `callback_query`, fail-closed RBAC, answerCallbackQuery guarantee |

---

## 3. Execution & Verification Commands

### Frontend E2E (Playwright)
```bash
cd nowing_web
# Run newly generated i18n E2E suite
pnpm test:e2e tests/i18n/vietnamese-locale-detection.spec.ts

# Run Lead Intelligence & Phone Unlock E2E suites
pnpm test:e2e tests/leads/two-tier-phone-unlock.spec.ts tests/leads/mission-control-glass-box.spec.ts

# Run all E2E tests
pnpm test:e2e
```

### Backend Unit & Integration Tests (Pytest)
```bash
cd nowing_backend
# Run unit tests (independent of DB)
uv run pytest tests/unit/gateway/ tests/unit/services/test_sequencer_service.py tests/unit/services/test_billing_event_service.py -q

# Run integration tests (with PostgreSQL 5434 + Redis 6380)
uv run pytest tests/integration/routes/test_pii_opt_out.py tests/integration/routes/test_contact_relock.py tests/integration/routes/test_dsh_mission_control.py tests/integration/routes/test_sequence_routes.py tests/integration/gateway/test_telegram_inbox.py -q
```

---

## 4. Next Steps
- Integrate `tests/i18n/vietnamese-locale-detection.spec.ts` into the CI deployment gate.
- Maintain test fixtures when expanding multi-channel sequencing (Zalo ZNS / Telegram outbound) in future epics.
