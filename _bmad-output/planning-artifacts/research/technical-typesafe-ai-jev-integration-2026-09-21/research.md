---
title: 'technical research: TypeSafe AI / Jev — machine-native decision model'
type: 'technical'
topic: 'TypeSafe AI Jev integration into Nowing'
decision: 'Should Nowing integrate Jev as a decision layer, and where in the stack'
source: 'native run'
status: complete
preset: 'standard'
validation: 'normal'
created: '2026-09-21'
updated: '2026-09-21'
verified_claims: 9
unverified_claims: 2
---

# Technical research: TypeSafe AI / Jev — machine-native decision model

**Decision this research serves:** Nowing có nên integrate Jev (TypeSafe AI) làm decision layer, và nếu có thì ở đâu trong stack?

---

## Executive summary

**Verdict: Jev đáng integrate vào Nowing, nhưng theo cách cụ thể — không phải thay thế LLM, mà làm decision primitive layer bên cạnh LLM.**

Ba findings drive kết luận này:

1. **Jev là primitive mới, không phải LLM nhỏ.** Nó trả về typed decisions (Choice/Score/Noul) với calibrated probabilities + confidence, 70-500ms/call, $42/B input tokens, output free. Không generate text, không hallucinate theo nghĩa schema — nhưng "0% hallucination" là schema-match guarantee, không phải correctness guarantee. [1][4]

2. **Fit mạnh nhất ở 3 điểm trong Nowing:** (a) subagent routing trong LangGraph multi-agent chat — thay LLM router 8.5s bằng 114ms typed decision; (b) entity resolution / dedup confidence scoring trong canonical pipeline — per-pair cost ~$0.0004 makes previously uneconomic per-item gates viable; (c) confidence-gated human review — Jev's core design axis là "act autonomously when confident, escalate when not". [1][5]

3. **Risk profile: 6-day-old product, $40M DCVC seed, credible founders (RLHF co-inventor), but no independent benchmarks, no Vietnamese language data, self-admitted possibly-subsidized pricing.** Mitigation: `system-one-adapter-python` [14] (official drop-in LLM fallback) + pin versioned model IDs + build ground-truth eval on Nowing's Vietnamese content before trusting confidence thresholds. [3][6][9]

**Biggest caveat:** Jev is English-primary [19]; Vietnamese performance is completely unknown — nowhere tested, not in docs, not in any community project found. Nowing is a Vietnamese-first platform. This is the single largest unknown.

---

## Dimension 1-2: What is Jev + Maturity

### Product definition

Jev is TypeSafe AI's flagship "System One Model" — a new model class trained with RLCD (Reinforcement Learning for Calibrated Decisions) instead of RLHF. Where LLMs generate text (optimized for human preference), Jev produces typed decisions with probabilities (optimized for calibrated judgment). [1]

**Three primitives, all in one API call:**

| Primitive | Question | Returns | Use case |
|-----------|----------|---------|----------|
| **Choice** | "Which of these options?" | `choice`, `probabilities`, `confidence` | Routing, classification, selection |
| **Score** | "Rate on this rubric" | `score`, `legend`, `probabilities`, `confidence` | Severity, quality, frustration |
| **Noul** | "Is this true?" | `noul` (0-1 probability) | Detection, verification, yes/no gates |

Confidence (0-1) is derived from the probability distribution shape — concentrated = confident, spread = uncertain [16].

All questions in one request evaluate **in parallel** against the same `state` — adding questions barely changes latency. No context-rot between questions. [4]

### API & SDK

- **Endpoint:** `POST https://api.typesafe.ai/v1/systemone` — `{state, model, questions: map<id, Question>}` → `{model, answers: map<id, Answer>}`
- **SDKs:** `typesafe-sdk` (PyPI v0.7.0, Python) + `@typesafe-ai/sdk` (npm v0.6.0, TypeScript) [15] — both official, sync+async, auto-retry on 429/529
- **Auth:** `TYPESAFE_API_KEY` env var, Bearer token
- **Limits:** 250K tokens/sec, 1,200 req/min, 64k context (32k state + longest question)
- **Distribution:** direct API + Vercel AI Gateway + OpenRouter + Cloudflare Workers AI [8]

