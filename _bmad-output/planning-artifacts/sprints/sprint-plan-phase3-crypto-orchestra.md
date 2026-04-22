---
sprintPlan: Phase 3 — Spike-Required Tier (Crypto Orchestra Final)
phase: 3
predecessor: Phase 2 Quality Gate Review (MUST PASS) + 2 Spikes (DONE)
successor: Phase 3 FINAL Quality Gate Review → 🎼 Crypto Orchestra Launch OR Rollback
estimatedDuration: 6 weeks (1w spikes + 4w stories + 1w gate review/launch)
stories: [spike-0.0, spike-0.0b, 9-3-token-unlock-scheduler, 9-6-technical-analyst]
qualityGates: [NFR-Q1, NFR-Q2, NFR-Q3, NFR-Q4]
createdAt: 2026-04-23
author: Mary (Strategic Business Analyst)
---

# Sprint Plan — Phase 3: Spike-Required Tier (Final)

## 🚨 Prerequisite Chain (blocking)

```
Phase 2 Quality Gate Review  →  2 Spikes (parallel)  →  Phase 3 Stories  →  Final Gate
       (MUST PASS)              0.0 + 0.0b              9.3 + 9.6           Decision
```

**Phase 3 chỉ start nếu:**
- ✅ Phase 2 all 4 Quality Gates PASS
- ✅ Chainlens success rate sustain > 95%
- ✅ Spike 0.0 (token unlock data) DONE với Option A or workable alternative
- ✅ Spike 0.0b (TA data + tooling) DONE với Option A (backend tool) prototype working
- ✅ Stakeholder approval cho Phase 3 scope (may narrow nếu spikes recommend)

**Nếu spike fail** → Story cần defer hoặc scope narrow. Specific:
- Spike 0.0 fail → defer 9.3, pivot Phase 3 scope (chỉ 9.6 hoặc replace 9.3)
- Spike 0.0b fail → defer 9.6 (HIGHEST risk story — không workaround dễ)

---

## 🎯 Sprint Goal

Complete full Crypto Orchestra (11 sub-agents) bằng cách thêm 2 highest-risk specialists:
- **Token Unlock Scheduler** (9.3): vesting events + sell pressure assessment
- **Technical Analyst** (9.6): chart indicators + trend outlook (NEW backend tool required)

**Final validation**: 4 Quality Gates phải maintain ở scale **11 agents parallel** — ultimate stress test.

**Outcome**: 🟢 LAUNCH FULL Crypto Orchestra với marketing campaign — OR rollback Phase 3 và launch chỉ Phase 1+2 (9 agents).

---

## 🗓️ 6-Week Timeline

### Week 1 — Parallel Spikes

**Spike 0.0 (Dev 1)** — Token Unlock Data Sources
| Day | Task |
|-----|------|
| Mon-Tue | Test Chainlens với 10 sample queries (top tokens với active vesting) |
| Wed | Score response: data availability / accuracy / format consistency |
| Thu | Evaluate alternatives nếu fail rate > 30% (TokenUnlocks API trial, Messari, CryptoRank) |
| Fri | Write recommendation memo: Option A (Chainlens viable) / B (Defer 9.3) / C (Procure paid API) |

**Spike 0.0b (Dev 2)** — TA Data + Tooling
| Day | Task |
|-----|------|
| Mon | Evaluate OHLCV sources: CoinGecko `/ohlc`, Binance public API, DexScreener |
| Tue-Wed | Prototype Option A: build `get_crypto_ta_indicators` tool với `pandas-ta` |
| Thu | Test prototype: BTC/ETH/UNI sample queries, verify RSI/MACD/MA accuracy |
| Fri | Recommendation memo: scope decision (full / conservative / defer) |

### Week 2 — Spike Decisions + Sprint Planning

| Day | Owner | Task |
|-----|-------|------|
| Mon | All | Review 2 spike memos |
| Mon | Stakeholder | Decision meetings — proceed Phase 3 or pivot |
| Tue | Mary | Update Story 9.3 + 9.6 specs based on spike findings (scope adjustments) |
| Wed | Mary | Add `crypto_ta.py` tool spec to Story 0.1 retroactively (nếu Option A approved) |
| Thu-Fri | Dev | Implement `crypto_ta.py` tool (if needed) — bridge Story 0.1 + 9.6 |

