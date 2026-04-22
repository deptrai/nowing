---
storyId: spike-0.0
storyTitle: SPIKE — Token Unlock Data Source Evaluation
type: research-spike
epicParent: epic-09-advanced-crypto-agents (Crypto Orchestra Phase 3)
dependsOn: [Phase 2 Quality Gate Review PASS]
blocks: [9-3-token-unlock-scheduler]
estimatedEffort: 3-5 days
status: ready-for-dev (blocked on Phase 2 GO)
priority: P2 (Phase 3 prerequisite)
createdAt: 2026-04-23
author: Mary (Strategic Business Analyst)
---

# Spike 0.0: Token Unlock Data Source Evaluation

## Spike Goal

**Decide** whether Story 9.3 (Token Unlock Scheduler) is feasible với current data sources, hoặc cần pivot Phase 3 scope.

**Question to answer**: Có data source nào đáng tin cậy cho upcoming token unlocks (30/60/90 days) và historical correlation, mà integrate được với Crypto Orchestra architecture không?

---

## Context

Story 9.3 đòi hỏi agent trả lời:
- Upcoming unlocks cho specific tokens (date, % supply, $ value, recipient)
- Historical sell pressure correlation (past unlock → price move)
- Pressure classification (HIGH/MED/LOW)

**Data source uncertainty là lý do Story 9.3 bị defer vào Phase 3**. Chainlens chưa verified cover được TokenUnlocks.app/Vesting.is/CryptoRank data tốt.

**Cost của spike**: 3-5 dev days — **rẻ hơn nhiều** so với commit Story 9.3 (3 dev days) rồi khám phá data không có → throw away.

---

## Spike Protocol

### Day 1-2: Test Chainlens Primary Hypothesis

**Objective**: Score Chainlens response quality cho 10 sample unlock queries.

**Test queries** (10 tokens có active vesting trong 2026):

| # | Token | Query |
|---|-------|-------|
| 1 | OP (Optimism) | "Optimism OP token unlock schedule next 90 days" |
| 2 | ARB (Arbitrum) | "Arbitrum ARB vesting cliff upcoming dates" |
| 3 | APT (Aptos) | "Aptos APT unlock amount and date next 60 days" |
| 4 | SUI (Sui) | "Sui SUI vesting schedule team investors" |
| 5 | JTO (Jito) | "Jito JTO token unlock next unlock event" |
| 6 | AAVE | "Aave AAVE vesting status (expected mostly complete)" |
| 7 | UNI (Uniswap) | "Uniswap UNI treasury unlock schedule" |
| 8 | STRK (Starknet) | "Starknet STRK unlock cliff dates" |
| 9 | W (Wormhole) | "Wormhole W token vesting schedule investors" |
| 10 | AEVO | "AEVO token unlock next major event" |

**Scoring criteria** (0-2 per query):
- **Data present** (0 = no data, 1 = partial, 2 = complete dates + amounts)
- **Accuracy** (0 = wrong, 1 = close, 2 = verified vs TokenUnlocks.app manual check)
- **Format consistency** (0 = unstructured, 1 = parseable, 2 = directly usable by agent)

**Scoring thresholds**:
- Total score ≥ 40/60 (67%) → **Option A viable** (proceed Story 9.3)
- Total 25-39 (42-65%) → Option B investigate (evaluate alternatives)
- Total < 25 (< 42%) → **Option C** (defer 9.3 hoặc procure paid data)

### Day 2-3: Evaluate Alternatives (Only if Day 1-2 inconclusive)

**If Chainlens insufficient**, test alternatives:

#### Alt 1: TokenUnlocks.app
- Check public API availability (unlock.json endpoint?)
- Check ToS for commercial scraping — legal risk?
- Check data freshness
- Check coverage (top 50 tokens?)

#### Alt 2: Messari API
- Pricing tier needed cho unlock data
- Rate limits
- Coverage
- Integration complexity

#### Alt 3: CryptoRank
- API availability
- Pricing
- Data quality

#### Alt 4: Self-scraping
- Risk: fragile, ToS violations, maintenance burden
- Only consider nếu tất cả API options fail

### Day 4-5: Write Recommendation Memo

**Deliverable**: `_bmad-output/research/spike-0.0-token-unlock-findings.md`

**Memo structure**:
```markdown
# Spike 0.0 — Token Unlock Data Source Findings

## TL;DR Recommendation
[Option A / B / C với 1-paragraph justification]

## Methodology
- 10 sample queries tested
- Sources evaluated: [Chainlens, TokenUnlocks, Messari, CryptoRank]
- Scoring rubric applied

## Chainlens Results
| Query | Data Score | Accuracy | Format |
| ... | | | |
Total: X/60

## Alternative Sources (if tested)
[Same scoring cho each]

## Cost-Benefit Analysis
- Option A cost: $0 (Chainlens existing)
- Option B cost: [estimated]
- Option C cost: $X/month paid API

## Recommended Decision
[A/B/C với reasoning]

## Impact on Story 9.3 Scope
[any scope adjustments needed]

## Impact on Sprint Plan
[timeline shift if any]
```

---

## Deliverables

- [ ] Spike findings memo (`research/spike-0.0-token-unlock-findings.md`)
- [ ] 10-query test results với scoring
- [ ] Cost-benefit analysis nếu alternatives evaluated
- [ ] Recommendation: Option A / B / C
- [ ] Stakeholder sign-off meeting scheduled

---

## Definition of Done

- [ ] **DoD-1** 10 sample queries run trên Chainlens với scoring
- [ ] **DoD-2** Alternatives evaluated (nếu Chainlens score inconclusive)
- [ ] **DoD-3** Memo written và shared với stakeholders
- [ ] **DoD-4** Decision meeting: Option A / B / C approved
- [ ] **DoD-5** Story 9.3 spec updated (nếu scope changes từ spike findings)
- [ ] **DoD-6** Sprint Plan Phase 3 updated với impact

---

## Outcome-Driven Success Criteria

Spike là **success** regardless of outcome — mục tiêu là DECISION, không phải positive finding.

| Outcome | Action |
|---------|--------|
| 🟢 Option A viable | Proceed Story 9.3 |
| 🟡 Option B workable (alternative source) | Update Story 9.3 scope + tooling |
| 🔴 Option C necessary (paid API) | Budget approval + procurement |
| ⛔ No viable option | **Defer Story 9.3**, pivot Phase 3 scope (9.6 only) |

**All 4 outcomes prevent wasted effort** — that's the spike value.

---

**Status**: ready-for-dev ✅
**Next**: After DONE → Story 9.3 proceeds (if viable) or defers.
