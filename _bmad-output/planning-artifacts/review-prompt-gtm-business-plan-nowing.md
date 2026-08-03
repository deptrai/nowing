---
title: "Review Prompt — GTM & Business Plan for Nowing"
status: ready
purpose: "Prompt for another agent to review the GTM/business plan"
created: "2026-08-04"
review_target: "/Users/luisphan/Documents/GitHub/nowing/_bmad-output/planning-artifacts/gtm-business-plan-nowing-2026-08-04.md"
---

# Review Prompt — GTM & Business Plan for Nowing

> Use this prompt as-is or pass it to another agent / review skill (`bmad-review-adversarial-general`, `bmad-checkpoint-preview`, or a custom reviewer).

---

## Your Role

You are a **strategic business reviewer** for an open-source AI product. You are reviewing a go-to-market and business plan that was synthesized from `bmad-market-research` and `bmad-cis-innovation-strategy`. Your job is to find weak logic, unstated assumptions, factual gaps, competitive blind spots, and execution risks. Be adversarial but constructive. Do not flatter. Do not assume the plan is correct.

The audience is the PO (Luisphan) and the engineering team. They are dev-strong, GTM-thin. The product is Nowing, an open-source research memory for AI agents.

---

## Required Inputs

Read these documents in this order before reviewing:

1. **The plan to review:**
   <ref_file file="/Users/luisphan/Documents/GitHub/nowing/_bmad-output/planning-artifacts/gtm-business-plan-nowing-2026-08-04.md" />

2. **Market research underlying the plan:**
   <ref_file file="/Users/luisphan/Documents/GitHub/nowing/_bmad-output/planning-artifacts/research/market-nowing-gtm-research-2026-08-04.md" />

3. **Innovation strategy underlying the plan:**
   <ref_file file="Users/luisphan/Documents/GitHub/nowing/_bmad-output/planning-artifacts/innovation-strategy-nowing-2026-08-04.md" />

4. **Baseline context:**
   <ref_file file="/Users/luisphan/Documents/GitHub/nowing/_bmad-output/planning-artifacts/business-plan-baseline-nowing-2026-08-04.md" />

5. **Source-of-truth product documents (read relevant sections):**
   - <ref_file file="/Users/luisphan/Documents/GitHub/nowing/_bmad-output/planning-artifacts/briefs/brief-Nowing-2026-07-25/brief.md" />
   - <ref_file file="/Users/luisphan/Documents/GitHub/nowing/_bmad-output/planning-artifacts/prds/prd-Nowing-2026-07-22/prd.md" />
   - <ref_file file="/Users/luisphan/Documents/GitHub/nowing/_bmad-output/planning-artifacts/sprint-change-proposal-2026-07-25-chainlens-engine-boundary.md" />
   - <ref_file file="/Users/luisphan/Documents/GitHub/nowing/_bmad-output/planning-artifacts/epics.md" />

---

## Review Dimensions

For each dimension, rate the plan **Strong / Adequate / Weak / Unacceptable** and give specific evidence + actionable recommendations.

### 1. Strategic Coherence
- Does the recommended strategy (Option A — Open-Core PLG + Usage-Based Cloud) flow logically from the vision, target user, and constraints?
- Are the three non-goals (NG-1, NG-2, NG-3) respected throughout?
- Is the reasoning for rejecting Option B and Option C sound?

### 2. Market Sizing Sanity
- Are TAM ($12–15B), SAM ($2.0–2.8B), and SOM ($10–30M ARR) justified? What assumptions are most fragile?
- Is the 0.5–3% OSS-to-cloud conversion benchmark appropriate for this product/category?
- Is the $100–$800/mo ARPU assumption realistic?

### 3. Competitive Positioning
- Is the “live web/UGC into self-hosted memory with provenance” wedge durable?
- What would it take for Onyx, Mem0, or Perplexity to close the wedge? How does the plan address that?
- Is the moat claim (head start + integration depth + data-acquisition operations) honest or overstated?

