# Epic 21 UX Hand-off — Lead Intelligence (2026-08-11 refresh)

**Date:** 2026-08-11
**Author:** Sally (UX Designer) + Architecture validation
**Audience:** PO, Engineering, Business/Legal
**Scope:** UX contracts and UI states for Epic 21 (Lead Gen Intelligence), refreshed after `bmad-architecture` validate.

**Status:** ✅ **UX contracts ready** — architecture FIT; **engineering sliceable after governance gates close**.

---

## 1. What is ready

All eight new patterns (N1–N8) now have UX contracts, and the canonical architecture (AD-31, AD-33, AD-36–AD-42) has been validated:

| ID | Pattern | Priority | Contract / Location | Status |
|---|---|---|---|---|
| N1 | Sidebar onboarding checklist | P1 | `ux-contract-sidebar-onboarding.md` | Contracted |
| N2 | Workspace mode switch (Outbound / Research / Content) | P1 | `ux-contract-workspace-mode-switch.md` | Contracted |
| N3 | Tables directory / lead lists library | P2 | `ux-contract-tables-directory.md` | Contracted |
| N4 | Inbox empty state + Email only; lead source from all scrapers | P0 | `ux-contract-lead-intelligence-panel.md` §8 | Contracted |
| N5 | Positive-reply / delivery / bounce notifications (email/Telegram; Zalo disabled) | P1 | `ux-contract-positive-reply-notifications.md` | Contracted |
| N6 | Per-lead projected cost inline | P1 | `ux-contract-lead-intelligence-panel.md` §7 | Contracted |
| N7 | Source-specific table tabs (dynamic, all scraper/connector sources) | P2 | `ux-contract-lead-intelligence-panel.md` §2.1 | Contracted |
| N8 | “Connect a campaign” status chip | P1 | `ux-contract-lead-intelligence-panel.md` §5 | Contracted |

Canonical Epic 21 UX doc and addendum also updated:
- `epic21-lead-intelligence-ux.md` §10 maps N1–N8 to contracts and evidence.
- `ux-contract-epic21-addendum-2026-08-11.md` is the trace/proposed source; status is **merged** into canonical contracts.

Research evidence:
- Final report: `ux-research-origami-final-2026-08-11.md`
- Screenshots: `evidence/origami-*-2026-08-11.*`

---

## 2. Architecture-enforced implementation constraints

The following are non-negotiable from `ARCHITECTURE-SPINE.md` and `epics.md`:

### Data model
- Every Epic 21 table has `id: UUID`, `workspace_id`, and `client_id` (AD-31). UI must filter all lead/sequence/outcome views by active `client_id`.
- `Sequence`, `SequenceStep`, `SequenceEnrollment`, `SequenceEvent`, `SequenceRun` are first-class tables. `Sequence` is **not** an `Automation` subtype (AD-39).
- `BillingEvent` is the canonical ledger for business events (`contact_enrichment`, `lead_scoring`, `outcome_meeting_booked`, `outcome_lead_enriched`, `signal_scan`, `email_send`). `TokenUsage` is only for LLM token consumption (AD-8, AD-10, AD-42).

### Lead source discovery
- Lead sources come from `CapabilityRegistry` metadata `emits_leads=true` (AD-39), not a hard-coded list.
- Signal sources are `CapabilityRegistry` capabilities with `emits_signals=true` and `signal_types=[...]` (AD-37).

### Signal → sequence triggers
- Use AD-33 `AlertRule` with `capability_id` (signal capability), `notification_channels` containing `sequence_enrollment`, and `target.sequence_id` / `target.step_id` (AD-33, AD-37, AD-39).

### Notifications
- Reuse Story 11.1 notification service. New channels: `email_reply`, `email_delivered`, `email_bounced`. `SequenceEvent` is the canonical event source (AD-39).
- Zalo/LinkedIn channels are **deferred out of MVP** (AD-41).

### PII / redaction
- All lead/contact data displayed in UI must be redacted by `app/services/pii/redact.py` (AD-25). UI never surfaces raw `source_input` (recipe).

### Outcome pricing
- `OutcomeEvent` + `BillingEvent` rows are created for meetings booked / leads enriched. UI reuses the usage/credit dashboard from Story 8.3 (AD-42).

---

## 3. Product / business questions to close before dev

