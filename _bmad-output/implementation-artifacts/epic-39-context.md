# Epic 39 Context: Typed-Decision Layer (Jev Integration)

<!-- Compiled from planning artifacts. Edit freely. Regenerate with compile-epic-context if planning docs change. -->

## Goal

Integrate TypeSafe Jev as a typed-decision layer — Choice/Score/Noul primitives with calibrated probabilities — behind a backend-agnostic `DecisionService` port, serving subagent routing, entity resolution, content guardrails, and intent classification. Jev is a complement, not an LLM replacement: it cannot generate text, but it makes decision tasks dramatically faster (~300ms vs ~8s LLM router) and cheaper (~$0.00002/decision). Vietnamese suitability is already proven: 96.3% accuracy on an 80-case eval, 308ms median latency, zero API errors.

## Stories

- Story 39.1: `DecisionService` Port + Jev Backend + Question Registry
- Story 39.2: Subagent Routing via Jev Choice (highest impact)
- Story 39.3: Entity Resolution Confidence Scoring
- Story 39.4: Content Guardrails via Jev Noul Battery
- Story 39.5: Intent Classification via Jev Choice
- Story 39.6: Voice Agent Post-STT Semantic Decisions (deferred)
- Story 39.7: Decision Telemetry Dashboard + Cost Tracking
- Story 39.8: Eval Harness CI Integration

## Requirements & Constraints

- All decision calls are gated by flags: `DECISION_ENABLED` master switch plus per-task flags (`DECISION_ROUTING_ENABLED`, `DECISION_FILTER_ENABLED`, `DECISION_ENTITY_ENABLED`, `DECISION_INTENT_ENABLED`, `DECISION_VOICE_ENABLED`).
- Every decision path is advisory/additive: when the flag is off or the backend errors, existing behavior must be preserved (LLM routes normally, heuristic-only dedup runs).
- Confidence-gated action with per-task thresholds, env-tunable (`DECISION_{TASK}_THRESHOLD`): routing 0.6, content filter 0.5, entity match 0.7, intent 0.5.
- Strict structural validation of every answer before it reaches a caller. Choice/Score: chosen id ∈ offered ids, probability keys exactly match ids, all values finite ∈[0,1], distribution sums to 1±0.02, chosen key is the argmax. Noul: finite float ∈[0,1]. Failure raises `InvalidDecisionAnswer` → caller falls back, never acts on malformed/miscalibrated output.
- Latency budget: ~300ms typical, 5s timeout ceiling (`DECISION_TIMEOUT_SECONDS`); voice path must complete within 500ms.
- Every call logs `input_tokens`, `output_tokens`, `latency_ms`, `model`, `backend` to `TokenUsage` for cost telemetry and drift detection.
- Eval baselines (80 Vietnamese cases): routing 100%, content filter 100%, intent 95%, entity 90% — all misses were borderline/defensible. Model upgrades or question-set changes require re-running the eval; CI fails below 90% on any task; routing upgrades need ≥95% confirmation.
- Non-goals: Jev is never in the billing path (money = exact arithmetic), never in the VAD path (stays on Silero, frame-level), has no streaming surface, and never generates text.

## Technical Decisions

- **Ports & adapters.** `DecisionService.decide(state, questions) -> DecisionResult` is the only entry point; callers never import the Jev SDK. Backends: `JevBackend` (typesafe-sdk `AsyncTypeSafeClient`), `LLMJsonBackend` (litellm structured output), `MockBackend` (deterministic tests). `DECISION_BACKEND` selects; fallback chain jev → llm_json on 5xx/529/timeout.
- **Model pinning.** Default `jev-1.13.0` via `DECISION_JEV_MODEL`; the returned model is logged per call. Never use the `jev-latest` alias in production.
- **Question registry.** Named, versioned question sets live under `app/services/decision/questions/`, named `{domain}_{question}`. Instructions are written in English; `state` carries natural Vietnamese text — eval confirmed this works, do not translate state.
- **Module layout:** `app/services/decision/{service.py, backends/{jev,llm_json,mock}.py, questions/, gate.py, validation.py}`.
- **Parallel questions.** All questions in one `decide()` call evaluate in parallel server-side — batch related checks (e.g., the 3-Noul content filter: `is_relevant`, `contains_prompt_injection`, `contains_sensitive`) into a single request.
- **Subagent routing** is a pre-LLM hint: Choice over 16 subagent options + `none_needed`; confidence ≥0.6 injects a system hint into the LLM context (biases, does not force); below threshold no hint is injected. Routing decisions are logged for offline accuracy tracking.
- **Entity dedup is two-stage** (speculative fan-out pattern): stage 1 heuristic (spatial/Jaccard dedup, phone/address/image union-find) narrows N entities → K candidate pairs (cap K≤250); stage 2 issues ONE `decide()` call per anchor carrying a `match_decision` Choice over only the heuristic-surviving candidate ids + `no_match` — Jev confirms survivors, never re-scores rejected pairs. ~1 call per anchor regardless of K. Score actions: ≥1.5 auto-merge, 0.5–1.5 curator review queue, <0.5 keep separate. The Jev stage is advisory — heuristic-only dedup still runs when disabled.
- **Consume-once semantics** are a mandatory invariant whenever a decision triggers a side-effect (mark/null the decision before executing so retries can't double-fire). Current epic paths are advisory/idempotent; this binds future actuation use.
- **Semantic freshness guard:** decide "is this observation still valid" by comparing semantic state (URL + extracted-content hash + field values), never raw HTML diffs.
- **Voice decisions** operate on STT transcripts only (Jev is text-only): `should_respond` (Noul), `caller_frustration` (Score 0–3), `transfer_to_human` (Noul ≥0.7 → escalate).
- **External API:** `POST https://api.typesafe.ai/v1/systemone`, `TYPESAFE_API_KEY` bearer auth, 64K context per request, SDK auto-retries 429/529. $42/B input tokens, output free.
- **`jev-ultrafast` is a pattern reference only** — do not vendor it as a dependency. Port its `choose()`/`validate_choice()`/question-registry patterns; keep MIT attribution if adapted.

## Cross-Story Dependencies

- Story 39.1 (port, validation, gate, registry, mock, telemetry logging) is the foundation — every other story depends on it.
- Stories 39.2–39.6 are independent consumers and can proceed in parallel after 39.1; 39.6 is deferred until 39.2–39.4 are stable.
- Story 39.7 depends on the TokenUsage logging from 39.1 plus live decision traffic from consumer stories.
- Story 39.8 builds on the existing `scripts/jev_eval/` harness (already built, baseline 96.3%) and gates model/question-set changes for all other stories.
- External systems touched: multi-agent chat middleware (routing hint), entity-resolution/scraper dedup pipeline, RAG/chat guardrail path, voice agent (LiveKit post-STT), TokenUsage telemetry.
