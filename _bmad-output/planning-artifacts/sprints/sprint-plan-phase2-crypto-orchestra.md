---
sprintPlan: Phase 2 — Web Research Tier (Crypto Orchestra)
phase: 2
predecessor: Phase 1 Quality Gate Review (MUST PASS)
successor: Phase 2 Quality Gate Review → Phase 3
estimatedDuration: 4 weeks
stories: [9-2-whale-tracker, 9-5-governance-analyst]
qualityGates: [NFR-Q1, NFR-Q2, NFR-Q3, NFR-Q4]
createdAt: 2026-04-23
author: Mary (Strategic Business Analyst)
---

# Sprint Plan — Phase 2: Web Research Tier

## 🚨 Prerequisite Chain (blocking)

```
Phase 1 Quality Gate Review  →  Chainlens reliability check  →  Phase 2 Kick-off
     (MUST PASS)                  (> 95% success rate)
```

**Phase 2 chỉ start nếu:**
- ✅ NFR-Q1 Accuracy < 3% (Phase 1 cumulative)
- ✅ NFR-Q2 Parallelism ratio < 1.3x @ 6 agents
- ✅ NFR-Q3 Graceful degradation > 98%
- ✅ NFR-Q4 Speed P95 < 90s
- ✅ Chainlens success rate > 95% trong Phase 1 production (telemetry verified)
- ✅ Chainlens has Arkham/Nansen/Snapshot/Tally data access (pre-flight test queries)

**Nếu BẤT KỲ gate FAIL** → Phase 2 postponed, remediation sprint required.

---

## 🎯 Sprint Goal

Expand Crypto Orchestra từ 6 agents (Phase 1) lên 9 agents bằng cách thêm 2 specialists web-research–based:
- **Whale Tracker** (9.2): on-chain wallet flow analysis via Chainlens-Arkham/Nansen
- **Governance Analyst** (9.5): DAO proposals + voting outcomes via Chainlens-Snapshot/Tally

**Key validation**: Parallelism ratio + graceful degradation phải MAINTAIN thresholds khi scale từ 6→9 agents, và 2 agents cùng reliant on Chainlens (single point of failure).

---

## 🗓️ 4-Week Timeline

### Week 1 — Story 9.2 Whale Tracker

| Day | Owner | Task |
|-----|-------|------|
| Mon | Mary | Pre-flight Chainlens verification (Arkham/Nansen test queries) |
| Mon | Dev 1 | Create `whale_tracker_spec.py` — 3 constants, prompt < 500 tokens |
| Tue | Dev 1 | Wire `whale_tracker_spec` trong `chat_deepagent.py` (8 sub-agents total) |
| Tue | Dev 1 | Unit tests: token budget, tool scoping |
| Wed | Dev 1 | Integration test: 8-agent parallel spawn, ratio < 1.3x |
| Wed | QA | 50-query sample: accuracy verification vs raw Chainlens output |
| Thu | QA | Manual review: 100% address authenticity (AC7) |
| Thu | Dev 1 | Fix any QA findings |
| Fri | Dev Lead | Code review + merge to develop |

### Week 2 — Story 9.5 Governance Analyst

| Day | Owner | Task |
|-----|-------|------|
| Mon | Mary | Pre-flight Chainlens verification (Snapshot/Tally test queries) |
| Mon | Dev 2 | Create `governance_analyst_spec.py` |
| Tue | Dev 2 | Wire spec (9 sub-agents total) |
| Tue | Dev 2 | Unit tests |
| Wed | Dev 2 | Integration test: 9-agent parallel (Phase 2 max) |
| Wed | QA | 50-query sample: accuracy + **neutral framing review** (AC11 specific) |
| Thu | QA | Manual expert review: governance health classification |
| Thu | Dev 2 | Fix findings |
| Fri | Dev Lead | Code review + merge |

### Week 3 — Phase 2 Integration & Stress Test

