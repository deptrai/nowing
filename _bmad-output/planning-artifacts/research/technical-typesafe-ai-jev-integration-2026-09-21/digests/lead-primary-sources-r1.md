# Lead's primary-source digest — typesafe.ai official site/docs/blog

**Accessed:** 2026-09-21
**Source class:** Primary (official TypeSafe AI website, docs, blog, GitHub org)

## Company & team
- Founder: **Diogo Almeida** — ex-OpenAI, helped build InstructGPT/RLHF (the research behind ChatGPT). [typesafe.ai/blog/introducing-system-one-models-and-jev]
- Team: ex-OpenAI, Google Brain, Meta/FAIR, Stripe, Airbnb, Plaid, Docker. In-person SF office near Embarcadero. "Backed by top-tier investors" (unnamed on site). [typesafe.ai/team]
- Founded: ~2 years in stealth before public launch (launch ~2026 per blog post "today we are releasing Jev"). Blog posts dated Jun-Sep 2026.

## Product — Jev (System One Model)
- **3 primitives**: Choice (pick from ≤255 options + probabilities + confidence), Score (rubric ≤10 levels + probabilities + confidence), Noul (yes/no 0-1 probability, no separate confidence)
- **API**: `POST /v1/systemone` — request body `{state, model, questions: map<id, Question>}`. Questions evaluated **in parallel** in a single call; adding questions barely changes latency. No context-rot between questions.
- **SDKs**: `typesafe-sdk-python` (161★), `typesafe-sdk-js` (191★) on github.com/typesafe-ai. Install `uv add typesafe-sdk`, env `TYPESAFE_API_KEY`.
- **Client shape**: `client.system_one(state={...}, questions={id: Choice/Noul/Score(...)})` → typed response with `response.choices[id].choice`, `.probabilities`, `.confidence`.

## Pricing & performance (vendor claims)
- $42/B input tokens ($0.042/MTok); output tokens FREE ("too cheap to meter")
- 70-500ms end-to-end response time (40-200x faster than LLMs on System One tasks)
- Claims "193.6x faster, 444.6x cheaper" vs workflow-eval baseline (average of GPT-6 Astra + Fable 5.1) — vendor's own workflow evals, they disclose potential bias
- Zero type errors "mathematically impossible" — schema guaranteed by model architecture, not parsed

## Key technical differences vs LLM
- **Parallel sampling**: generates all outputs in single query, not autoregressive token-by-token
- **RLCD training**: optimizes for calibrated decisions with honest probabilities (vs RLHF human preference, RLVR verifiable rewards)
- **No string generation**: "gives up strings" — cannot write text, code, explanations. Only typed decisions.
- **Calibrated confidence**: built into model output, not prompted. Used to gate autonomous vs human-review paths.
- **Cardinality cap**: 255 options per Choice. Higher-cardinality uses 2-stage pattern (score then choose).

## Architectural patterns (official)
- **Speculative Fan-Out**: send many questions including speculative ones in one call; 13 questions in 1 call = 11.5x cheaper, 9.6x faster than 13 calls
- **Confidence-Gated Routing**: thresholds on confidence for autonomous vs escalate paths; threshold scales with action risk
- **Composite Scoring**: split multi-factor judgment into N Score questions, weight in code
- **Intent Routing**: classify user intent → route to handler (the canonical "smart if-statement")

## Use case map (official docs)
Classification, Detection (spam/fraud/urgency/jailbreak/PII), Scoring (severity/relevance/quality), Routing (tool/escalation/model), Search, Retrieval (RAG context), Ranking, Verification (citation/policy/tool-call/response quality), ML Feature Extraction, Structured Data Extraction

## Cookbooks (evidence of real use cases)
autoformat, autoresearch_feature_discovery, citation_check, classification_using_confidence, classifying_rag_passages, consistency_choice, consistency_noul, date_extraction, entity_alignment, function_calling, hierarchical_classification, llm_guardrails, parallel_questions, pre_parsed_value_extraction, rerank_typesafe, sde_cascade, semantic_find, skill_suggestion

## Lock-in mitigation — IMPORTANT FINDING
**`system-one-adapter-python`** (209★, official repo): drop-in replacement for `typesafe_sdk`'s `system_one` API backed by LLM APIs. Supports OpenAI-compatible + Anthropic native. Lets you:
- Compare TypeSafe vs LLM on cost/speed/intelligence on YOUR workload
- Migrate off Jev to any LLM while keeping the same call shape
- Use custom endpoints (e.g. self-hosted, OpenRouter, x.ai)
This is TypeSafe's own hedge — they ship the exit ramp.

## Agent skills
- `skills` repo (1284★) — "Agent skills for building with TypeSafe's System One API" — likely Claude Code/agent-compatible skill definitions. Worth exploring for Nowing integration.

