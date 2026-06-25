# Story 10.1.6b — Nansen TGM Tier Customer Communications (Cross-Functional)

**Epic:** 10 — Institutional Research & Risk Management Terminal
**Depends on:** Story 10-1-6a (TGM tier detection deployed)
**Owners:** Marketing + Sales + Support + Finance
**Status:** backlog
**Priority:** P1 — required within 2 weeks of 10-1-6a production deploy
**Created:** 2026-05-06

> **🔄 Split 2026-05-06:** Originally part of story 10-1-6 (bundled dev + cross-functional). Per IR § QV-4, split into focused stories. This story tracks **non-dev** workstreams that don't gate dev team velocity.

---

## Problem Statement

Story 10-1-6a (dev) ships tier detection — backend identifies Pro-tier customers hitting TGM-only endpoint, FE shows upgrade notice. **Detection alone doesn't drive conversions or reduce support load** — needs coordinated customer comms across 4 stakeholder teams.

Without this story:
- Customers see notice but no clear upgrade path → support tickets spike
- Sales doesn't know which customers need outreach → revenue left on table
- Finance can't forecast tier-mix shift → budget surprises
- Marketing has no narrative for tier change → confusion in user community

---

## Acceptance Criteria

### Marketing (Owner: TBD)

**AC-MK1 — Customer email campaign:**
GIVEN tier detection ships in production
WHEN list of affected customer hashes available (from Sentry/Grafana via 10-1-6a)
THEN send email blast to existing Pro-tier Nansen integration users:
- Subject: "Smart Money Flow upgrade — Nansen TGM tier required for new features"
- Body: explain change, link to upgrade flow, FAQ
- CTA: "Upgrade Nansen plan" (link to nansen.ai/plans) hoặc "Contact sales for assistance"

**AC-MK2 — Public comms:**
- Blog post on nowing.ai/blog explaining tier requirements + alternative providers (Arkham, Dune fallback)
- In-app announcement banner for affected workspaces (1-week display)

### Sales (Owner: TBD)

**AC-SL1 — Upgrade playbook:**
- Sales team receives 1-pager: "When customer asks about Nansen tier"
  - Q: "Why upgrade?" → A: "Access TGM-tier smart money data + 5x rate limit"
  - Q: "Can I use alternatives?" → A: "Arkham/Dune fallback works automatically; Nansen TGM gives best fidelity"
  - Q: "Is there a Nowing-bundled option?" → A: [decision pending — see AC-FN1]

**AC-SL2 — Outreach to top-20 affected customers:**
Personal outreach within 48h of email blast for customers with > $500/mo Nowing spend.

### Support (Owner: TBD)

**AC-SP1 — Runbook published:**
`docs/operations/nansen-tier-troubleshooting.md` with:
- How to verify customer's Nansen tier (via `POST /admin/nansen/recheck` endpoint built in 10-1-6a)
- Common questions + answers
- Escalation matrix (when to involve Sales, when to refund, etc.)

**AC-SP2 — Macro responses ready:**
3 saved responses in support tool:
- "Nansen tier upgrade required" (most common)
- "Use Arkham/Dune fallback" (cost-conscious customer)
- "Refund partial month" (edge case)

### Finance (Owner: TBD)

**AC-FN1 — Tier-mix forecast:**
Given customer hash list with current Nansen spend:
- Forecast 30/60/90-day scenarios:
  - Best case: 80% upgrade to TGM, 20% downgrade
  - Worst case: 40% upgrade, 60% downgrade or churn
  - Midpoint: 60% upgrade
- Calculate Nowing-side ARR impact + Nansen API cost change

**AC-FN2 — Decision: Nowing-bundled Nansen offering?**
Strategic question: Should Nowing offer "TGM-included Pro" tier để absorb Nansen cost + simplify customer journey?
- Pro: Sticky upsell, customer simplicity
- Con: Margin compression, vendor lock-in
- Decision deadline: 30 days after 10-1-6a deploy
- Decision-maker: CFO + Product

---

## Cross-Functional Coordination

### Trigger Condition

10-1-6a deployment to production AND first batch of `nansen.tier_mismatch` Sentry events captured (minimum 50 customer hashes).

### Sequencing

1. **Day 0 (10-1-6a deploy):** Tier detection live, customer hash list starts populating
2. **Day 7:** Marketing email + blog (AC-MK1, AC-MK2)
3. **Day 7-14:** Sales outreach to top-20 (AC-SL2)
4. **Day 7:** Support runbook live (AC-SP1)
5. **Day 14:** First Finance forecast (AC-FN1)
6. **Day 30:** Nowing-bundled decision (AC-FN2)

### Communication Channels

- Slack: `#nansen-tgm-rollout` (created when 10-1-6a starts dev)
- Weekly sync: PM + Marketing + Sales lead, 30 min
- Dashboard: Grafana board sharing customer hash counts + conversion metrics

---

## Risks & Dependencies

| Risk | Mitigation | Owner |
|---|---|---|
| Customer churn > forecast | Sales escalation playbook + refund-partial-month policy | Sales + Finance |
| Nansen ToS change mid-rollout | Legal review of Nansen contract before launch | Legal |
| Translation/i18n for non-English customers | Translate email + blog to Vietnamese (primary), Japanese (secondary if applicable) | Marketing |
| Privacy concerns from logging customer hashes | SHA-256 only, no raw key logged; GDPR review | Legal + Eng |

---

## Definition of Done

- [ ] All 4 stakeholder teams (Marketing, Sales, Support, Finance) sign off on their AC checklists
- [ ] First customer email blast delivered + open rate ≥ 30%
- [ ] Support tickets về "tier" tagged + tracked; volume stable after week 2
- [ ] Finance forecast presented to CFO; bundled-tier decision made
- [ ] Customer hash list maintained with conversion status (upgraded / downgraded / churned)

---

## Notes

This story does NOT block dev team velocity. 10-1-6a can ship and run independently. 10-1-6b coordinates customer-facing rollout that should follow 10-1-6a within 2 weeks.

If teams are under-resourced for cross-functional comms, recommend keeping 10-1-6a deployment behind feature flag (`NANSEN_TIER_NOTICE_ENABLED=false`) until 10-1-6b can launch coordinated.