### Pricing

$42/B input tokens ($0.042/MTok); output tokens free. Vendor admits "we can't prove it isn't subsidized." No free tier found. [1]

### Company

- **Founder/CEO:** Diogo Almeida — ex-OpenAI, co-invented RLHF, helped build ChatGPT/InstructGPT
- **Co-founders:** Erik Gafni, Sasha Sheng
- **Stage:** Seed-stage, ~2 years in stealth, launched 2026-09-15
- **Funding:** $40M seed led by DCVC at ~$200M valuation (Forkast, press-reported) [7]
- **Team:** ex-OpenAI, Google Brain, Meta/FAIR, Stripe, Airbnb, Plaid, Docker. SF in-person. [10]
- **HN launch:** 1,929 points, 509 comments — massive traction, briefly lost ability to serve users [13]

### Performance claims

| Claim | Vendor says | Independent check | Confidence |
|-------|------------|-------------------|------------|
| 70-500ms latency | Yes, per call | Cua measured 260-280ms hosted; HN user 712ms P50 | Medium — vendor-claimed, partial corroboration |
| 193.6x faster, 444.6x cheaper | Workflow evals vs avg GPT-6 Astra + Fable 5.1 | Self-authored workflows, disclosed bias | Low-medium — honest about methodology |
| Zero hallucination | Schema-match guaranteed | HN: "approve for unauthorized action still meets schema" — misleading framing | Medium — schema guarantee ≠ correctness |
| Calibrated probabilities | RLCD training | Bryo AI tested vs Gemini: slightly less accurate, 10-20x cheaper [17] | Unverified |

### Jaggedness (official limitations, jev-1.13)

9 documented failure modes: literal reading, no math/counting, dates as text, multi-hop indirection, large-state degradation, adversarial content vulnerability, contradictory criteria confusion, no structural invariants, no generation. [9]

### Key differentiator vs alternatives

Not just "structured output" — the model is *trained* for calibrated probabilities. JSON mode forces schema; Jev's probabilities are optimized against outcomes. Skeptics note this may not be a moat (prefill + constrained decoding approximates it), but the calibration quality is the differentiator. [6]

---

## Dimension 3: Fit with Nowing stack

### Fit map

