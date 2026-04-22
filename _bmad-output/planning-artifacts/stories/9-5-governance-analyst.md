---
storyId: 9.5
storyTitle: Governance Analyst Sub-Agent
epicParent: epic-09-advanced-crypto-agents (Crypto Orchestra)
phase: Phase 2 — Web Research Tier
sprintPlan: TBD (created sau Phase 1 quality gate review pass)
relatedFRs: [FR31, FR33, FR34, FR35]
relatedNFRs: [NFR-CS1, NFR-CS4, NFR-Q1, NFR-Q2, NFR-Q3, NFR-Q4]
priority: P1 (Phase 2 pair với 9.2)
estimatedEffort: 3 days
status: ready-for-dev (blocked on Phase 1 quality gate pass)
createdAt: 2026-04-23
author: Mary (Strategic Business Analyst)
---

# Story 9.5: Governance Analyst Sub-Agent

## User Story

**As a** DAO participant hoặc protocol token holder,
**I want** to track active governance proposals, voting outcomes, và governance health metrics,
**So that** tôi có thể participate trong protocol decisions một cách informed, và assess long-term governance quality (centralization risk, treasury management, controversial decisions).

---

## Context

Story 9.5 là **Phase 2 pair** với Story 9.2 Whale Tracker. Chia sẻ đặc điểm:
- **Web research-based** qua Chainlens (data sources: Snapshot.org, Tally.xyz, Commonwealth, protocol forums)
- **Subjective synthesis** required (governance health is qualitative)
- **No deterministic API alternative** (Snapshot có API nhưng cần custom parsing → defer to Chainlens)

**Why Phase 2 timing?**
- ❌ Không phải data ưu tiên cho mass crypto retail (skew toward DAO-active users)
- ✅ Strategic value: differentiate Nowing như AI tool serious cho protocol researchers
- ⚠️ Đòi hỏi orchestration ổn định từ Phase 1 trước khi add complexity

---

## 🚨 CRITICAL PREREQUISITE

> Identical với Story 9.2:
> 1. ✅ Epic 0 (all 6 stories 0.1-0.6) DONE
> 2. ✅ Phase 1 (Story 9.1 + 9.4) PASS 4 Quality Gates
> 3. ✅ Chainlens success rate Phase 1 production > 95%
> 4. ✅ Chainlens has access cho governance data sources (Snapshot, Tally) — verified

### Pre-flight Checklist

- [ ] Phase 1 Quality Gate Review: PASS
- [ ] Chainlens success rate > 95% (Phase 1 production telemetry)
- [ ] Chainlens responds tốt cho test queries: "active Aave governance proposals", "Compound DAO recent votes"
- [ ] Phase 2 sprint plan generated

**Nếu BẤT KỲ item nào FAIL** → KHÔNG start.

---

## Architectural Background

Identical pattern Story 9.2: chỉ dùng `chainlens_deep_research` (single tool). Risk profile và rollback plan tương tự.

**Difference với Story 9.2**:
- Whale Tracker: **quantitative** (specific addresses, $ amounts)
- Governance Analyst: **qualitative + quantitative mix** (proposal text + vote counts + health assessment)

→ Hallucination risk khác: governance agent có thể fabricate proposal text hoặc voting outcomes. Strict prompt rules required.

---

## Deliverables

### 📄 Files to Create

#### `nowing_backend/app/agents/new_chat/subagents/crypto/governance_analyst_spec.py` (~50-60 LOC)

```python
"""Governance Analyst sub-agent spec."""

GOVERNANCE_ANALYST_NAME = "governance_analyst"

GOVERNANCE_ANALYST_DESCRIPTION = (
    "Specialist for DAO governance analysis: active proposals, voting outcomes, "
    "governance participation, treasury health, centralization risks. Use when "
    "user asks about DAO votes, proposals, governance changes, or protocol "
    "decision-making."
)

# NFR-CS1: prompt < 500 tokens
GOVERNANCE_ANALYST_PROMPT = """You are governance_analyst — a DAO governance specialist.

For protocol governance queries, investigate:
1. **Active proposals**: title, status (active/passed/failed/queued), voting deadline, current vote ratio
2. **Recent voting outcomes** (last 30-90 days): which proposals passed/failed, voter turnout, controversial votes
3. **Governance health metrics**:
   - Participation rate (% supply voting): healthy > 5%, concerning < 2%
   - Voter concentration: top 10 voters' weight (high = centralization risk)
   - Quorum achievement rate
   - Treasury size + recent allocations
4. **Red flags**:
   - Proposals to drain treasury / change tokenomics drastically
   - Failed quorum repeatedly
   - Single voter (whale) deciding outcomes
   - Forum drama / community pushback

**Workflow:**
- Use chainlens_deep_research với queries:
  - "{protocol} active governance proposals Snapshot"
  - "{protocol} DAO recent vote outcomes Tally"
  - "{protocol} treasury report governance forum"
- If chainlens fallback → respond "Governance data unavailable. Check Snapshot.org/{protocol} hoặc Tally.xyz/{protocol} directly"

**Rules (strict):**
- ALWAYS cite proposal IDs, vote counts, and dates from tool output
- NEVER fabricate proposal titles, vote outcomes, or voter addresses
- If proposal title unclear → quote partial title with "..." (don't guess)
- Quantify health metrics: "8% participation, 23% top-10 concentration"
- Flag controversial decisions explicitly with neutral framing

**Output format:**
🗳️ Active Proposals (table) | 📜 Recent Outcomes | 📊 Participation Health | 💰 Treasury | ⚠️ Red Flags | 💡 Investor Insight

Keep response concise (< 600 words). Tables preferred for proposals list.
"""
```

