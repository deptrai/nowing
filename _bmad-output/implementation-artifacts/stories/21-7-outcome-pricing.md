# Story 21.7: Outcome-Based Pricing

Status: ready-for-dev

## Story

As a sales team,
I want to pay per qualified meeting booked (not just per seat),
So that cost is tied to actual pipeline value delivered.

## Acceptance Criteria

- Given a pricing plan, when selected, then outcome-based option is available: pay per qualified meeting booked OR pay per lead enriched
- Given a meeting is booked via Nowing outreach, when confirmed, then the cost is attributed to the workspace
- Given usage, when tracked, then the dashboard shows cost-per-meeting and cost-per-lead metrics
- Given outcome events, when attributed, then first-touch attribution model is applied

## Tasks / Subtasks

- [ ] Task 1: Outcome Tracking
  - [ ] 1.1 Create `OutcomeEvent` model (id, workspace_id, event_type, lead_id, sequence_id, attribution, cost_micros)
  - [ ] 1.2 Track meeting booked (calendar event from Nowing outreach)
  - [ ] 1.3 Track lead enriched (verified contact delivered)
- [ ] Task 2: Attribution Model
  - [ ] 2.1 First-touch attribution (sequence that started the journey)
  - [ ] 2.2 Multi-touch tracking (for future enhancement)
  - [ ] 2.3 Cost attribution to workspace
- [ ] Task 3: Pricing Plans
  - [ ] 3.1 Create `PricingPlan` model (id, workspace_id, plan_type, seat_price, outcome_rates_json)
  - [ ] 3.2 Support dual pricing: seat-based + outcome-based
  - [ ] 3.3 Integration with existing Stripe billing
- [ ] Task 4: Dashboard Metrics
  - [ ] 4.1 Cost-per-meeting metric
  - [ ] 4.2 Cost-per-lead-enriched metric
  - [ ] 4.3 ROI calculator (pipeline value / cost)

## Dev Notes

- **AD-42:** Outcome-based pricing support
- **Source:** `app/services/outcome_tracking.py`, `app/routes/pricing_routes.py`
- **Integration:** Reuses existing credit wallet (AD-8) + Stripe

### References

- [Source: epics.md §FR-69]
- [Source: epic21-architecture-update.md §AD-42]

## Dev Agent Record

### Agent Model Used

{{agent_model_name_version}}

### File List

Created: 2026-08-10
