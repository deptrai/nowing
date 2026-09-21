# Jev Integration Points — Source Code Verified

**Date:** 2026-09-21 | **Eval baseline:** 96.3% Vietnamese accuracy, 308ms median | **Epic:** 39

Scan method: source code read of `nowing_backend/app/` — all paths verified to exist.

---

## Status: What's already built

| Component | Status | Location |
|-----------|--------|----------|
| `JevRouterMiddleware` | ✅ Exists | `app/agents/chat/multi_agent_chat/main_agent/middleware/jev_router.py` |
| Feature flag `enable_jev_router` | ✅ Wired | `app/agents/chat/multi_agent_chat/shared/feature_flags.py` (default OFF) |
| Middleware stack placement | ✅ Wired | `stack.py` — after `NowingCheckpointedSubAgentMiddleware`, before `mode_budget` |
| `typesafe-sdk` 0.7.0 | ✅ Installed | `pyproject.toml` |
| `TYPESAFE_API_KEY` | ✅ In `.env.local` | |
| Eval harness | ✅ Built | `scripts/jev_eval/` (80 cases, 96.3%) |
| `DecisionService` abstraction | ❌ Not built | Epic 39.1 — needed to unify all backends |
| `QuestionRegistry` | ❌ Not built | Epic 39.1 — questions currently inline in `jev_router.py` |

**Gap:** `jev_router.py` calls `typesafe_sdk` directly — no `DecisionService` port. It works for subagent routing but doesn't scale to other decision types. Epic 39.1 builds the port; `jev_router.py` becomes a caller.

---

## Verified Integration Points

### TIER 1 — Ready now (eval-proven, clear integration point)

#### 1. Subagent routing ✅ (already scaffolded)

- **What:** `JevRouterMiddleware` — injects `<jev_routing_hint>` before LLM call
- **Where:** `app/agents/chat/multi_agent_chat/main_agent/middleware/jev_router.py`
- **Flag:** `NOWING_ENABLE_JEV_ROUTER=true` + `TYPESAFE_API_KEY` set
- **Eval:** 100% accuracy on 20 Vietnamese routing cases
- **Missing:** `DecisionService` port (currently calls SDK directly — Epic 39.1)

#### 2. Content guardrails — RAG passage + user input filter

- **What:** 3 Nouls in one call: `is_relevant`, `contains_prompt_injection`, `contains_sensitive`
- **Where:**
  - `app/services/pii/redact.py` — currently regex-only; Jev adds semantic PII/injection detection
  - `app/retriever/` — RAG relevance check on retrieved chunks before LLM sees them
  - `app/services/connector_service.py` — filter scraped content before indexing
- **Eval:** 100% accuracy on 20 Vietnamese content filter cases (incl. Vietnamese prompt injection)
- **New code needed:** `content_filter` question set in `QuestionRegistry` + hook in retrieval pipeline
- **Story:** 39.4

#### 3. Intent classification — chat message analytics

- **What:** Choice over 8 intents: search/action/question/comparison/recommendation/chitchat/complaint/feedback
- **Where:**
  - `app/services/chat/` — tag every user message with intent for analytics
  - `app/services/auto_reply_agent.py` — `InboundIntentClassifier` currently regex-based (`HOT_INTENT_PATTERNS`); Jev adds semantic classification for nuanced Vietnamese intents
- **Eval:** 95% accuracy on 20 Vietnamese intent cases
- **New code needed:** `intent_classify` question set + hook in chat pipeline
- **Story:** 39.5

### TIER 2 — High value, needs schema design

#### 4. Entity resolution — scraper dedup

- **What:** Score (0=different, 1=uncertain, 2=same) for entity pair matching
- **Where:**
  - `app/services/dedup/spatial_windowed_dedup.py` — currently Jaccard token similarity only; Jev adds semantic matching (handles diacritics, abbreviations, "Sunrise City" vs "Sunset City" trap cases)
  - `app/services/bds_aggregator/dedupe.py` — BĐS listing merge across batdongsan/chotot/muaban; currently uses field-level coalesce, not entity-level matching
  - `app/services/corporate_verification_service.py` — fuzzy match Levenshtein ≥0.85 threshold; Jev replaces with calibrated Score
- **Eval:** 90% accuracy — the 2 misses are borderline uncertain scores (correct behavior for ambiguous pairs)
- **Note:** Currently all rule-based; Jev adds semantic understanding. Not a replacement — use Jev to **verify** candidates that pass heuristic filter (two-stage: cheap heuristic narrows candidates, Jev confirms)
- **Story:** 39.3

#### 5. Lead scoring — composite fit + intent