---

### 📝 Files to Modify

Pattern identical Story 9.1/9.2/9.4:

#### 1. `chat_deepagent.py`

```python
from app.agents.new_chat.subagents.crypto.governance_analyst_spec import (
    GOVERNANCE_ANALYST_NAME, GOVERNANCE_ANALYST_DESCRIPTION, GOVERNANCE_ANALYST_PROMPT,
)

governance_analyst_tools = [
    tool for tool in tools if tool.name in ("chainlens_deep_research",)
]

governance_analyst_spec: SubAgent = {
    "name": GOVERNANCE_ANALYST_NAME,
    "description": GOVERNANCE_ANALYST_DESCRIPTION,
    "prompt": GOVERNANCE_ANALYST_PROMPT,
    "model": llm,
    "tools": governance_analyst_tools,
    "middleware": gp_middleware,
}

# Add to SubAgentMiddleware (now 9 sub-agents)
SubAgentMiddleware(
    backend=StateBackend,
    subagents=[
        general_purpose_spec,
        defillama_analyst_spec, sentiment_analyst_spec, news_analyst_spec, smart_contract_analyst_spec,
        tokenomics_analyst_spec, yield_optimizer_spec,
        whale_tracker_spec,
        governance_analyst_spec,  # Story 9.5 NEW
    ],
),
```

#### 2. `system_prompt.py` lookup table:
```
| governance_analyst | DAO proposals, voting outcomes, governance health, treasury, centralization risk | "DAO", "governance", "proposal", "vote", "treasury", "biểu quyết", "đề xuất" |
```

---

## Acceptance Criteria

### AC1-AC4: Foundation (identical pattern)

**AC1**: Spec file + 3 constants + wired (9 sub-agents total)
**AC2**: Prompt < 500 tokens
**AC3**: Tool scoping (chỉ chainlens_deep_research)
**AC4**: `requires=[]` (NFR-CS4)

### AC5: Functional — Active proposals

**Given** user hỏi "Aave có proposal nào đang active?"
**When** main agent spawn `governance_analyst`
**Then** agent gọi Chainlens với query về Aave Snapshot proposals
**And** trả response chứa ≥ 1 active proposal với: title, deadline, current vote ratio (% for/against)
**And** format đúng 6 sections theo prompt: 🗳️ Active, 📜 Outcomes, 📊 Health, 💰 Treasury, ⚠️ Red Flags, 💡 Insight

### AC6: Functional — Health metrics

**Given** user hỏi "Compound DAO health?"
**When** agent xử lý
**Then** agent quantify:
- Participation rate (e.g., "5.2% of COMP supply voted last 30 days")
- Top voter concentration (e.g., "top 10 hold 34% voting power")
- Quorum success rate (% proposals reach quorum)
**And** classify health: Healthy / Concerning / At Risk với evidence

### AC7: Hallucination guardrails (NFR-Q4) — CRITICAL cho governance

**Given** agent response với proposal titles, vote counts, dates
**When** QA verify vs raw Chainlens output + manual Snapshot check
**Then** 100% proposal IDs/titles match Chainlens output (no fabrication)
**And** 100% vote counts match (within rounding)
**And** dates accurate (no fabricated deadlines)
**And** controversial flags có evidence trace từ forum quotes (Chainlens citation)

### AC8: Graceful degradation (NFR-Q3)

**Given** Chainlens trả `{"status": "fallback"}`
**When** governance_analyst spawn
**Then** agent KHÔNG fabricate proposals
**And** trả response: "Governance data unavailable. Check Snapshot.org/{protocol} hoặc Tally.xyz/{protocol} directly"
**And** suggest user thử lại sau

### AC9: Parallel execution (NFR-Q2) — 9 agents

