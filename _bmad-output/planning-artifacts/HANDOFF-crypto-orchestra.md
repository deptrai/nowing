# 🎼 Crypto Orchestra — Handoff to Dev Team

**Date**: 2026-04-23
**From**: Mary (Strategic Business Analyst)
**To**: Dev Lead, Dev 1, Dev 2, QA, DevOps, Product Lead
**Subject**: Crypto Orchestra Initiative — Planning complete, ready-for-dev

---

## 📌 TL;DR

Planning stack cho **Crypto Orchestra** (Epic 9 — AI-native Bloomberg Terminal cho crypto retail) đã hoàn thành. 14 artifacts tổng cộng **~200KB documentation** ready cho dev team kick-off.

**Realistic timeline**: ~17-18 weeks từ kick-off đến Full Launch.

**Kick-off blocker**: Code audit 2026-04-23 phát hiện **Epic 0 (Crypto Foundation) chưa thực sự implement** mặc dù docs từ giữa 2025 cho thấy đã xong. → Phải start Epic 0 TRƯỚC, không skip thẳng Phase 1.

---

## 🎯 What's Ready for You

### Planning Artifacts (Source of Truth)

```
_bmad-output/planning-artifacts/
├── briefs/
│   └── product-brief-epic9-crypto-orchestra.md       (business rationale, stakeholder decisions)
├── prd.md                                             (FR27-35, NFR-CS1-4, NFR-Q1-4)
├── epics.md                                           (Epic 0, 8, 9 specs — cross-linked to story files)
├── crypto-subagents-epics.md                          (Epic 0 source doc — status CHƯA IMPLEMENT)
├── sprints/
│   ├── sprint-plan-phase1-crypto-orchestra.md        (4-week Phase 1)
│   ├── sprint-plan-phase2-crypto-orchestra.md        (4-week Phase 2)  🆕
│   └── sprint-plan-phase3-crypto-orchestra.md        (6-week Phase 3)  🆕
└── stories/                                           (12 stories + 2 spikes — ALL READY)
    ├── story-0.1-crypto-tool-infrastructure.md       ✅ Epic 0 (BLOCKING)
    ├── story-0.2-base-sub-agents.md                  ✅ Epic 0 (BLOCKING)
    ├── story-0.3-main-agent-prompt.md                ✅ Epic 0 (BLOCKING)
    ├── story-8.1-api-integration-tests.md            ✅ Epic 8 (gatekeeper)
    ├── story-8.2-parallel-execution-validation.md    ✅ Epic 8 (gatekeeper)
    ├── story-8.3-error-handling-fallback.md          ✅ Epic 8 (gatekeeper)
    ├── story-9.1-tokenomics-analyst.md               ✅ Phase 1
    ├── story-9.4-yield-optimizer.md                  ✅ Phase 1
    ├── story-9.2-whale-tracker.md                    ✅ Phase 2
    ├── story-9.5-governance-analyst.md               ✅ Phase 2
    ├── spike-0.0-token-unlock-data-sources.md        🆕 Phase 3 prerequisite
    ├── spike-0.0b-ta-data-and-tooling.md             🆕 Phase 3 prerequisite
    ├── story-9.3-token-unlock-scheduler.md           ⚠️ Phase 3 (blocked on Spike 0.0)
    └── story-9.6-technical-analyst.md                ⚠️ Phase 3 (blocked on Spike 0.0b)

_bmad-output/implementation-artifacts/
└── sprint-status.yaml                                 (updated với 12 stories + spikes)

nowing_backend/docs/
└── crypto-subagents-guide.md                         (Epic 0 implementation blueprint)
```

### Quick Index

| If you are... | Start here |
|---------------|-----------|
| Dev Lead | `sprint-plan-phase1-crypto-orchestra.md` + `sprint-status.yaml` |
| Dev 1 (implementer) | `story-0.1-crypto-tool-infrastructure.md` (first to pick up) |
| Dev 2 | `story-0.2-base-sub-agents.md` (after 0.1 DONE) |
| QA | `story-8.1`, `8.2`, `8.3` — gatekeepers you'll enforce |
| DevOps | `story-8.2` (telemetry middleware) + `story-8.3` (feature flags) |
| Product Lead | `briefs/product-brief-epic9-crypto-orchestra.md` + `prd.md` User Journey #8 |
| Legal | `story-9.6-technical-analyst.md` AC12 (TA disclaimer review) |
| Marketing | Sprint Plan Phase 3 Week 6 (launch prep) |

---

## 🚦 Critical Prerequisite Chain

**KHÔNG start Phase 1 nếu chưa xong chain này:**

```
┌─────────────────────────────────────────────────────────────┐
│  Epic 0: Foundation (3 stories, ~2-3 weeks)                 │
│  └─ Story 0.1 → Story 0.2 → Story 0.3                       │
│                                                              │
│                            ↓                                 │
│                                                              │
│  Epic 8: Testing (3 stories, ~1 week)                        │
│  └─ Story 8.1 → Story 8.2 → Story 8.3                       │
│                                                              │
│                            ↓                                 │
│                                                              │
│  Phase 1: 2 stories + Quality Gate Review (~4 weeks)         │
│  └─ Story 9.1 + Story 9.4 → Review                           │
│                                                              │
│                            ↓                                 │
│             🚦 QUALITY GATE (4 NFRs)                         │
│             🟢 PASS → Phase 2                                │
│             🟡 MARGINAL → Remediate                          │
│             🔴 FAIL → Rollback + RCA                         │
└─────────────────────────────────────────────────────────────┘
```