| # | Question | Blocks |
|---|---|---|
| Q1 | Does the lead-source selection in the empty-state CTA reuse the existing Integrations settings, or a new inline source picker? | N4 implementation |
| Q2 | Should the empty state display all connected scrapers by default, or only those opted into lead generation (`emits_leads=true`)? | N4 rollout |
| Q3 | Who can send positive-reply notifications (email/Telegram) — workspace admin only or any user with channel connected? | N5 permissions |
| Q4 | Positive-reply classification: does the agent/ML label it, or is any reply treated as positive until user marks otherwise? | N5 trigger logic |
| Q5 | Outcome-pricing (FR-69): per-lead projected cost is read from `BillingEvent` + `User.credit_micros_balance`; what currency/precision format does the UI show? | N6 cost display |
| Q6 | Workspace mode switch (N2): is Content mode a separate paid module, or available to all workspaces? | N2 nav gating |

---

## 4. Engineering notes

- **No new dependencies** are required by these UX contracts; they build on existing sidebar, data panel, table, notification, and credit-balance components.
- **Existing foundation to reuse:**
  - `CapabilityRegistry` for lead-source and signal-source discovery.
  - `Sequence`/`SequenceStep` tables (new, not `Automation`) for N8 campaign chip.
  - `BillingEvent` + wallet service for N6 projected cost and outcome-pricing.
  - Telegram/notification service (Story 11.1) for N5 notification plumbing, extended with `email_reply`/`email_delivered`/`email_bounced`.
  - Usage dashboard / credit display (`ux-contract-usage-dashboard.md`) for N6 cost formatting.
  - 2-panel layout and data table (`ux-contract-lead-intelligence-panel.md`) for N4/N7/N8.
- **Open implementation detail:**
  - N5 inbound email handling (SES webhook or IMAP idle) implemented as a capability; `SequenceEvent` is canonical source.
  - N7 dynamic source tabs query `CapabilityRegistry` where `emits_leads=true`.
  - N6 projected cost queries `BillingEvent` + `User.credit_micros_balance`; `TokenUsage` only for LLM steps.

---

## 5. Suggested implementation order

1. **P0 — N4:** Inbox empty state + lead-source selection (highest activation impact, depends on Q1/Q2).
2. **P1 — N6:** Per-lead projected cost (tightens FR-69 UX, depends on Q5; needs `BillingEvent` first).
3. **P1 — N8:** Campaign status chip (unblocks sequence activation from the lead table; needs `Sequence` table).
4. **P1 — N2:** Workspace mode switch (enables Outbound nav, low risk if Research stays default).
5. **P1 — N1:** Onboarding checklist (drives new-user activation, but needs completion-criteria events).
6. **P1 — N5:** Positive-reply / delivery / bounce notifications (depends on Q3/Q4 and inbound email capability).
7. **P2 — N3 + N7:** Tables directory + dynamic source tabs (lead-list management at scale, depends on `CapabilityRegistry` `emits_leads=true`).

---

## 6. Governance gates before public beta

1. Email outreach legal/ToS sign-off.
2. Contact-enrichment vendor contract / POC (Cleanlist / BetterContact).
3. PII/consent pipeline: separate HR redaction from lead enrichment.
4. CRM sync scope confirmed (read-first → write-back).
5. Outcome-pricing display / per-lead projected cost estimator tested.

---

## 7. Files to review

- `ux-designs/ux-Nowing-2026-07-22/ux-contract-lead-intelligence-panel.md`
- `ux-designs/ux-Nowing-2026-07-22/ux-contract-sidebar-onboarding.md`
- `ux-designs/ux-Nowing-2026-07-22/ux-contract-workspace-mode-switch.md`
- `ux-designs/ux-Nowing-2026-07-22/ux-contract-tables-directory.md`
- `ux-designs/ux-Nowing-2026-07-22/ux-contract-positive-reply-notifications.md`
- `ux-designs/ux-Nowing-2026-07-22/ux-contract-epic21-addendum-2026-08-11.md`
- `ux-design/epic21-lead-intelligence-ux.md`
- `ux-research-origami-final-2026-08-11.md`
- `epics.md` (Story 21.1–21.7)
- `architecture/architecture-Nowing-2026-07-22/ARCHITECTURE-SPINE.md` (AD-31, AD-33, AD-36–AD-42)

---

**Next action after this hand-off:** PO answers Q1–Q6; engineering slices contracts into frontend/backend stories once governance gates close.