### Week 3 — Story 9.3 Token Unlock Scheduler

| Day | Owner | Task |
|-----|-------|------|
| Mon | Dev 1 | Create `token_unlock_scheduler_spec.py` |
| Mon | Dev 1 | Wire spec (10 sub-agents total) |
| Tue | Dev 1 | Unit tests: token budget, tool scoping |
| Tue-Wed | Dev 1 | Integration test: 10-agent parallel spawn |
| Wed | QA | 50-query sample: 100% date authenticity (CRITICAL — wrong date = financial damage) |
| Thu | QA | Manual verification vs TokenUnlocks.app |
| Thu | Dev 1 | Fix findings, especially date staleness disclosure (AC11) |
| Fri | Dev Lead | Code review + merge |

### Week 4 — Story 9.6 Technical Analyst (HIGHEST RISK)

| Day | Owner | Task |
|-----|-------|------|
| Mon | Dev 2 | Create `technical_analyst_spec.py` |
| Mon | Dev 2 | Wire spec (11 sub-agents — FULL orchestra!) |
| Tue | Dev 2 | Unit tests + verify NO fabricated patterns scope |
| Tue-Wed | Dev 2 | Integration test: 11-agent parallel (FINAL stress test) |
| Wed | QA | 50-query sample: 100% numeric authenticity, 0 invented chart patterns |
| Thu | Legal | Review disclaimer language (AC12 — DYOR + financial risk warning) |
| Thu | Dev 2 | Apply legal-approved disclaimer text |
| Fri | Dev Lead | Code review + merge |

### Week 5 — Phase 3 Integration & Final Stress Test

| Day | Owner | Task |
|-----|-------|------|
| Mon | Dev Lead | Deploy Phase 3 to staging |
| Mon | QA | Smoke test 10 comprehensive queries: 11-agent spawn verified |
| Tue | DevOps | Enable `CRYPTO_ORCHESTRA_PHASE3_ENABLED` feature flag (canary 5% — smaller blast radius) |
| Tue-Wed | DevOps | Monitor production metrics: parallelism ratio @ 11 agents, degradation rate |
| Wed-Thu | QA | Run 100-query Final Quality Gate benchmark |
| Fri | Mary | Compile Final Quality Gate Review report |

### Week 6 — Final Quality Gate Review + 🎼 Launch OR Rollback

| Day | Owner | Task |
|-----|-------|------|
| Mon | All | Review Final benchmark results |
| Mon | Mary | Compare Phase 1, 2, 3 cumulative metrics |
| Tue | Stakeholder | Final Quality Gate Decision meeting |
| Tue | All | Decision documented |
| Wed | Marketing | If 🟢 LAUNCH: prepare blog post, Twitter thread, Product Hunt |
| Wed | Marketing | If 🟡 Remediate: hold launch, communicate timeline shift |
| Wed | DevOps | If 🔴 Rollback: disable Phase 3 flag, RCA |
| Thu | Marketing | 🎼 Crypto Orchestra GA launch (if green) |
| Fri | All | Retrospective + post-launch monitoring kickoff |

---

## 👥 Team Assignments

| Role | Week 1 (Spikes) | Week 2 (Decisions) | Week 3 (9.3) | Week 4 (9.6) | Week 5 (Integration) | Week 6 (Launch) |
|------|----------------|-------------------|--------------|--------------|---------------------|-----------------|
| Dev 1 | Spike 0.0 | Tool impl | 9.3 lead | review | Staging | Buffer |
| Dev 2 | Spike 0.0b | Tool impl | review | 9.6 lead | Staging | Buffer |
| Dev Lead | — | Architecture review | Code review | Code review | Deploy | Decision |
| QA | — | — | 9.3 testing | 9.6 testing | Benchmark | Report |
| Legal | — | — | — | Disclaimer review | — | — |
| DevOps | — | — | — | — | Feature flag + monitoring | Launch ops |
| Mary (BA) | Spike review | Spec updates | — | — | — | Report + decision |
| Marketing | — | Coordinate timeline | — | — | Prepare assets | 🎼 Launch |