---

## 📊 4 Quality Gates (Phase 1/2/3 cumulative)

| Gate | Threshold | Validation Source |
|------|-----------|-------------------|
| **NFR-Q1** Accuracy | < 3% factual error rate | Story 8.1 + per-phase QA 50-query samples |
| **NFR-Q2** Parallelism Ratio | < 1.3x (total/max_individual) | Story 8.2 ParallelismTelemetryMiddleware |
| **NFR-Q3** Graceful Degradation | > 98% partial-fail success | Story 8.3 fault injection (respx) |
| **NFR-Q4** Speed | P95 < 90s full-suite | Story 8.2 100-query benchmark |

All gates cumulative — must maintain qua từng phase.

---

## ⚠️ Known Risks (documented, not ignored)

| # | Risk | Phase | Mitigation |
|---|------|-------|-----------|
| 1 | **Epic 0 drift** — docs say done, code empty | 0 | This handoff forces explicit Epic 0 implementation |
| 2 | Chainlens Arkham/Nansen access unverified | 2 | Pre-flight test Week 1 Mon (Sprint Plan Phase 2) |
| 3 | Token unlock data source uncertain | 3 | Spike 0.0 BEFORE Story 9.3 commit |
| 4 | No OHLCV API free cho crypto | 3 | Spike 0.0b BEFORE Story 9.6 commit |
| 5 | LLM fabricate chart patterns | 3 | Scope conservative (no visual patterns), AC8 strict |
| 6 | TA disclaimer legal exposure | 3 | Week 4 Legal review mandatory (Sprint Plan Phase 3) |
| 7 | 11-agent parallelism break 1.3x | 3 | Canary rollout 5% + telemetry continuous |

---

## 💰 Cost Notes (Budgeting)

| Item | Estimate | Source |
|------|----------|--------|
| Token cost per comprehensive query (4 agents) | ~$0.05 | Phase 1 baseline |
| Token cost full orchestra (11 agents) | ~$0.15 | Phase 3 projected |
| 100-query Phase 3 benchmark | ~$15 | 1 run trước mỗi gate review |
| External APIs (Phase 1, 2) | $0 | Free tiers adequate |
| External APIs (Phase 3) | TBD | Spike 0.0 may recommend paid API |
| Chainlens usage spike | +50% | 2 agents reliant in Phase 2 |

---

## 🎬 Recommended Kick-off Sequence

### Week 1 Actions (for Dev Lead)

1. **Mon AM**: Team all-hands 30min
   - Walk through this handoff
   - Clarify questions
   - Assign Dev 1 → Story 0.1, Dev 2 → standby (starts 0.2 when 0.1 ~50% done)

2. **Mon PM**: Environment setup
   - Verify `ETHERSCAN_API_KEY`, `CHAINLENS_*` env vars
   - Verify CoinGecko, GoPlus, CryptoPanic, DeFiLlama accessible
   - Branch convention: `epic-0/story-0-1-crypto-tools` (follow team convention)

3. **Tue-Fri**: Dev 1 implements Story 0.1
   - Daily standup sync
   - Mid-week: Dev 2 reviews 0.1 design pre-implementation

4. **Week 2**: Dev 1 + Dev 2 parallel on 0.1 (finish) + 0.2 (start)

5. **Week 3**: Dev Lead + QA kick off Epic 8 prep while 0.2 + 0.3 finishing

### Escalation Path

| Trigger | Escalate to |
|---------|-------------|
| Pre-flight check fails | Dev Lead → Mary (scope reassessment) |
| Quality Gate PASS decision | Stakeholder meeting (Mary convene) |
| Quality Gate FAIL | Dev Lead → Product Lead → Rollback decision |
| Spike findings | Mary → scope memo → Stakeholder |
| Legal concern (Story 9.6) | Dev 2 → Legal → Product Lead |

---

## 📞 Points of Contact

| Role | Person | Availability |
|------|--------|--------------|
| Planning author | Mary (this doc) | Async via BMad |
| Product decisions | Product Lead | Standups + stakeholder meetings |
| Architecture questions | Dev Lead | Slack #dev-crypto-orchestra |
| Chainlens issues | Chainlens team | (external — request channel via Dev Lead) |

---

## 🎁 Delivered Value (What You're Getting)

- ✅ **12 fully-specified stories** với 100+ Acceptance Criteria, DoD checkpoints, rollback plans
- ✅ **3 sprint plans** (Phase 1, 2, 3) với day-by-day timelines and team assignments
- ✅ **2 spike stories** với outcome-driven success criteria (decisions valuable regardless of finding)
- ✅ **4 Quality Gates** với threshold + measurement method
- ✅ **Risk register** (7 documented risks với mitigations)
- ✅ **Cost estimates** for budgeting
- ✅ **Traceability matrix** mỗi story → FRs + NFRs
- ✅ **Reality check** — drift giữa docs và code đã identified + closed với Epic 0

---

## 🎼 Vision Reminder

Crypto Orchestra positions Nowing như **AI-native Bloomberg Terminal cho crypto retail** — 11 specialist sub-agents chạy song song cho comprehensive analysis mà không trader retail nào access được miễn phí.

Phase 1 launch (2 advanced agents trên 6 total) đã là differentiation play. Full Phase 3 launch (11 agents) là moat.

**Quality-first approach**: thà defer 9.3/9.6 nếu spikes fail hơn là launch fabricating data cho users.

---

**Ready when you are. Questions? Slack #crypto-orchestra-planning.**

🎼 Mary
Strategic Business Analyst, BMad