### 4. Business Model & Pricing
- Is the three-tier license model (Apache-2.0 / BSL 1.1 / closed) clear and defensible?
- Is the 1.5–2.5× margin target achievable given deep-research cost volatility?
- Are the pricing packages (self-host free, cloud pay-as-you-go, team/enterprise subscription) sequenced correctly?
- What is missing from the unit economics? (e.g., CAC, support cost, payment processing, churn)

### 5. GTM Motion Feasibility
- Given the team is “dev-strong, GTM-thin,” is the MCP/GitHub/HN-only distribution plan realistic?
- Are the M1 (≤15 minutes to first useful recall) and conversion funnel assumptions testable?
- Is there enough detail on what the “Show HN” launch should look like?

### 6. Execution Roadmap & Gates
- Is the gate sequence correct? (NFR-8 → FR-38 → FR-37 → 8.7)
- Are Phase 1, 2, 3 boundaries realistic?
- Is State B (sync chat-mode) gating handled conservatively enough?

### 7. Risks & Mitigations
- Which risks are under-mitigated or missing entirely?
- Are there second-order risks not covered? (e.g., community backlash from BSL, DeepSeek/Gemini model cost swings, open-source contributor expectations)
- Is the legal/retention risk (OQ-3) taken seriously enough?

### 8. Metrics
- Are leading/lagging indicators well-chosen?
- Are SM-10, SM-11a/b/c defined precisely enough to be measured?
- Is there a missing metric that would catch failure earlier?

### 9. Messaging
- Is the “do say / don’t say” table compliant with the license and non-goals?
- Could any messaging still trigger HN/Reddit backlash?
- Is the one-liner distinctive and believable?

### 10. Actionability
- Can the engineering team act on this plan tomorrow, or are too many items still vague?
- Is the owner/function for each mitigation clear?

---

## Specific Questions to Answer

1. **What is the single biggest unstated assumption that could invalidate this plan?** Name it and say what evidence would disprove it.

2. **Where is the plan most vulnerable to an incumbent’s fast follow?** Pick one competitor and describe a plausible 6-month response that would hurt Nowing.

3. **Is the pricing model likely to produce positive gross margin?** Build a rough bottom-up unit economic check for one typical cloud deep-research call and one typical month of an active research team.

4. **What would make self-hosters convert to cloud?** Is deep-research alone enough, or should the plan include cloud-only collaboration/team features earlier?

5. **Should the plan sequence cloud-first or self-host-first differently?** Defend your answer with GTM and technical trade-offs.

6. **What is the minimum viable “Show HN” launch?** List the exact artifacts (README, demo, MCP server, docker-compose, landing) that must be ready and their quality bar.

7. **Where does the plan over-rely on ChainLens?** Identify dependencies that are not under Nowing’s control and suggest risk mitigation.

8. **Are there missing non-goals or anti-goals?** Suggest 1–2 additional things Nowing should explicitly decide NOT to do.

---

## Output Format

Write your review to:

`/Users/luisphan/Documents/GitHub/nowing/_bmad-output/planning-artifacts/review-gtm-business-plan-nowing-2026-08-04.md`

Use this structure:

```markdown
# Review — GTM & Business Plan (Nowing)

## 1. Overall Verdict
[Strong / Adequate / Weak / Unacceptable] with one-paragraph summary.

## 2. Dimension-by-Dimension Review
### 1. Strategic Coherence
- Rating: X
- Evidence: ...
- Recommendation: ...

... repeat for all 10 dimensions ...

## 3. Answers to Specific Questions
### Q1 ...
...

## 4. Top 5 Action Items (prioritized)
1. ...
2. ...
3. ...
4. ...
5. ...

## 5. Red Flags — Must Fix Before Approval
- ...
- ...

## 6. Optional Enhancements
- ...
```

Language: primarily English, with Vietnamese summary callouts where the finding is critical for the team.

---

## Constraints

- Do not modify the reviewed plan. Produce a review file only.
- Do not introduce new dependencies or skills unless you note them as suggestions.
- Be specific. Avoid generic advice like “do more marketing” or “talk to customers more.” Quote plan lines/sections when criticizing.
- If you find a factual claim unsupported by the inputs, flag it explicitly.
- If you are uncertain, say so and explain what evidence would resolve the uncertainty.
