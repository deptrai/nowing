# Story 21.2: Lead Scoring & Prioritization

Status: ready-for-dev

## Story

As a sales manager,
I want leads scored and ranked by conversion likelihood,
So that my team focuses on the highest-value prospects.

## Acceptance Criteria

Given a set of leads, when scored, then each lead receives a composite score based on fit (firmographics, technographics) and intent (signal strength, recency).

Given a lead score, when displayed, then it shows score breakdown (fit vs intent), trend (improving/declining), and comparison to similar converted leads.

Given ICP criteria, when updated, then lead scores are recalculated for all leads in workspace.

Given scoring results, when stored, then they are persisted as Memory rows with type 'semantic' and tag 'lead_score'.

## Tasks / Subtasks

- [ ] Task 1: Scoring Engine (AC: 1, 2)
  - [ ] 1.1 Create `LeadScore` model (id, workspace_id, company_name, score, fit_score, intent_score, factors_json, computed_at)
  - [ ] 1.2 Implement `LeadScoringService` with weighted scoring algorithm
  - [ ] 1.3 Create scoring API: `POST /workspaces/{id}/leads/score`
  - [ ] 1.4 Create scoring API: `GET /workspaces/{id}/leads/scores`

- [ ] Task 2: Fit Score Calculation (AC: 1)
  - [ ] 2.1 Company size scoring (employee count, revenue)
  - [ ] 2.2 Industry match scoring (ICP alignment)
  - [ ] 2.3 Location scoring (target geography)
  - [ ] 2.4 Tech stack scoring (technology alignment)

- [ ] Task 3: Intent Score Calculation (AC: 1)
  - [ ] 3.1 Signal strength scoring (from Story 21.1 SignalEvent data)
  - [ ] 3.2 Recency multiplier (7d=1.0, 30d=0.7, 90d=0.4, older=0.1)
  - [ ] 3.3 Signal type weighting (funding > hiring > tech_stack > news > executive_move)

- [ ] Task 4: Score Display & UX (AC: 2)
  - [ ] 4.1 Fit Score badge component (color-coded: green 80-100, yellow 50-79, red 0-49)
  - [ ] 4.2 Score breakdown tooltip (fit vs intent components)
  - [ ] 4.3 Trend indicator (improving/declining based on signal history)

- [ ] Task 5: ICP-based Recalculation (AC: 3)
  - [ ] 5.1 Listen for ICP criteria updates
  - [ ] 5.2 Trigger async recalculation of all lead scores
  - [ ] 5.3 Log recalculation results for audit

- [ ] Task 6: Memory Integration (AC: 4)
  - [ ] 6.1 Store scores as Memory rows (type='semantic', tag='lead_score')
  - [ ] 6.2 Link scores to ResearchThread for context continuity
  - [ ] 6.3 Expose via existing memory search API

## Dev Notes

### Architecture Patterns & Constraints

- **AD-18 Compliance:** Scores stored in workspace Memory layer (namespace isolation)
- **AD-2 Compliance:** All DB I/O uses AsyncSession
- **AD-11.1 Compliance:** Score Memory rows include `source_capability` + `source_input` for re-validation

### Scoring Algorithm

```
Composite Score = (Fit Score × 0.5) + (Intent Score × 0.5)

Fit Score (0-100):
- Company Size: 0-20 (based on employee count/revenue)
- Industry Match: 0-20 (ICP alignment)
- Location: 0-20 (target geography match)
- Tech Stack: 0-20 (technology alignment)
- Data Completeness: 0-20 (how much data we have)

Intent Score (0-100):
- Signal Strength: 0-40 (number + type of signals)
- Recency: 0-30 (weighted by signal age)
- Engagement: 0-30 (website visits, content consumption)

Recency Multiplier:
- Last 7 days: 1.0
- Last 30 days: 0.7
- Last 90 days: 0.4
- Older: 0.1
```

### Source Tree Components to Touch

```
nowing_backend/
├── app/
│   ├── services/
│   │   └── lead_scoring.py            # NEW: scoring engine
│   ├── routes/
│   │   └── lead_scoring_routes.py     # NEW: REST endpoints
│   ├── db.py                          # UPDATE: add LeadScore model
│   └── mcp_tools.py                   # UPDATE: register scoring MCP tools
├── alembic/
│   └── versions/
│       └── 195_add_lead_score.py      # NEW: migration
└── tests/
    └── unit/
        └── services/
            └── test_lead_scoring.py   # NEW: unit tests
```

### References

- [Source: `_bmad-output/planning-artifacts/epics.md` §FR-64]
- [Source: `_bmad-output/planning-artifacts/architecture/epic21-architecture-update.md` §AD-38]
- [Source: `_bmad-output/planning-artifacts/ux-design/epic21-lead-intelligence-ux.md` §Fit Score Badge]

## Dev Agent Record

### Agent Model Used

{{agent_model_name_version}}

### Debug Log References

### Completion Notes List

### File List

### Timestamp

Created: 2026-08-10