- **What:** Score for lead quality, Noul for "is this a real lead"
- **Where:**
  - `app/lead_intelligence/scoring/service.py` — `LeadScoringService` computes fit+intent composite
  - `app/lead_intelligence/confidence/gate.py` — `ConfidenceGate` checks schema completeness; Jev adds semantic quality check (is this a real business? is the description coherent?)
  - `app/lead_intelligence/signals/service.py` — `SignalDetectionService` detects funding/hiring/tech signals; Jev can classify whether a scraped page actually represents a buying signal
- **Jev fit:** Score primitive for lead quality; Noul for "is genuine business vs spam/placeholder"
- **Story:** 39.3 extended (or separate epic story)

#### 6. Hybrid LLM tier selection

- **What:** Choice for which LLM tier handles a request
- **Where:**
  - `app/services/hybrid_llm_router.py` — `_select_tier()` currently rule-based on `task_type` + `sensitivity` + quota/health
  - Jev could make this a learned decision: "Which tier should handle this request?" with options `gemini_free`, `local_vllm`, `deepseek_flash`, `deepseek_pro`
- **Jev fit:** Choice primitive over 4 tiers; state = `{task_type, sensitivity, peak, text_preview}`
- **Note:** This is the Armin Ronacher model-routing use case. Currently rule-based and works; Jev adds nuance (e.g., "this looks like sensitive legal content even though tagged public")
- **Story:** New — not in current epic, add as 39.9 or defer

#### 7. Sequence condition evaluation

- **What:** Noul/Score for whether a sequence step should fire
- **Where:**
  - `app/services/sequencer/service.py` — `evaluate_condition_step` currently evaluates DSL conditions
  - Complex conditions like "lead responded positively" or "prospect seems interested" are semantic — Jev Noul can evaluate these against conversation history
- **Jev fit:** Noul per condition ("did the lead express buying intent?", "is this a positive reply?")
- **Story:** New — extends 39.5 or separate

### TIER 3 — Future/deferred

#### 8. Voice agent post-STT decisions

- **What:** Noul for transfer-to-human, Score for caller frustration
- **Where:**
  - `app/services/voice/agent_worker.py` — `on_user_turn_completed` hook; after STT transcript, before LLM response
  - Must fit within LiveKit endpointing-delay budget (~500ms max)
- **Constraint:** Jev is text-only — operates on STT transcript, not audio
- **Story:** 39.6 (deferred)

#### 9. Quality score enhancement

- **What:** Score for auto-mode model selection
- **Where:** `app/services/quality_score.py` — currently formulaic scoring (provider prestige + recency + health)
- **Jev fit:** Jev could score model-to-task fit ("which model is best for this Vietnamese legal question?") — but this is a routing decision at a different layer
- **Priority:** Low — current formulaic approach works; Jev adds marginal value

#### 10. Anti-bot escalation triage

- **What:** Noul for "is this a real block or a false positive"
- **Where:** `app/services/anti_bot_escalation.py` — currently escalates all blocks to admin review
- **Jev fit:** Noul on screenshot metadata/page content to auto-resolve known false positives
- **Priority:** Low — reduces admin burden but not critical path

#### 11. Outlier detection (social copilot)

- **What:** Noul for "is this post a genuine outlier/viral"
- **Where:** `app/services/social_copilot/outlier_detector.py` — currently statistical (engagement ratio ≥3x baseline)
- **Jev fit:** Semantic check on top of statistical — "does this content look viral vs just high-engagement spam"
- **Priority:** Low — statistical approach is already working

---

## Architecture Gaps

| Gap | Current state | Needed |
|-----|---------------|--------|
| `DecisionService` port | `jev_router.py` calls SDK directly | `app/services/decision/service.py` — Protocol + factory |
| `QuestionRegistry` | Questions inline in middleware | `app/services/decision/questions/` — named, versioned sets |
| `ConfidenceGate` | Inline threshold check in `jev_router.py` | `app/services/decision/gate.py` — reusable, per-task thresholds |
| `LLMJsonBackend` | Not implemented | `app/services/decision/backends/llm_json.py` — litellm fallback |
| `MockBackend` | Not implemented | `app/services/decision/backends/mock.py` — deterministic tests |
| Telemetry | `TokenUsage` exists but not wired to Jev | Log `input_tokens`, `model`, `backend` per `decide()` call |
| Cost tracking | No Jev cost tracking | `decision_cost_usd` field or derived from `input_tokens` |

---

## Recommended Build Order

1. **39.1 `DecisionService` + backends + registry** — foundation, unblocks everything
2. **39.2 Subagent routing** — refactor `jev_router.py` to use `DecisionService` (already works, just needs port)
3. **39.4 Content guardrails** — highest accuracy (100%), easiest to verify
4. **39.5 Intent classification** — chat analytics + auto-reply enhancement
5. **39.3 Entity resolution** — two-stage: heuristic candidates → Jev confirm
6. **39.7 Telemetry dashboard** — cost/accuracy monitoring
7. **39.8 Eval CI gate** — regression prevention
8. **39.6 Voice post-STT** — deferred until stable