| Day | Owner | Task |
|-----|-------|------|
| Mon | Dev Lead | Deploy Phase 2 to staging |
| Mon | QA | Smoke test 10 comprehensive queries (Rule C): 9-agent spawn verified |
| Tue | DevOps | Enable `CRYPTO_ORCHESTRA_PHASE2_ENABLED` feature flag (canary 10%) |
| Tue-Wed | DevOps | Monitor production metrics: parallelism ratio, degradation rate, Chainlens success rate |
| Thu | QA | Run 100-query Quality Gate benchmark |
| Fri | Mary | Compile Quality Gate Review report |

### Week 4 — Phase 2 Quality Gate Review + Decision

| Day | Owner | Task |
|-----|-------|------|
| Mon | All | Review 100-query benchmark results |
| Mon | Mary | Compare Phase 1 vs Phase 2 baseline metrics |
| Tue | Stakeholder | Quality Gate Decision meeting |
| Tue | All | Decision documented: 🟢 GO Phase 3 / 🟡 Remediate / 🔴 Rollback |
| Wed-Fri | All | If GO: buffer time for Phase 3 kickoff prep |
| Wed-Fri | All | If Remediate: fix specific issues before Phase 3 |
| Wed-Fri | All | If Rollback: disable Phase 2 feature flag, RCA investigation |

---

## 👥 Team Assignments

| Role | Name | Week 1 | Week 2 | Week 3 | Week 4 |
|------|------|--------|--------|--------|--------|
| Dev 1 | TBD | 9.2 lead | review | staging | buffer |
| Dev 2 | TBD | review | 9.5 lead | staging | buffer |
| Dev Lead | TBD | Code review | Code review | Deploy | Decision |
| QA | TBD | 9.2 testing | 9.5 testing | Benchmark | Report |
| DevOps | TBD | — | — | Feature flag + monitoring | — |
| Mary (BA) | — | Pre-flight | Pre-flight | — | Report + decision |

---

## 🎛️ Quality Gate Criteria (Phase 2 Review)

All 4 gates cumulative (including Phase 1 metrics):

| Gate | Threshold | Measurement Method |
|------|-----------|-------------------|
| NFR-Q1 Accuracy | < 3% factual error rate | 100-query QA sample, manual cross-check vs raw Chainlens output |
| NFR-Q2 Parallelism | < 1.3x ratio @ 9 agents | Telemetry middleware P95 ratio |
| NFR-Q3 Graceful | > 98% | Fault injection test + production canary observability |
| NFR-Q4 Speed | P95 < 90s | Production telemetry (full-suite queries) |

**Critical concern for Phase 2**:
- 2 agents (9.2 + 9.5) cùng reliant on Chainlens
- Nếu Chainlens fail → both agents degrade → graceful > 98% threshold risk

---

## ⚠️ Phase 2 Specific Risks

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|-----------|
| Chainlens không có Arkham access | Low | High | Pre-flight verify Week 1 Mon. Defer 9.2 nếu fail |
| Chainlens không có Snapshot/Tally | Low | High | Pre-flight verify Week 2 Mon. Defer 9.5 nếu fail |
| Hallucinated wallet/proposal data | Medium | High | AC7 strict 100% authenticity, QA manual review |
| 9-agent parallelism ratio > 1.3x | Low | Medium | Telemetry continuous monitoring, canary rollback |
| Inflammatory framing on controversial DAO votes | Low | Medium | AC11 neutral framing review |

---

## 🎬 Phase 2 → Phase 3 Decision Matrix

```
All 4 gates pass + Chainlens success > 95%
                         ↓
                   ✅ 🟢 GO Phase 3
                   ├─ Kick off Spike 0.0 (token unlock data sources)
                   └─ Kick off Spike 0.0b (TA data + tooling)

1 gate marginal fail + others pass
                         ↓
                   ⚠️ 🟡 REMEDIATE (1-week sprint)
                   ├─ Fix specific issue
                   └─ Re-run gate review, if pass → Phase 3

2+ gates fail OR catastrophic issue
                         ↓
                   ❌ 🔴 ROLLBACK
                   ├─ Disable Phase 2 feature flag
                   ├─ Post-mortem + RCA
                   └─ Re-plan Phase 2 approach (may pivot story scope)
```

---

**Status**: ready-for-dev ✅ (blocked on Phase 1 Quality Gate PASS)
**Next**: Phase 3 Sprint Plan (file `sprint-plan-phase3-crypto-orchestra.md`)