## Ecosystem signals
- 493 GitHub repos matching "typesafe ai jev" (mostly community, low stars — very early ecosystem)
- Community projects: jev-mcp (Rust MCP server), duckdb-jev (DuckDB extension), HA-Jev (Home Assistant), jev-spec (spec-driven semantic verification)
- Docs domain: docs.typesafe.ai — comprehensive, well-organized, cookbooks+patterns+SDK refs
- Model versioning: jev-1.13 exists under /model-jaggedness/ (jaggedness tracking is unusual transparency)

## Gaps / not yet verified
- Public eval methodology is vendor-published; "193.6x/444.6x" is on workflow evals they authored (disclosed bias)
- No independent benchmark verification found yet
- Pricing sustainability: "we can't prove it isn't subsidized" (their own words)
- Early access — not GA; rate limits, quotas, SLA unknown
- Company funding amount not disclosed on site
- No SOC2/security/compliance info surfaced yet

---

## UPDATE — Model specs + key cookbooks

### Jev 1.13 specs (docs.typesafe.ai/models)
- **Price**: $42/Btok ($0.042/Mtok) input; output FREE
- **Rate limits**: 250,000 tokens/sec, 1,200 req/min
- **Context**: 64k tokens/request total; 32k for state + longest question
- **Input**: text only — string, JSON object, or array of text. No image/audio/video.
- **Aliases**: `jev-latest` → jev-1.13.0, `jev-preview` → latest preview. Pin versioned ID for reproducibility.
- **No per-customer fine-tuning** — same weights for all accounts. Shape via `state` + `instructions`/`criteria`.
- **Language**: English primary; other languages (incl CJK) "handled but not equally well" — important caveat for Vietnamese Nowing use cases.
- **Data**: not trained on customer requests. ZDR for enterprise. DPA + Privacy Policy at /legal.
- **Model listing**: `GET /v1/models` returns available models/aliases.

### Cookbook: RAG passage classification (HIGHLY relevant to Nowing)
- Per retrieved RAG passage, send ONE TypeSafe request with 4 Noul questions: is_relevant, contains_answer_evidence, contradicts_query_premise, contains_prompt_injection
- Threshold-based routing: injection>0.70 → exclude; contradicts>0.70 → conflict block; relevance<0.45 → exclude; evidence>0.55 → include
- Real numbers from jev-1.12 (2026-08-27): corpus of 81 Supabase auth docs passages, top-12 cosine retrieval, planted prompt injection scored 0.99 on injection question (excluded), false-premise queries correctly routed to conflict block
- Critical caveat: "Nothing here is a security boundary" — injection filter is a filter, not a guarantee; treat all passages as untrusted regardless

### Cookbook: Entity alignment (relevant to Nowing's entity resolution)
- Score question with 3 levels: different product / related-but-unsure (→ curator) / same product (→ merge)
- 3 Noul questions ride along: name_match, brewery_match, style_match (field-level detail for curator)
- Beer benchmark (Magellan, 450 pairs): 360 → different, 40 → same, 50 → curator. No thresholds to fit — level wording drives behavior.
- Cost scales with # candidate pairs, not corpus size.

### Cookbook: LLM guardrails (relevant to Nowing's chat surface)
- Battery of 4 Noul + 1 Score per message, one request total
- Both input and output screening in one shape
- Two thresholds per hazard: action_threshold (block/route) and review_threshold (human)
- Policy = named set of numbers → same assessment, different decisions by switching policy name
- Severity Score can escalate a review to a block
- Real jailbreak prompts from public collections tested; dosage_request case shows severity-escalation logic

### Nowing-relevant patterns
- **classifying_rag_passages** → directly applicable to Nowing's RAG pipeline (replace/augment embedding-only filtering)
- **entity_alignment** → directly applicable to Nowing's entity resolution/canonical data pipeline (450-pair beer benchmark mirrors Nowing's dedup problem)
- **llm_guardrails** → Nowing's multi-agent chat + voice agent could use input/output screening (jailbreak, harmful content)
- **sde_cascade** (Structured Data Extraction) → scraper field extraction with confidence
- **skill_suggestion** → relevant if Nowing's multi-agent chat needs to route to subagents
- **citation_check** → relevant for research capability (verify claims cite sources correctly)

---

## UPDATE 2 — Skills repo + agent integration + quickstart

### typesafe-ai/skills (1287★)
- **Official Claude Code plugin** (.claude-plugin/marketplace.json + plugin.json)
- SKILL.md for `typesafe-ai` skill — comprehensive guidance for AI coding agents
- Install via `npx skills add typesafe-ai/skills` or Claude Code plugin marketplace
- Skill instructs agents to read live docs at docs.typesafe.ai (llms.txt index), use `.md` suffix for Markdown
- Guidance: pick primitive by answer shape, keep known rules in code, compose not monolith