---

## 🎛️ Final Quality Gate Criteria

All 4 gates cumulative across all 3 phases:

| Gate | Threshold | Phase 3 Specific Concern |
|------|-----------|--------------------------|
| NFR-Q1 Accuracy | < 3% factual error rate | Date accuracy CRITICAL cho 9.3, indicator authenticity cho 9.6 |
| NFR-Q2 Parallelism | < 1.3x ratio @ 11 agents | Maximum stress — most likely to break |
| NFR-Q3 Graceful | > 98% | 9.6 needs new tool — 1 more failure mode |
| NFR-Q4 Speed | P95 < 90s | 11-agent overhead may push timing |

---

## ⚠️ Phase 3 Specific Risks (HIGHEST in entire initiative)

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|-----------|
| Spike 0.0 fail (no unlock data source) | Medium | High | Plan B: defer 9.3, scope Phase 3 as 9.6 only |
| Spike 0.0b fail (no OHLCV source) | Low | High | Plan B: defer 9.6 indefinitely (no workaround) |
| LLM fabricate chart patterns | High | High | Scope conservative: NO visual patterns in prompt. AC8 strict |
| Wrong unlock date → user trade wrong → financial damage | Medium | Critical | AC11 mandatory "as of {date}" disclosure |
| 11-agent parallelism breaks 1.3x ratio | Medium | Medium | Telemetry continuous, canary rollback ready |
| Legal exposure on TA disclaimer | Low | High | Week 4 Legal review mandatory, AC12 enforceable |
| Token cost explosion @ 11-agent comprehensive | Medium | Medium | Cost monitoring per query, budget cap |

---

## 🎬 Phase 3 → Launch Decision Matrix

```
All 4 gates pass + spikes successful
                         ↓
                   ✅ 🟢 LAUNCH
                   ├─ 🎼 Crypto Orchestra GA
                   ├─ Marketing campaign (blog, Twitter, Product Hunt)
                   ├─ Landing page update với 10-agent showcase
                   └─ Post-launch monitoring (4-week sustained metrics check)

1 gate marginal fail OR 1 spike workaround needed
                         ↓
                   ⚠️ 🟡 REMEDIATE OR PARTIAL LAUNCH
                   ├─ Fix specific issue (1-week sprint)
                   ├─ OR launch chỉ Phase 1+2 (9 agents) — defer Phase 3 indefinitely
                   └─ Communicate timeline shift transparently

2+ gates fail OR catastrophic
                         ↓
                   ❌ 🔴 ROLLBACK PHASE 3
                   ├─ Disable Phase 3 feature flag
                   ├─ Launch chỉ Phase 1+2 (still strong product — 9 agents!)
                   ├─ Post-mortem + RCA cho Phase 3 issues
                   └─ Re-plan Phase 3 approach (may take quarter+)
```

---

## 📊 Cumulative Effort Estimate

| Phase | Duration | Team Capacity Needed |
|-------|----------|---------------------|
| Epic 0 Foundation | 2-3 weeks | 2 devs full-time |
| Epic 0 Testing (0.4-0.6) | ~1 week | 1 dev + QA |
| Phase 1 (9.1 + 9.4) | 4 weeks | 2 devs + QA + Dev Lead |
| Phase 2 (9.2 + 9.5) | 4 weeks | 2 devs + QA + Dev Lead |
| **Phase 3 (9.3 + 9.6)** | **6 weeks** | **2 devs + QA + Dev Lead + Legal + Marketing** |
| **TOTAL** | **~17-18 weeks** | (with realistic buffers) |

---

**Status**: ready-for-dev ✅ (blocked on Phase 2 Quality Gate PASS + 2 Spikes DONE)
**Next**: Spike stories `spike-0.0-token-unlock-data-sources.md` + `spike-0.0b-ta-data-and-tooling.md`
