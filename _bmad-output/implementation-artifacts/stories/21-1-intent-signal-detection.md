# Story 21.1: Intent Signal Detection

Status: ready-for-dev

## Story

As a salesperson,
I want to detect buying signals from companies (funding, hiring, tech stack, executive moves),
So that I can reach out at the right moment.

## Acceptance Criteria

Given a company in workspace, when signals are monitored, then funding events, job postings, tech stack changes, and executive moves are detected and surfaced with signal type, confidence, source URL, and timestamp.

Given multiple signals for the same company, when aggregated, then a composite lead score is calculated.

Given a new signal is detected, when created, then it triggers a notification (in-app + optional Telegram) to workspace owners.

Given signal data, when stored, then it includes: company_name, signal_type, source_url, confidence (0-100), detected_at, raw_snippet.

## Tasks / Subtasks

- [ ] Task 1: Signal Detection Engine (AC: 1, 2)
  - [ ] 1.1 Create `SignalEvent` model (id, workspace_id, company_name, signal_type, source_url, confidence, detected_at, raw_snippet, processed)
  - [ ] 1.2 Create `SignalSubscription` model (id, workspace_id, signal_types[], notification_channels[])
  - [ ] 1.3 Implement `SignalDetectionService` as Celery task (daily scan + real-time webhook handler)
  - [ ] 1.4 Integrate with existing scrapers (FR-6) for data collection
  - [ ] 1.5 Register as AlertRule template type (governed by AD-33)

- [ ] Task 2: Signal Sources Integration (AC: 1)
  - [ ] 2.1 Funding signals: Crunchbase API + TechCrunch RSS feeds (buy)
  - [ ] 2.2 Hiring signals: Job board monitoring (build on existing scrapers)
  - [ ] 2.3 Tech stack signals: Website change detection (build)
  - [ ] 2.4 Executive move signals: LinkedIn monitoring (build on existing scrapers)
  - [ ] 2.5 News signals: News API (buy) + RSS feeds (build)

- [ ] Task 3: Signal Aggregation & Scoring (AC: 2)
  - [ ] 3.1 Implement signal aggregation logic (multiple signals → composite score)
  - [ ] 3.2 Create `LeadScore` model (id, workspace_id, company_name, score, fit_score, intent_score, factors_json, computed_at)
  - [ ] 3.3 Integrate with existing Memory layer (store scores as Memory rows with type 'semantic' + tag 'lead_score')

- [ ] Task 4: Notifications (AC: 3)
  - [ ] 4.1 Create signal detection notification (in-app + Telegram)
  - [ ] 4.2 Reuse existing NotificationService + TelegramAdapter
  - [ ] 4.3 Respect user notification preferences (FR-31)

- [ ] Task 5: REST API & MCP Tools
  - [ ] 5.1 Create `/workspaces/{id}/signals` endpoints (list, create, search)
  - [ ] 5.2 Create `/workspaces/{id}/signals/subscriptions` endpoints
  - [ ] 5.3 Create MCP tools: `nowing_list_signals`, `nowing_subscribe_signals`
  - [ ] 5.4 Add TokenUsage tracking for signal detection operations

## Dev Notes

### Architecture Patterns & Constraints

- **AD-33 Compliance:** Signal Engine MUST be an AlertRule template type, not a new service. Reuse existing Automation scheduler (Celery Beat) + notification dispatch.
- **AD-18 Compliance:** Signal data stored in workspace Memory layer (namespace isolation). Use existing `Memory` model with `source_type = 'SIGNAL_EVENT'`.
- **AD-2 Compliance:** All DB I/O uses AsyncSession. Create Alembic migration for new tables.
- **AD-3 Compliance:** Signal detection capabilities register as scraper capabilities (`app/capabilities/<platform>/`) with self-registering routes.
- **AD-34 Compliance:** Signal data feeds `chainlens-research` via `Chunk[]` → `POST /v1/ingest/scraper` for indexing.

### Source Tree Components to Touch

