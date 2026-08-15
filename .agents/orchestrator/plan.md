# Plan: Epic 21 Lead Gen Intelligence (Strict BMad Pipeline)

## Phase 0: Discovery & Comprehensive Story Status Audit
- [ ] 0.1 Audit all Stories 21.1 to 21.7 across `nowing_backend/`, `tests/`, and `_bmad-output/`:
  - **Story 21.1 (Intent Signal Detection)**: Audit codebase, models, tests, verification status.
  - **Story 21.2 (Lead Scoring Engine)**: Audit codebase, models, tests, verification status.
  - **Story 21.3 (Contact Enrichment & PII Governance)**: Audit status (models, services, tests).
  - **Story 21.4 (Outbound Prospecting Sequencer)**: Audit status.
  - **Story 21.5 (CRM Integration & Write-Back)**: Audit status.
  - **Story 21.6 (Multi-Channel Prospecting Delivery)**: Audit status.
  - **Story 21.7 (Outcome-Based Pricing & ROI Tracking)**: Audit status.
- [ ] 0.2 Synthesize Survey & Audit into `PROJECT.md` with Feature Inventory, Status Matrix, and Execution Roadmap.

## Phase 1: Sequential Story Execution via BMad Pipeline
For each story identified as PARTIAL or BACKLOG (order: 21.3 -> 21.4 -> 21.5 -> 21.6 -> 21.7):
1. **bmad-create-story**: Create / standardize story spec file in `_bmad-output/implementation-artifacts/stories/`.
2. **bmad-testarch-atdd**: Generate red-phase acceptance test scaffolds (`tests/unit/lead_intelligence/`, `tests/integration/lead_intelligence/`). Verify red tests fail cleanly.
3. **bmad-dev-story**: Implement models, migrations, services, capabilities, routes to make all tests green.
4. **bmad-code-review**: Multi-layer adversarial review (Blind Hunter, Edge Case Hunter, Acceptance Auditor), Challengers, Forensic Auditor (`teamwork_preview_auditor`), and mutation testing check.
5. **bmad-sprint-status**: Update sprint status and document completion.

## Phase 2: Epic 21 Verification Gates
- [ ] Full unit test suite pass: `uv run pytest tests/unit/lead_intelligence/ -q`
- [ ] Full integration test suite pass: `uv run pytest tests/integration/lead_intelligence/ -q`
- [ ] Linter & formatter check: `ruff check app/lead_intelligence tests/unit/lead_intelligence tests/integration/lead_intelligence`, `ruff format`
- [ ] Forensic integrity audit across entire Epic 21.

## Phase 3: Final Handoff & Victory Claim
- [ ] Compile comprehensive `handoff.md` with complete evidence chain and test artifacts.
- [ ] Issue Victory Claim to parent.