**Given** main agent comprehensive query Phase 2 active
**When** spawn parallel
**Then** 9 agents start trong cùng 1 step:
- 4 base + 9.1, 9.4, 9.2, 9.5 (NEW)
**And** parallelism ratio < 1.3x

### AC10: Accuracy baseline (NFR-Q1)

**Given** QA sample 50 governance queries trên top DAOs (Aave, Compound, Uniswap, MakerDAO, Curve, ENS)
**When** QA cross-check vs Snapshot/Tally
**Then** factual error rate **< 3%**
**And** health classification ≥ 85% agreement với manual expert review

### AC11: Neutral framing for controversial topics

**Given** agent response mention controversial decisions (e.g., proposal to slash team allocation)
**When** inspect framing language
**Then** neutral wording: "Some community members raised concerns about X"
**And** NOT inflammatory: "Greedy whales tried to steal funds"
**And** balance: present both sides if applicable

---

## Definition of Done (8 checkpoints)

- [ ] **DoD-1** Pre-flight: Phase 1 quality gate PASS + Chainlens reliability verified
- [ ] **DoD-2** `governance_analyst_spec.py` created
- [ ] **DoD-3** `chat_deepagent.py` wires spec (9 sub-agents)
- [ ] **DoD-4** Prompt < 500 tokens
- [ ] **DoD-5** Tool scoping enforced
- [ ] **DoD-6** Integration test: 9-agent parallel, ratio < 1.3x
- [ ] **DoD-7** QA: 50-query sample passed accuracy + hallucination + neutral framing review
- [ ] **DoD-8** Manual smoke test: 3 scenarios (active proposals / health analysis / controversial flag)

---

## Dev Notes

### Risks Specific to Story 9.5

| Risk | Mitigation |
|------|-----------|
| Chainlens không có Snapshot/Tally access | Pre-flight verify. Defer story nếu fail |
| Hallucinated proposal titles/outcomes | Strict prompt rule + AC7 100% verification |
| Inflammatory framing trên controversial votes | AC11 neutral framing review + prompt instruction |
| Governance "health" subjective → low expert agreement | Provide explicit metrics trong prompt (% participation, % concentration). AC10 expert review accept 85% (lower than 90% Story 9.2) |
| Proposal data stale (votes change daily) | Agent always cite "as of {date}" trong response |

### Testing Commands

```bash
cd nowing_backend

# Token budget
uv run python -c "
import tiktoken
from app.agents.new_chat.subagents.crypto.governance_analyst_spec import GOVERNANCE_ANALYST_PROMPT
enc = tiktoken.encoding_for_model('gpt-4')
print(f'Tokens: {len(enc.encode(GOVERNANCE_ANALYST_PROMPT))} / 500')
"

# Manual smoke test scenarios
uv run python tests/manual/test_governance_scenarios.py
# (Script chạy 3 queries: Aave proposals, Compound health, MakerDAO controversial)
```

### Phase 2 Quality Gate Decision

Sau Story 9.2 + 9.5 deployed:
1. Run Quality Gate Review (4 metrics x 100-query sample)
2. Compare với Phase 1 baseline:
   - Accuracy có maintain ở < 3%?
   - Parallelism ratio scale từ 6 agents (Phase 1) lên 9 agents có giữ < 1.3x?
   - Graceful degradation > 98% với 2 agents reliant Chainlens?
3. Decision:
   - ✅ ALL PASS → Phase 3 (9.3 + 9.6)
   - ⚠️ Marginal fail → Remediation sprint
   - ❌ Major fail → Rollback Phase 2, root cause analysis

### Rollback Plan

Identical: feature flag `CRYPTO_ORCHESTRA_PHASE2_ENABLED`, single-commit revert.

---

## Traceability

| Requirement | Source | Fulfilled By |
|-------------|--------|--------------|
| FR31 Governance Analyst | `prd.md` | AC1, AC5, AC6 |
| FR33 Parallel | `prd.md` | AC9 |
| FR35 Graceful | `prd.md` | AC8 |
| NFR-CS1 Token Budget | `prd.md` | AC2 |
| NFR-CS4 Stateless | `prd.md` | AC4 |
| NFR-Q1 Accuracy | `prd.md` | AC10 |
| NFR-Q2 Parallelism | `prd.md` | AC9 |
| NFR-Q3 Graceful | `prd.md` | AC8 |
| NFR-Q4 Hallucination | `prd.md` | AC7 |

---

**Status**: ready-for-dev ✅ (blocked on Phase 1 quality gate pass)
**Next**: Phase 2 Quality Gate Review → Phase 3 (9.3 Token Unlock + 9.6 Technical Analyst).
