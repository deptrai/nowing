# Brief — TypeSafe AI / Jev integration into Nowing

**Decision:** Nowing có nên integrate Jev (TypeSafe AI) làm decision layer, và nếu có thì ở đâu trong stack?

**What we know:**
- TypeSafe AI là AI lab mới; product = Jev, một "System One Model"
- Pitch: LLMs cho chat (RLHF → instruction following); Jev cho decisions inside software (RLCD → typed outputs + calibrated confidence)
- Claims: 193.6x faster, 444.6x cheaper vs LLMs for System One tasks; $42/B input tokens (238x cheaper than Claude Fable 5.1); 0.114s/decision vs 8.566s LLM
- Differentiator vs JSON mode / structured output: model produces calibrated probability, not just schema-valid string
- Early access status — pricing/limits/docs chưa rõ

**Nowing stack context (for integration-fit reasoning, NOT evidence):**
- Python backend: FastAPI, multi-agent chat (LangGraph), voice agent worker (LiveKit + Silero VAD streaming)
- ChainLens research capability (SSE-parsed research agent calls)
- Scraper modules, connector sync, RAG
- Billing/quota per-token
- Existing P0 surfaces: token/credit, auth, provider routing, pricing registration, RAG/connector sync side effects

**Research questions per dimension:** see plan gate.

**Run folder:** `_bmad-output/planning-artifacts/research/technical-typesafe-ai-jev-integration-2026-09-21/`