### Quickstart example (verbatim from docs)
```python
from typesafe_sdk import Choice, Noul, Score, TypeSafeClient

client = TypeSafeClient()
response = client.system_one(
    state=ticket,
    questions={
        "department": Choice(instructions="...", criteria={...}),
        "frustration": Score(instructions="...", criteria=[...]),
        "is_urgent": Noul(instructions="..."),
    },
)
# response.answers["department"].choice → "technical"
# response.answers["frustration"].score → 1.0
# response.answers["is_urgent"].noul → 1.0
```

### Integration notes for Nowing
- SDK: `uv add typesafe-sdk` → `TypeSafeClient` (sync + async), env `TYPESAFE_API_KEY`
- Python-native — fits Nowing's FastAPI backend
- `system-one-adapter-python` lets you swap backend to any OpenAI/Anthropic model with same call shape
- Skills repo suggests: "Put the constants (questions and thresholds) in a single place" — matches Nowing's pattern of centralized config
- Pattern advice: "Agents aren't great at writing questions, so expect to edit collaboratively" — human-in-the-loop for question design

### Jaggedness tracking
- docs.typesafe.ai/model-jaggedness/jev-1.13 — unusual transparency: tracks accuracy shifts as state grows

---

## UPDATE 3 — External verification (TechCrunch, HN)

### TechCrunch (2026-09-18, Tim Fernholz) — independent coverage
- Confirms: Diogo Almeida ex-OpenAI, co-invented RLHF, left 2 years ago
- Jev launched "this week" (week of 2026-09-15); briefly lost ability to serve users due to demand spike
- **Real-world deployments:**
  - **Vercel** (Pranit Sharma, software engineer): replaced OpenAI "ChatGPT Luna 5.6" classifier for command safety review → "5 to 18 times more quickly and with greater accuracy"
  - **Bryo AI** (Nikhil Mudholkar, CTO): tested Jev vs Gemini on business email classification — "Gemini slightly more accurate, but 10-20x more expensive"; values "the only one that hands back a real probability"
- **Armin Ronacher** (CTO of Earendil/Pi): "it delegates the hallucination problem to the user" — user must interpret confidence thresholds; predicts competitors will emerge
- Model routing use case: predicting which workload needs which model — Jev's cost/speed makes real-time sorting possible
- Almeida: architecture "tight-lipped"; suspected to be built on open-weight LLM base; trained exclusively on synthetic data
- Company positioning: "not a lab in the sense of bet on infinite wealth... main product is intelligence"

### HN launch post (1929 pts, 509 comments — high traction)
- Thread: https://news.ycombinator.com/item?id=49717558
- Skeptics: "all claims just sound like marketing terms" (ramon156), want real proof of RLCD + parallel sampling
- Interest: coding use case via AST input; model routing; automation pipelines
- Question about "output tokens free" — how sustainable?
- Some users: "could put this to use today"; "like looking 5 years into the future"
- Demand briefly exceeded capacity at launch

### Open-source alternative already exists
- Qwen-2.5-1B-RLCD on HuggingFace (drinkmoonshine/parallel-constrained-decoding space) — community replication attempt
- kbai-skill on GitHub — "Open-Source Alternative to TypeSafe.ai"
- Category forming: "System One Model" as a model class may outlive any single vendor

### Vercel AI SDK integration guide exists
- vercel.com/kb/guide/typesafe-jev-and-ai-sdk — official Vercel KB on using Jev with AI SDK (2 pts on HN)

---

## UPDATE 4 — Ecosystem & distribution (awesome-jev + market data)

### awesome-jev list (community-curated, 209 verified entries)
- Repo: github.com/MrJev/awesome-jev — verified bar: Jev is central, 10+ stars, runs, numbers carry source
- Ecosystem is ~6 days old at access time — explosion of community projects
- Trending: browser-use/jev-ultrafast (12.5K★, +8.8K week), fast-jev-compaction (5.3K★), NanoJev (1.5K★)
- Categories: agent integrations (MCP/skills), coding agents, guardrails, model routing, CLI, browser/computer use, data/observability, search/KG, finance, robotics
- Community SDKs beyond official Python/JS: Elixir, Java, Go, Rust, .NET, Swift, Ruby
- **Vercel AI Gateway**: `typesafe-ai/jev` via AI SDK 7 experimental evaluate API, with ZDR + no-training options (2026-09-16)
- **OpenRouter**: `typesafe/jev-1.13` listed at TypeSafe's own price (2026-09-18)
- **jev-harness**: TypeScript lib wrapping Jev in policies/confidence gates/shadow mode — relevant pattern for Nowing
- **jevcache**: local decision cache keyed on (model, schema, state) — relevant for cost control