```
nowing_backend/
├── app/
│   ├── capabilities/
│   │   └── signals/
│   │       ├── definition.py          # NEW: capability registration
│   │       ├── executor.py            # NEW: signal detection logic
│   │       └── schemas.py             # NEW: input/output schemas
│   ├── services/
│   │   ├── signal_detection.py        # NEW: core detection service
│   │   └── signal_aggregation.py      # NEW: scoring logic
│   ├── routes/
│   │   └── signals_routes.py          # NEW: REST endpoints
│   ├── tasks/
│   │   └── signal_tasks.py            # NEW: Celery tasks (daily scan + webhook)
│   ├── db.py                          # UPDATE: add SignalEvent, LeadScore models
│   ├── mcp_tools.py                   # UPDATE: register signal MCP tools
│   └── notifications/
│       └── constants.py               # UPDATE: add signal notification types
├── alembic/
│   └── versions/
│       └── 194_add_signal_tables.py   # NEW: migration
└── tests/
    └── unit/
        └── capabilities/
            └── signals/
                └── test_detection.py  # NEW: unit tests
```

### Key Dependencies

| Dependency | Version | Purpose |
|------------|---------|---------|
| APScheduler (existing) | — | Signal monitoring schedule (daily) |
| Celery (existing) | — | Async signal processing |
| BeautifulSoup/httpx (existing) | — | Web scraping for signals |
| NewsAPI | Latest | News signal feed |
| Crunchbase API | v4 | Funding signal feed |

### Testing Standards

- Unit tests: Pytest with 90% coverage (existing standard)
- Integration tests: Transactional DB sessions (existing fixture)
- Contract tests: SSE stream parsing for real-time signals
- Eval tests: Signal detection accuracy on `nowing_evals`

### Signal Types & Detection Methods

| Signal Type | Source | Detection Method | Frequency |
|-------------|--------|------------------|-----------|
| `funding` | Crunchbase, TechCrunch | API polling + RSS webhook | Daily |
| `hiring` | Job boards | Scraper monitoring | Daily |
| `tech_stack` | Company websites | Website change detection | Daily |
| `executive_move` | LinkedIn | Scraper monitoring | Daily |
| `news` | News API, RSS | API polling + RSS webhook | Daily |

### Scoring Algorithm

```
Composite Score = (Fit Score × 0.5) + (Intent Score × 0.5)

Fit Score = Company Size + Industry Match + Location + Tech Stack Match
Intent Score = Signal Strength × Recency Multiplier

Recency Multiplier:
- Last 7 days: 1.0
- Last 30 days: 0.7
- Last 90 days: 0.4
- Older: 0.1
```

### Project Structure Notes

- Alignment with unified project structure: All signal code under `app/capabilities/signals/`
- Detected conflicts: None — new capability follows existing AD-3 pattern
- Naming convention: `SignalEvent` (not `Signal`), `LeadScore` (not `Score`)

### UX Integration

- Signal events display in Data Panel "Signals" tab (per `epic21-lead-intelligence-ux.md`)
- Signal chips appear in chat context when relevant
- Filter chips for signal type, date range, confidence

### References

- [Source: `_bmad-output/planning-artifacts/epics.md` §Epic 21: Lead Gen Intelligence]
- [Source: `_bmad-output/planning-artifacts/architecture/epic21-architecture-update.md` §AD-37]
- [Source: `_bmad-output/planning-artifacts/ux-design/epic21-lead-intelligence-ux.md` §Story 21.1]
- [Source: `_bmad-output/planning-artifacts/research/technical-ai-lead-intelligence-origami-architecture-research-2026-08-10.md` §Key Lessons]
- [Source: `nowing_backend/app/capabilities/` — existing capability pattern]
- [Source: `nowing_backend/app/services/` — existing service pattern]
- [Source: `nowing_backend/app/automations/` — AD-33 AlertRule template pattern]

## Dev Agent Record

### Agent Model Used

{{agent_model_name_version}}

### Debug Log References

### Completion Notes List

### File List

### Timestamp

Created: 2026-08-10
Last Updated: 2026-08-10