| Nowing subsystem | Jev fit | Reason |
|---|---|---|
| **Multi-agent chat router** (LangGraph main → subagents) | **HIGH** | Canonical "intent routing" pattern [20]. 70-500ms typed decision vs seconds-long LLM router. Choice over subagent types (chainlens, batdongsan, recruitment, etc.). Confidence-gated fallback to main agent on uncertainty. |
| **Scraper / entity resolution / canonical pipeline** | **HIGH** | Entity alignment cookbook is a direct analog: Score for merge/curate/different, Nouls per field [11]. Per-pair cost ~$0.0004 makes per-item gates economically viable at scraper volume. |
| **Confidence-gated human review** (cross-cutting) | **HIGH** | Jev's core design axis. Confidence thresholds scale with action risk — exactly what Nowing's human-review-gate pattern needs. |
| **RAG passage classification** | **HIGH** | Cookbook shows 4-question-per-passage filter: relevance, evidence, contradiction, prompt injection. Directly applicable to Nowing's RAG. |
| **Voice agent worker** (LiveKit + Silero VAD) | **MEDIUM** | Text-only — cannot replace VAD. But post-STT semantic decisions fit: turn-taking above VAD (LiveKit's turn-detector pattern), frustration scoring, human-transfer gating. 70-500ms fits LiveKit's endpointing-delay budget. |
| **Connector sync** | **MEDIUM** | Document-type classification, change triage, sync-conflict decisions. Latency irrelevant — win is cost + calibrated confidence. |
| **LLM guardrails** (chat input/output screening) | **HIGH** | Official cookbook: battery of Noul (jailbreak? harmful? PII?) + Score (severity) in one request [12]. Both input and output screening. Two-threshold policy: action vs review. |
| **ChainLens research** | **LOW-MEDIUM** | Core is generation — Jev can't generate. Fit as cheap verifier/guardrail over agent traces and tool-call routing. |
| **Billing / quota (P0)** | **N/A** | Money decisions are exact arithmetic — Jev's own manifesto says code handles computation. At most offline anomaly detection. |

### What Jev does NOT solve for Nowing

- **Generation/synthesis/chat** — Jev cannot produce text. All LLM-powered features stay on LLM.
- **Reasoning** — no chain-of-thought, no multi-step inference. "Gut-check" decisions only.
- **Vietnamese-first content** — English-primary training [19]. Jev may work on Vietnamese text but accuracy is untested. **Must evaluate before deployment.**
- **Audio/image inputs** — text only. Voice pipeline needs STT first, then Jev on transcript.

---

## Dimension 4-5: Integration approach + Risk

### Integration architecture

```
┌─────────────────────────────────────────────────┐
│  Nowing Backend (FastAPI)                       │
│                                                 │
│  ┌──────────────┐    ┌──────────────────────┐   │
│  │ LangGraph    │    │ DecisionService      │   │
│  │ Multi-Agent  │───→│ (new abstraction)    │   │
│  │ Chat         │    │                      │   │
│  └──────────────┘    │  ┌────────────────┐  │   │
│                      │  │ TypeSafeClient   │  │   │
│  ┌──────────────┐    │  │ (typesafe-sdk)   │  │   │
│  │ Scraper /    │───→│  └────────────────┘  │   │
│  │ Entity Resol │    │         OR           │   │
│  └──────────────┘    │  ┌────────────────┐  │   │
│                      │  │ SystemOneAdapter │  │   │
│  ┌──────────────┐    │  │ (LLM fallback)   │  │   │
│  │ Voice Agent  │───→│  └────────────────┘  │   │
│  │ (post-STT)   │    └──────────────────────┘   │
│  └──────────────┘              │                │
│                                 ▼                │
│                      api.typesafe.ai             │
│                      OR any OpenAI/Anthropic     │
│                      endpoint via adapter        │
└─────────────────────────────────────────────────┘
```

**Recommended abstraction:** Build a `DecisionService` that wraps `TypeSafeClient` (or `SystemOneAdapterClient`) behind Nowing's own interface. This keeps:
- Question definitions + thresholds centralized (TypeSafe's own advice)
- Backend swap possible without changing callers
- A/B testing Jev vs LLM on same question set
- Fallback path if TypeSafe API degrades

### Alternatives matrix

| Alternative | Latency | Cost/decision | Calibration | Ops burden | Vendor risk | Notes |
|---|---|---|---|---|---|---|
| **Jev (TypeSafe)** | 70-500ms | ~$0.0004 | Native calibrated | Low — hosted API | High — 6-day-old product | Official adapter = escape hatch |
| **LLM JSON mode** (via adapter) | 3-329s | 10-444x more | Poor natively | Low-medium | Low — multi-provider | Default fallback; same interface |
| **Constrained decoding** (Outlines, Instructor) | Inference-bound | GPU cost | Schema only, no calibration | Medium-high | Low — OSS | Need labeled data for calibration |
| **Self-hosted RLCD replicas** (Open-Jev-2B/9B) | GPU-bound, local | Marginal | Unverified | High | Low — Apache-2.0 | Immature, days old |
| **Small classifiers** (DistilBERT, SetFit) | Fastest (ms) | Cheapest at scale | Must recalibrate per task | Highest — training pipeline | None | Requires labeled data + training |
| **Gateway-routed Jev** (Vercel/Cloudflare) | +gateway hop | May differ | Same model | Lowest | Medium | Check rate/data terms |

### Risk register

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| **Vietnamese performance unknown** | HIGH concern | HIGH if deployed on vi content | **Build Vietnamese ground-truth eval FIRST** — test Jev on Nowing's actual vi content before any production threshold |
| Vendor fold / API dies | Medium ($40M seed, but early) | High | `system-one-adapter-python` = official exit ramp; keep Noul/Choice/Score as internal abstraction |
| Price change / subsidy ends | Medium-high (vendor admits) | Medium | Per-decision cost telemetry; adapter enables A/B vs LLM |
| Alias drift (`jev-latest` moves) | High (documented) | Medium | Pin `jev-1.13.0`; log returned model version per response |
| Accuracy regression on Nowing workload | Medium | High if thresholds gate autonomy | Own ground-truth eval; don't trust vendor benchmarks |
| Capacity/availability (529 exists; launch-day outage) | Medium early access | Medium | SDK retry + confidence-gated fallback in code |
| Ecosystem hype vs reality | High (3 same-day awesome repos) | Low-medium | Verify code exists before citing adoption |
| Key-person risk (Almeida = public face) | Low-medium | Medium | Monitor team growth, hiring |

### Lock-in mitigation

The decisive mitigant is **TypeSafe's own `system-one-adapter-python`** [14] — a drop-in `TypeSafeClient` replacement backed by OpenAI/Anthropic structured outputs. This means:
- Same `system_one(state, questions)` call shape works with any LLM
- The Noul/Choice/Score primitive contract is the abstraction layer to keep in your code
- Migration path is first-party, not DIY
- A/B testing is trivially possible

---

## Cross-dimension insights

1. **The adapter changes the risk calculus.** Without `system-one-adapter-python`, Jev would be a risky vendor dependency. With it, the integration cost is bounded — you write to the interface, not the vendor. TypeSafe shipping their own exit ramp is either confidence or pragmatism; either way, it protects integrators.

2. **The "Jev-shaped hole" in Nowing is real.** Nowing's architecture already separates decision (routing, classification, scoring) from generation (LLM chat, research synthesis). Jev fits exactly into the decision side. The LangGraph subagent dispatch, entity-resolution dedup, and human-review gates are the three highest-value insertion points — all currently use LLMs where a decision primitive would suffice.

3. **Vietnamese is the gating unknown.** Jev is English-primary [19]. Nowing's users, content, and voice pipeline are Vietnamese-first. Before any production use, Nowing needs a Vietnamese eval: does Jev maintain calibrated confidence on Vietnamese text? If not, the use case narrows to English-content features only.

4. **Cost model favors Jev at scale.** ~$420/month for 10M decisions vs $2K-$100K for equivalent LLM calls. But at Nowing's current scale, the adapter path may be cheaper than the integration effort — the win is latency (114ms vs 8.5s), not cost.

5. **The category is forming.** Open-Jev replicas, CUA-S1 (computer use), community SDKs in 7 languages, Vercel/Cloudflare/OpenRouter distribution — "System One Model" is becoming a category, not a product. If TypeSafe folds, the concept survives; the adapter preserves the interface.

---

## Contrary evidence

- **"Not a moat" argument** (Sean Goedecke, 2026-09-18): prefill + one-token constrained generation on ordinary LLMs reproduces most of Jev's value. The calibration advantage is real but may not be durable.
- **"0% hallucination" is misleading** (HN commenters): schema-match ≠ correctness. Jev can pick the wrong option with high confidence — it just can't produce a type error.
- **CUA-S1-FORMS** (706K param specialist model): beat hosted Jev 99.7% vs 83.6% on its scoped task [18] at 7-9ms local vs 260-280ms hosted. Specialist > generalist on narrow tasks.
- **Prior art exists**: March 2025 arxiv paper claims similar non-autoregressive probability prediction; GLiNER comparisons on HN; diffusion LLMs could serve same function.
- **No production case study** besides Vercel anecdote [2]; no SLA; launch-day capacity failure.

---

## Recommendations

### For Nowing integration

**R1: Build a `DecisionService` abstraction now, evaluate Jev alongside LLM fallback.**
- Implement `DecisionService` wrapping `TypeSafeClient` + `SystemOneAdapterClient` behind a common interface
- Question definitions + thresholds in a single config file (TypeSafe's own best practice)
- Pin `jev-1.13.0`, not `jev-latest` — control model upgrades on your schedule
- Confidence basis: medium-high — adapter makes this low-risk to try

**R2: First integration target: subagent routing in multi-agent chat.**
- Replace or augment LLM router with Choice over subagent types
- Latency win: ~114ms vs seconds for LLM router
- Confidence-gated: low-confidence → fallback to main agent (existing behavior)
- Confidence basis: high — canonical intent-routing pattern, Vercel validated similar use

**R3: Second target: entity resolution confidence scoring.**
- Score for merge/curate/different + Noul per field match
- Entity alignment cookbook is a direct analog
- Cost viable at scraper volume (~$0.0004/pair)
- Confidence basis: high — cookbook mirrors Nowing's dedup problem

**R4: Third target: LLM guardrails on chat input/output.**
- Noul battery (jailbreak, PII, harmful) + Score (severity) in one request
- Two-threshold policy: action vs review
- Confidence basis: medium-high — official cookbook exists; test on Vietnamese prompts first

**R5: Before production — build Vietnamese eval.**
- Take 50-100 real Nowing use cases in Vietnamese
- Run through Jev + adapter + LLM JSON mode
- Compare accuracy, latency, cost per decision
- If Vietnamese accuracy is acceptable → deploy; if not → restrict to English-content features
- Confidence basis: this is the gating unknown; everything else is secondary

**R6: Voice agent — post-STT semantic decisions only.**
- Jev cannot replace Silero VAD (text-only, VAD is frame-level)
- Post-STT: turn-taking confidence, frustration scoring, human-transfer gating
- 70-500ms fits LiveKit's endpointing-delay budget
- Confidence basis: medium — LiveKit's own turn-detector pattern validates the slot

### NOT recommended

- **Don't put Jev in billing/quota path** — money decisions are exact arithmetic, not probabilistic judgment
- **Don't replace LLM for generation** — Jev cannot generate text; it's a complement, not replacement
- **Don't trust `jev-latest` alias in production** — pin versioned IDs
- **Don't skip the adapter** — even if you use Jev, keep `system-one-adapter-python` as the interface contract for portability

---

## Open questions

1. **Vietnamese accuracy** — does Jev maintain calibration on Vietnamese text? (No data anywhere; must test.)
2. **Pricing sustainability** — is $42/Btok subsidized? (Vendor admits uncertainty.)
3. **Model size/architecture** — undisclosed; suspected open-weight base + custom head.
4. **Independent benchmarks** — all evals are self-published; Every tested one task; no third-party comprehensive eval.
5. **Funding confirmation** — $40M/DCVC is press-reported only, no primary source.
6. **Enterprise terms** — ZDR, SLA, uptime guarantees, custom rate limits — need console access or sales call.
7. **RLCD paper** — founder says "architecture is close to the chest"; no published paper exists.
8. **Streaming API** — no streaming surface found; unclear if private/enterprise streaming exists.

---

## Source appendix

| # | Claim/finding | Publisher | Pub date | Accessed | Confidence |
|---|---|---|---|---|---|
| 1 | Jev pricing $42/Btok, 70-500ms, typed primitives | [TypeSafe AI docs](https://docs.typesafe.ai/models) | Live site | 2026-09-21 | High |
| 2 | Vercel deployment 5-18x faster than GPT Luna 5.6 | [TechCrunch](https://techcrunch.com/2026/09/18/a-new-kind-of-ai-model-from-a-chatgpt-inventor-is-thrilling-developers/) | 2026-09-18 | 2026-09-21 | Medium (single source) |
| 3 | "193.6x faster, 444.6x cheaper" workflow evals | [TypeSafe AI blog](https://typesafe.ai/blog/introducing-system-one-models-and-jev) | 2026-09-15 | 2026-09-21 | Low-medium (self-published, bias disclosed) |
| 4 | API shape: POST /v1/systemone, Choice/Score/Noul | [TypeSafe AI docs](https://docs.typesafe.ai/api) | Live site | 2026-09-21 | High |
| 5 | RAG passage classification cookbook | [TypeSafe AI docs](https://docs.typesafe.ai/cookbooks/classifying_rag_passages) | Live site | 2026-09-21 | High |
| 6 | "Not a moat" critique — prefill + constrained decoding | [Sean Goedecke blog](https://seangoedecke.com) | 2026-09-18 | 2026-09-21 | Medium (opinion) |
| 7 | $40M DCVC seed, ~$200M valuation | [Forkast](https://forkast.news) | 2026-09-18 | 2026-09-21 | Medium (press-reported) |
| 8 | Distribution: Vercel AI Gateway, OpenRouter, Cloudflare | [awesome-jev](https://github.com/MrJev/awesome-jev) + [Vercel changelog](https://vercel.com/changelog) | 2026-09 | 2026-09-21 | Medium (community-verified) |
| 9 | Jev 1.13 jaggedness — 9 failure modes | [TypeSafe AI docs](https://docs.typesafe.ai/model-jaggedness/jev-1.13) | Live site | 2026-09-21 | High (official) |
| 10 | Team: ex-OpenAI/Google Brain/Meta FAIR, SF | [TypeSafe AI team page](https://typesafe.ai/team) | Live site | 2026-09-21 | High |
| 11 | Entity alignment cookbook (450-pair beer benchmark) | [TypeSafe AI docs](https://docs.typesafe.ai/cookbooks/entity_alignment) | Live site | 2026-09-21 | High |
| 12 | LLM guardrails cookbook (jailbreak detection) | [TypeSafe AI docs](https://docs.typesafe.ai/cookbooks/llm_guardrails) | Live site | 2026-09-21 | High |
| 13 | HN launch: 1929 pts, 509 comments | [Hacker News](https://news.ycombinator.com/item?id=49717558) | 2026-09-15 | 2026-09-21 | High |
| 14 | system-one-adapter-python: LLM fallback | [GitHub](https://github.com/typesafe-ai/system-one-adapter-python) | Live repo | 2026-09-21 | High |
| 15 | Python SDK 0.7.0 (Pydantic), JS SDK 0.6.0 [15] | [PyPI](https://pypi.org/project/typesafe-sdk/) + [npm](https://www.npmjs.com/package/@typesafe-ai/sdk) | 2026-09 | 2026-09-21 | High |
| 16 | Confidence mechanics: derived from probabilities | [TypeSafe AI docs](https://docs.typesafe.ai/confidence) | Live site | 2026-09-21 | High |
| 17 | Bryo AI: Jev vs Gemini — slightly less accurate, 10-20x cheaper | [TechCrunch](https://techcrunch.com/2026/09/18/a-new-kind-of-ai-model-from-a-chatgpt-inventor-is-thrilling-developers/) | 2026-09-18 | 2026-09-21 | Medium |
| 18 | CUA-S1-FORMS: specialist beats Jev 99.7% vs 83.6% | [Hacker News](https://news.ycombinator.com) | 2026-09-19 | 2026-09-21 | Medium |
| 19 | English-primary; other languages "handled but not equally well" | [TypeSafe AI docs](https://docs.typesafe.ai/models) | Live site | 2026-09-21 | High |
| 20 | LangGraph router pattern (conditional edges) | [LangChain docs](https://docs.langchain.com) | Live site | 2026-09-21 | Medium |

---

## Staleness map

| Claim | Class | Pub date | Freshness bar | Re-check by |
|---|---|---|---|---|
| Jev pricing $42/Btok | pricing | 2026-09 | ≤1 mo | 2026-10-21 |
| Rate limits 250K tok/s | version | 2026-09 | ≤1 mo | 2026-10-21 |
| Jev 1.13.0 current | version | 2026-09 | ≤1 mo | 2026-10-21 |
| SDK versions (py 0.7.0, js 0.6.0) | version | 2026-09 | ≤1 mo | 2026-10-21 |
| $40M DCVC seed | company | 2026-09 | ≤6 mo | 2027-03-21 |
| Ecosystem 209 entries | ecosystem | 2026-09 | ≤6 mo | 2027-03-21 |
| Vietnamese performance | risk | — | No data yet | After eval |
| Latency 70-500ms | performance | 2026-09 | ≤6 mo | 2027-03-21 |
| Benchmark 193.6x/444.6x | performance | 2026-09 | ≤3 mo (AI-adjacent) | 2026-12-21 |

**Earliest re-check:** 2026-10-21 (pricing + version claims expire first).