### SDK release cadence
- Python SDK 0.7.0 (2026-09-18): Pydantic replaces msgspec, response_model for typed parsing
- JS SDK 0.6.0 (2026-09-15): Score criteria → ordered array
- Breaking changes happening fast — early days, expect API drift

### Distribution channels
- Direct API (typesafe.ai)
- Vercel AI Gateway (typesafe-ai/jev)
- OpenRouter (typesafe/jev-1.13)
- Official agent skill for Claude Code/Codex (1287★)
- Not on AWS Bedrock / Azure yet (HN commenter request)

### Key ecosystem insights for Nowing
- "jev-harness" pattern (policies + confidence gates + shadow mode) is exactly what Nowing would need for production use
- "jevcache" (deterministic replay cache) solves billing/idempotency concerns
- Multi-provider distribution (Vercel, OpenRouter) reduces vendor lock-in risk — you can route through existing provider relationships
- Ecosystem moving fast: expect API changes, new model versions, community patterns

---

## UPDATE 5 — Jev 1.13 jaggedness (official limitations)

9 documented failure modes, critical for Nowing fit assessment:

| # | Failure mode | Mitigation | Nowing impact |
|---|---|---|---|
| 1 | **Literal reading** — answers what you wrote, not what you meant | State exact conditions; boundary cases in criteria | HIGH — Vietnamese prompts may amplify literalness; question design matters |
| 2 | **Math/numbers** — not a calculator, doesn't count reliably | Keep arithmetic in code | LOW — Nowing already does math in code |
| 3 | **Date/time comparison** — reads dates as text, not ordered quantities | Extract via Choice; compare in code | MEDIUM — date extraction for BDS listings, news articles needs care |
| 4 | **Indirection** — multi-hop reasoning costs accuracy | Direct questions; name state parts explicitly | MEDIUM — avoid "the X of the Y" questions |
| 5 | **Large state w/ irrelevant detail** — accuracy falls | Filter first; send only what question needs | HIGH — Nowing states can be large; must pre-filter |
| 6 | **Adversarial content** — prompt injection can steer | Precise prompts; test edge cases | MEDIUM — RAG passages can carry injections; use as filter not security boundary |
| 7 | **Contradictory instructions/criteria** — confused by misalignment | Align criteria+instruction; clear phrasing | LOW — question design issue, solvable |
| 8 | **Structural invariants** — Noul vs Choice not interchangeable; same question worded differently → different answer | Don't rely on P(A) + P(not A) = 1 across separate questions | HIGH — threshold tuning is per-question-type, not portable |
| 9 | **Generation** — cannot generate text | Use LLM for generation; Jev for selection | N/A — Nowing keeps LLM for generation |

### Key architectural implication for Nowing
- Jev is NOT an LLM replacement — it's a complement. Still need Claude/DeepSeek for generation/synthesis.
- Jev fits as a "decision primitive" layer: classification, routing, scoring, verification.
- Vietnamese language support is uncertain ("English primary, others handled but not equally well") — must test before deploying on Vietnamese content.
- State pre-filtering is critical — can't dump whole documents into state.

---

## UPDATE 6 — Production integration pattern (how-to-build guide)

Full working example from docs.typesafe.ai/concepts/how-to-build-with-system-one:

**Pattern shown:** `triage_ticket(ticket, customer)` — a realistic customer-service triage:
1. Handle deterministic states without calling model (`if ticket["status"] == "closed": return "no_action"`)
2. Build filtered `state` — only fields the questions need
3. Ask 6 questions in ONE call: 1 Choice (topic→billing/orders/account), 4 Nouls (credential phishing, identity mismatch, unexpected reward, refund request, open-order mention), 1 Score (frustration 0-2)
4. Compose in code:
   - `spam_risk = 0.45*credentials + 0.30*identity + 0.25*reward` (weighted composite)
   - `spam_is_uncertain = 0.4 < spam_risk < 0.6` → human review
   - `topic.confidence < 0.75` → human review
   - Route to billing/orders/account with confidence-gated sub-decisions

**Key engineering practices from the example:**
- Deterministic checks BEFORE model call (no Jev needed for `status == "closed"`)
- State filtering: only fields questions need
- Weights in code, not prompts (`0.45*cred + 0.30*identity + 0.25*reward`)
- Confidence thresholds per action type, not global
- Speculative fan-out: ask all questions even if some paths don't need them

### Evals site (evals.typesafe.ai)
- Workflow evals page shows concrete workflows (e.g. expense claim processing)
- Format: "model answers → code decides" split
- Each workflow is a code artifact with typed questions + decision logic
