# DIGEST — dim3+4: extractable patterns + Nowing fit (R3)

Sources: raw jev-ultrafast files (agent.py, model.py, questions.py, snapshot.js, browser.py) + Nowing codebase (jev_router.py, ARCHITECTURE-SPINE.md, INTEGRATION-POINTS.md, browser-control-integration-proposal-2026-08-04.md, dedup modules).

## A. Extracted patterns (claims about jev-ultrafast)

1. **Dynamic indexed action space**: 1 DOM node = 1 index even if multi-op; grouped per-op target maps (CLICK/TYPE_TEXT/SELECT → {index: action}); dropdowns = composite `element:option`; controls = op-level choices; capped ≤250. [model.py action_space, snapshot.js]
2. **Speculative fan-out: op + all target heads in ONE request**: 1 POST /v1/systemone carries operation Choice + 1 `<op>_target` Choice per op; only matching head consumed; unused heads never execute. 2 decisions, 1 RTT. [model.py choose()]
3. **One-request-per-decision-cycle**: op + target share observed state; no serial calls; target questions independent (premise names assumed op). [model.py, design.md]
4. **Strict validation-gated execution**: validate_choice() requires: choice ∈ ids, prob keys match ids, all finite in [0,1], sum to 1 ±0.02, chosen prob = argmax. Failure → ValueError, NO action executed. Retry only 429/529/503; mutations never retried. [model.py]
5. **DONE requires independent outcome verification**: model DONE/BLOCKED only accepted if page fresh(); flight demo separately verifies route/date/results. Model DONE ≠ task success. [agent.py, design.md]
6. **State shaping: visible-only, atomic snapshot, freshness guards**: snapshot.js = 1 IIFE, url/title/visible-text (6000 cap, on-screen text nodes)/≤250 actions in 1 CDP evaluate. Freshness = semantic marker comparison, not mutation counting; scoped context (nearest form/dialog/row ≤6000) permits unrelated visible updates. Geometry re-resolved + occlusion hit-tested before input. [snapshot.js, browser.py]
7. **Text-helper handoff**: TYPE_TEXT dispatches to small OpenAI-compatible LLM (deepseek-chat default, reasoning disabled); output must parse JSON exactly `{"text": ...}` (≤2000 chars, non-empty); cached only if helper input identical, discarded after mutation. [model.py field_text, questions.py]
8. **Consume-once decision + loop guards**: decision nulled before mutation (retry cannot double-click); logged before post-action observation; 3 consecutive no-change non-wait → blocked; MAX_STEPS=60 actions / 120 requests. [agent.py, questions.py]
9. **Model output never becomes selectors/JS**: node IDs code-owned (WeakMap in snapshot.js); executor re-checks visibility/enabled/readonly/occlusion before CDP events; model output = index into observed actions. [browser.py]
10. **Performance posture**: no screenshots in default loop; 1 browser call per snapshot; post-input wait 2 rAF/50ms (200ms combobox cap); focus emulation keeps background tab rendering. 7.07s Flights, 25% faster, 1092→101 protocol calls — 3 repeats, not benchmark. [README, design.md]

## B. Nowing fit (observations, not external claims)

### Already present in Nowing (Epic 39 plan covers):
- **Confidence-gated execution**: `jev_router.py` gates hints at ≥0.6; AD-J4 formalizes `ConfidenceGate`. jev-ultrafast adds *stricter* variant to port: validate chosen prob is argmax + sum≈1 (`fit`: strengthen validate in `DecisionService`, story 39.1).
- **One-request multi-question**: Epic 39 already has "3 Nouls in one call" for guardrails; Jev evaluates questions in parallel. Speculative head (validate only head matching selected op) is a refinement.
- **Question registry / versioned instructions**: AD-J5 maps to jev-ultrafast `questions.py` as named constants. jev-ultrafast is good concrete reference implementation for 39.1.
- **Model pinning + telemetry**: AD-J3/AD-J7 already planned; jev-ultrafast logs model/usage/latency_ms per decision.
- **DONE ≠ verified**: Epic 39 decisions are advisory (routing, filters), not actuator loops. Not needed for 39; relevant if Nowing builds actuation later.

### NEW patterns worth porting to Nowing:
1. **Speculative fan-out with per-head candidate narrowing** (`fit`: entity resolution, story 39.3). Target heads contain only compatible candidates; unused heads never validated. Nowing's two-stage dedup (heuristic narrow → Jev confirm) maps cleanly onto `SpatialWindowedDeduplicator` (`app/services/dedup/spatial_windowed_dedup.py`) and `bds_aggregator/dedupe.py`.
2. **Strict answer-schema validation before any action** (`fit`: AD-J1 `DecisionResult` in `app/services/decision/service.py`). `validate_choice` (argmax + distribution-sum check) stricter than Nowing's current threshold-only check in `jev_router.py`. Cheap to port, prevents malformed/miscalibrated answers.
3. **Consume-once decision semantics** (`fit`: future actuation — sequencer conditions in `app/services/sequencer/service.py`, anti-bot escalation). Null decision before executing so retries can't double-fire.
4. **Semantic freshness guard** (`fit`: `app/services/anti_bot_escalation.py` and scraper re-visit — compare URL + extracted content hash + field values instead of raw HTML diff).

### Usable as browser-automation dependency for Nowing?
- **NO as dependency.** MVP demo (~840 LOC core, no package release beyond uv/pyproject, "two websites do not establish broad reliability"). Hardcoded to `api.typesafe.ai/v1/systemone` with `jev-latest`, attaches to **user's existing Chrome profile** via `browser-harness` daemon (desktop assumption), no shadow-DOM/frames/uploads.
- **vs browser-control proposal (2026-08-04):** proposal chose **Chrome MV3 extension in user's logged-in session** (Manus "My Browser" model) for legal reasons (user IP/session, no server-side scrape). jev-ultrafast's model is local desktop tool, not shippable extension; does not supersede extension plan.
- **However, 3 mechanisms transfer to extension's content-script design**:
  - Indexed element-table snapshot (numbered accessible controls, replaces raw DOM scrape — cheaper than Playwright MCP accessibility tree per proposal §9)
  - Semantic freshness marker for Deal-Radar re-checks
  - Operation+target single-request decision shape (running over Nowing `DecisionService`, not raw typesafe.ai)
- **Verdict**: treat jev-ultrafast as **pattern reference, not dependency**. Port A1/A4/A6/A8/A9 into Nowing's own code; do not vendor the repo.
