---
stepsCompleted: [1, 2, 3, 4, 5, 6]
lastStep: 6
inputDocuments: []
workflowType: 'research'
lastStep: 1
research_type: 'technical'
research_topic: 'deepseek-harness integration into Nowing/ChainLens DSH architecture'
research_goals: 'Clarify whether DSH in Nowing/ChainLens architecture refers to github.com/deepseek-ai/deepseek-harness, find existing references in architecture/story backlog, and identify integration value/risks.'
user_name: 'Luisphan'
date: '2026-08-19'
web_research_enabled: true
source_verification: true
---

# Research Report: technical

**Date:** 2026-08-19
**Author:** Luisphan
**Research Type:** technical

---

## Research Overview

This report investigates whether `github.com/deepseek-ai/deepseek-harness` (DSH) is already integrated, planned, or merely referenced conceptually within the Nowing + ChainLens architecture. It combines live web research of the DSH repository and documentation with a code-level audit of Nowing's architecture spine, sprint change proposal, story backlog, and implementation artifacts.

**Key finding:** The unified architecture repeatedly uses the name "DeepSeek Harness" and the abbreviation `dsh` for the sidecar orchestrator, and it adopts agent-team patterns (Supervisor-Specialist, Producer-Reviewer, fan-out/fan-in) associated with harness-style agent runtimes. However, the actual `dsh-worker` implementation in Story 26.2 is a custom Python sidecar built inside `nowing_backend` using Redis Streams, FastAPI capabilities, and existing Nowing auth. There is no dependency on the Node.js/Cordis `deepseek-harness` repository in any `package.json`, `pyproject.toml`, `requirements.txt`, or `Dockerfile`.

The full analysis below covers technology stack, integration patterns, architectural patterns, implementation options, risk assessment, and a recommended roadmap for resolving the ambiguity between architecture vocabulary and working code.

## Technical Research Scope Confirmation

**Research Topic:** deepseek-harness integration into Nowing/ChainLens DSH architecture
**Research Goals:** Clarify whether DSH in Nowing/ChainLens architecture refers to github.com/deepseek-ai/deepseek-harness, find existing references in architecture/story backlog, and identify integration value/risks.

**Technical Research Scope:**

- Architecture Analysis - design patterns, frameworks, system architecture
- Implementation Approaches - development methodologies, coding patterns
- Technology Stack - languages, frameworks, tools, platforms
- Integration Patterns - APIs, protocols, interoperability
- Performance Considerations - scalability, optimization, patterns

**Research Methodology:**

- Current web data with rigorous source verification
- Multi-source validation for critical technical claims
- Confidence level framework for uncertain information
- Comprehensive technical coverage with architecture-specific insights

**Scope Confirmed:** 2026-08-19

---

<!-- Content will be appended sequentially through research workflow steps -->

## Technology Stack Analysis

### Programming Languages

_DeepSeek Harness_ is a **TypeScript / Node.js** project. The source tree uses `pnpm` workspaces, with packages under `packages/` and apps under `apps/`. It ships a CLI `dsh` and a web UI. Core runtime plugins are written in TypeScript and composed through the **Cordis** plugin kernel.

_Nowing / ChainLens_ are **Python (FastAPI/SQLAlchemy)** and **TypeScript (Next.js/NestJS)**. The `dsh-worker` sidecar described in Story 26.2 is implemented inside `nowing_backend`, not as an external Node process.

**Implication:** If Nowing were to integrate the actual `deepseek-harness` repo, it would introduce a **second runtime** (Node.js + Cordis) alongside the existing Python monolith and NestJS/Next.js stack, or it would need a Python bridge.

_Source:_ https://github.com/deepseek-ai/deepseek-harness (repo structure), https://deepseek.com/harness/en/ (quick start `npx @deepseek-ai/dsh web`).

### Development Frameworks and Libraries

_DeepSeek Harness_ is built on **Cordis** (`github.com/cordiverse/cordis`), a plugin-oriented framework where everything (model adapter, tool registry, session log, agent loop, UI) is a replaceable plugin. It supports multiple runtime modes: Standard, Code, Minimal, and Creator. The architecture document explicitly states: _"There is no privileged core to patch: you extend dsh by mounting a plugin beside the others"_.

_Nowing_ already has its own **capability registry** (`app/capabilities/core/store.py`), **tool registry** (`main_agent/tools/registry.py`), **async runner** (`app/capabilities/core/async_runner.py`), and **Redis Streams** worker pattern (`app/tasks/social_stream_worker.py`). These provide equivalent primitives without Cordis.

**Implication:** Cordis is a powerful composability layer, but Nowing already has working plugin/capability abstractions. Adopting Cordis would be a **rewrite or parallel runtime**, not a drop-in library.

_Source:_ https://github.com/deepseek-ai/deepseek-harness/blob/master/docs/architecture.md

### Database and Storage Technologies

_DeepSeek Harness_ uses an **append-only `SessionEvent` log** and an in-memory store (`core/session`). Persistence is plugin-based, so storage can be swapped.

_Nowing_ uses **PostgreSQL 16 + pgvector** as the single source of truth, plus **Redis 7** for streams/cache. Story 26.2 specifies `dsh_missions` table persistence and `nowing:dsh:tasks` Redis stream.

**Implication:** The two persistence models differ. DeepSeek Harness's session log is not a relational workspace/lead model. Integration would require an adapter to sync session events into Nowing's PostgreSQL/Zero-Cache pipeline.

### Development Tools and Platforms

_DeepSeek Harness_ ships via `npx @deepseek-ai/dsh web` or cloned from source with `pnpm install && pnpm run build`. It is MIT licensed and in **developer preview** (created 2026-08-13 per GitHub metadata).

_Nowing_ is a brownfield monorepo with `uv` (Python), `pnpm` (web/ChainLens), Docker Compose, and Dokploy for deployment.

### Cloud Infrastructure and Deployment

_DeepSeek Harness_ is designed to run as a standalone agent harness, either headless or with a web UI. It does not define a sidecar/k8s deployment contract.

_Nowing's_ architecture (AD-102) defines `dsh-worker` as a **sidecar container** derived from the same `nowing_backend` image, consuming Redis Streams and calling authenticated REST endpoints. This is a narrower, deployment-specific pattern.

### Technology Adoption Trends

_DeepSeek Harness_ is new (developer preview, 166k stars in the search result, likely inflated/simulated). The dominant design trend is **modular agent runtime via plugins**; other players include LangGraph, AutoGen, and OpenAI's Swarm.

_Nowing_ is trending toward **reactive, stateless workers** with PostgreSQL/Zero-Cache as the single source of truth, rather than adopting an external agent harness.

### Cross-Technology Analysis

- **Name collision:** `dsh` is the CLI abbreviation of DeepSeek Harness and also the internal name of Nowing's sidecar worker. This is the source of confusion.
- **Semantic difference:**
  - `github.com/deepseek-ai/deepseek-harness` = general-purpose agent harness (Node/Cordis).
  - Nowing `dsh-worker` = domain-specific sidecar for long lead-research missions (Python/Redis Streams).
- **Overlap:** Both handle long-running agent tasks, tool calls, subagent delegation, and session resumption. Nowing could conceptually use DeepSeek Harness as the runtime for its `dsh-worker`, but doing so would require major architectural churn.

### Quality Assessment

- **Confidence — high:** DeepSeek Harness is a real project with public docs and repo.
- **Confidence — high:** Nowing's `dsh-worker` is an internal Python sidecar with no dependency on the Node repo.
- **Confidence — medium:** The architecture doc uses the word "Harness" and "dsh" without an explicit GitHub URL, leaving room for intentional naming or future adoption.

---

## Integration Patterns Analysis

### API Design Patterns

_DeepSeek Harness_ exposes its own **plugin API and tool registry** through Cordis. Tools are registered in `ctx.tools` and the model calls them via function-calling or Code Mode. It has an `apiProxy` for client-host communication and supports OpenAPI/REST tool plugins (e.g., `dsh-openapi`).

_Nowing_ exposes **REST endpoints** and **MCP tools**.
- REST: `POST /api/v1/workspaces/:workspace_id/leads/batch-ingest`, `POST /api/v1/workspaces/:workspace_id/scrapers/chainlens/research?mode=async`.
- MCP: `nowing_mcp` server has `batch_ingest_leads` (AD-109 says MCP tool is **out of scope** for Epic 26; REST is canonical).

**Observed integration design in architecture:**
- `dsh-worker` sidecar is supposed to call Nowing through **authenticated REST** and optionally **FastMCP Gateway (`/mcp/v1/tools/ingest_lead`)** (per `.memlog.md` AD-102).
- However, `ARCHITECTURE-SPINE.md` AD-102 Rule 2 says the sidecar interacts through `POST /api/v1/workspaces/:workspace_id/leads/batch-ingest` or **an equivalent MCP tool**.
- This is a **two-option contract**: REST now, MCP later.

**DeepSeek Harness's own MCP client** (`@deepseek-ai/dsh-mcp-client`) can connect to an MCP server via stdio or streamable HTTP and register its tools under `mcp__<serverName>__<toolName>`. This means if Nowing's MCP server is exposed, DeepSeek Harness could consume it as a tool source.

_Source:_ https://deepseekdocs.com/en/docs/features/mcp, https://github.com/deepseek-ai/deepseek-harness/blob/master/packages/mcp/mcp-client/src/index.ts

### Communication Protocols

_Nowing dsh-worker_ uses **Redis Streams** (`nowing:dsh:tasks`) for mission dispatch, `XAUTOCLAIM`/`XACK` for delivery semantics, and `nowing:dsh:dlq` for dead-letter. Heartbeats use a Redis lock (`nowing:dsh:lock:{mission_id}`) with TTL.

_DeepSeek Harness_ uses **Cordis typed events** and an append-only `SessionEvent` log. It does not natively use Redis Streams; persistence is plugin-based.

**Implication:** Adopting DeepSeek Harness as the actual sidecar runtime would mean replacing or wrapping Nowing's Redis Streams dispatch with Cordis events / sessions. This is a **protocol mismatch**.

### Data Formats and Standards

_Nowing_ uses **JSON** for REST payloads, **JSONB** in PostgreSQL, and **SSE** for ChainLens/Nowing streaming.

_DeepSeek Harness_ uses **JSON** for tool schemas and session events, with a `ToolSchema` DSL and lossless-JSON tool outputs. It supports **Code Mode** where the model emits TypeScript to orchestrate tools.

**Implication:** DeepSeek Harness tool outputs are lossless JSON; Nowing's lead/ingest payloads are Pydantic models. Integration would need a schema adapter and PII filtering at the boundary.

### System Interoperability Approaches

There are **three possible integration shapes**:

1. **Replace internal `dsh-worker` with DeepSeek Harness runtime**
   - Run `dsh` headless or as a sidecar.
   - Write a custom Cordis plugin for Nowing tools (`batch_ingest_leads`, `chainlens.research`, `portal.scrape`).
   - Replace Redis Streams with Cordis events, or bridge Redis Streams into a `dsh` plugin.
   - **Risk:** highest churn; AD-102/AD-106 are built around Python/Redis, not Node/Cordis.

2. **Use DeepSeek Harness as an optional tool-calling layer inside Nowing**
   - Keep Python `dsh-worker` but embed/invoke `dsh` CLI for subagent orchestration.
   - `dsh` calls Nowing REST/MCP for actions.
   - **Risk:** two runtimes, process spawning overhead, credential/secret sharing.

3. **Borrow patterns only; keep internal implementation**
   - Use "Supervisor-Specialist" and "Producer-Reviewer" patterns from Harness/AutoGen literature.
   - Keep Python stack, Redis Streams, and existing capability registry.
   - This is what `ARCHITECTURE-SPINE.md` AD-106 describes: _"Harness Hierarchical Delegation & Specialist Team Pattern"_ — a **design pattern**, not a dependency.

### Microservices Integration Patterns

- **API Gateway:** Nowing FastAPI is the gateway. ChainLens is a stateless engine. `dsh-worker` is a sidecar.
- **Circuit Breaker:** `HybridLLMRouter` in Nowing already does tiered fallback (Gemini → local vLLM → DeepSeek Cloud).
- **Saga / Distributed transactions:** Mission execution in `dsh-worker` with checkpoint resumption is a Saga pattern. DeepSeek Harness's append-only session log could serve as saga audit log.

### Event-Driven Integration

- **Nowing:** Redis Streams + PostgreSQL WAL/Zero-Cache.
- **DeepSeek Harness:** Cordis events + `SessionEvent` log.

If integrated, the **session log** could become the source of truth for mission replay and audit, while PostgreSQL remains source of truth for leads/chunks.

### Integration Security Patterns

- **DeepSeek Harness MCP client** supports `headers` for auth tokens and `env` for secrets, scrubbed from model context.
- **Nowing** uses `PAT` (Personal Access Token) + `X-Dsh-Worker-Secret` for sidecar auth.
- **PII boundary:** DeepSeek Harness must not see PII. Nowing already masks `0908 *** 456` and encrypts in `verified_contacts`.

### Evidence from Architecture & Backlog

- `.memlog.md` line 11: `AD-102: DeepSeek Harness (dsh) is deployed as a decoupled Sidecar container (dsh-worker) communicating with Nowing Core via Redis Streams (nowing:dsh:tasks) and FastMCP Gateway (/mcp/v1/tools/ingest_lead).`
- `ARCHITECTURE-SPINE.md` AD-102: sidecar communicates via REST or equivalent MCP, no direct DB.
- `Story 26.2`: `dsh-worker` sidecar is implemented in Python inside `nowing_backend`, consuming Redis Streams. No Node/Cordis dependency.
- `sprint-change-proposal-2026-08-17-unified-nowing-chainlens-dsh.md`: uses DeepSeek models + "mẫu thiết kế Agent Team từ Harness" (Agent Team patterns from Harness), not the repo itself.

### Key Finding: Name vs. Dependency

- **Architecture naming uses "DeepSeek Harness" and `dsh`** as the **conceptual sidecar/orchestrator**.
- **Actual code in Story 26.2 is a custom Python sidecar** named `dsh-worker`, not importing `deepseek-harness`.
- There is a **gap between architecture vocabulary and implementation**: the architecture sounds like an adoption of DeepSeek Harness, but the backlog implements an in-house equivalent.
- The `.memlog` reference to `FastMCP Gateway (/mcp/v1/tools/ingest_lead)` suggests a future convergence point, but no code exists for that path.

---

## Architectural Patterns and Design

### System Architecture Patterns

**DeepSeek Harness** is a **plugin-oriented, context-based architecture**. It uses Cordis, where every capability (model, tools, sessions, UI, agent loop) is a plugin that registers services and typed events in a shared `Context`. This is a form of **modular monolith with reversible effects**: plugins load/unload dynamically, and there is no privileged core.

**Nowing/ChainLens** is a **layered modular monolith + stateless sidecars**: FastAPI backend, PostgreSQL 16 + pgvector, Zero-Cache CDC, Redis Streams, and a `dsh-worker` sidecar. AD-102 explicitly carves out an exception to AD-1 (monolith) for the sidecar, but the sidecar is described as a Python worker in Story 26.2.

**Cross-comparison:**

| Dimension | DeepSeek Harness (dsh) | Nowing dsh-worker (current) |
|---|---|---|
| Runtime | Node.js + Cordis | Python + asyncio |
| Plugin model | Cordis `Service` / effects | FastAPI capability registry / agent tool registry |
| State log | Append-only `SessionEvent` | PostgreSQL `dsh_missions` + Redis Streams |
| Tool dispatch | `ctx.tools` / Code Mode | `app/capabilities/core/execute_with_context` |
| Session replay | Built-in trajectory viewer | Not yet; checkpoint JSONB in mission row |
| Sidecar deployment | Headless/web via `dsh` CLI | Custom Docker image `SERVICE_ROLE=dsh` |

**Implication:** The two are architecturally analogous (plugin/capability registries, event-driven, reversible effects/circuit breakers), but not implementation-compatible without a bridge.

_Source:_ https://deepseek-harness.github.io/deepseek-harness/en/reference/cordis-primer, https://deepseek-harness.github.io/deepseek-harness/en/develop/framework/

### Design Principles and Best Practices

**DeepSeek Harness design principles (from Cordis):**
- **Spatiotemporal composability**: plugins compose in space (context) and time (lifecycle).
- **Reversible effects**: all registrations are effects that unwind on unload.
- **Dependency-driven loading**: `inject` declares service dependencies; load order is automatic.
- **No privileged core**: extend by mounting plugins, not patching core.

**Nowing design principles (from Architecture Spine):**
- **Single source of truth (PostgreSQL 16 + pgvector)**.
- **Stateless external engines (ChainLens)**.
- **Monolith with approved sidecar exception (AD-102)**.
- **Hermetic testability & $0 API cost (AD-107)**.

**Friction:**
DeepSeek Harness's "no privileged core" encourages replacing persistence via plugin. Nowing's AD-2 and AD-101 make PostgreSQL the privileged single source of truth. Reconciling these would require a Nowing-specific `dsh` persistence plugin that writes to PostgreSQL/Redis, not the default in-memory/session log.

### Scalability and Performance Patterns

**DeepSeek Harness:**
- Plugin overhead is low; model calls dominate.
- `ctx.sessions` is in-memory; persistence plugin is needed for durability.
- No built-in horizontal scaling contract; one `dsh` process per profile.

**Nowing dsh-worker:**
- Redis Streams allow multiple worker replicas to consume from `nowing:dsh:tasks`.
- `XAUTOCLAIM` + per-mission Redis lock handles failover and split-brain.
- PostgreSQL is the bottleneck; bulk upsert sorted by `value_hmac` prevents deadlocks.

**Implication:** Replacing the Python `dsh-worker` with DeepSeek Harness would lose the Redis Streams multi-replica pattern unless wrapped in a `dsh` plugin or a separate adapter.

### Integration and Communication Patterns

**Nowing uses:**
- REST (FastAPI routes) for external/sidecar calls.
- MCP (stateless HTTP) for client integrations.
- Redis Streams for background job dispatch.
- PostgreSQL WAL → Zero-Cache for real-time UI sync.

**DeepSeek Harness uses:**
- Cordis events for in-process communication.
- `apiProxy` for host/client HTTP.
- MCP client plugin to connect to external MCP servers.
- OpenAPI plugin to consume REST APIs as tools.

**The .memlog AD-102 states:** `DeepSeek Harness (dsh) is deployed as a decoupled Sidecar container (dsh-worker) communicating with Nowing Core via Redis Streams (nowing:dsh:tasks) and FastMCP Gateway (/mcp/v1/tools/ingest_lead).`

This is the **only explicit architecture-level statement** linking `dsh` to DeepSeek Harness. It is not reflected in the implementation stories. This suggests the architecture team **named/conceptualized** the sidecar as DeepSeek Harness but the engineering backlog **built an in-house equivalent** using existing Python/Redis/FastMCP infrastructure.

### Security Architecture Patterns

- **DeepSeek Harness**: secrets via `env`/`credentials`, scrubbed host environment, tool-call timeouts, sandbox for code execution.
- **Nowing**: PAT + `X-Dsh-Worker-Secret` (constant-time compare), workspace-scoped RBAC, PII encryption, blind HMAC deduplication.

If integrated, the `dsh` sidecar would need to store/rotate a PAT and `DSH_WORKER_SECRET` inside the Node process, adding a new secret surface.

---

## Implementation Approaches and Technology Adoption

### Technology Adoption Strategies

Given the findings above, there are **four adoption strategies** for `deepseek-harness` in Nowing:

1. **Borrow patterns only (recommended for current state)**
   - Keep the Python `dsh-worker` and existing capability registry.
   - Apply Harness/Cordis design ideas (reversible effects, dependency-driven loading, typed events) where they fit.
   - Update architecture docs to clarify that `DSH` is an **in-house sidecar inspired by** DeepSeek Harness patterns, not the repo.
   - **Effort:** documentation + minor refactor. **Risk:** low.

2. **Wrap `dsh` headless as a one-off task runner**
   - Use `dsh --profile headless "mission task"` inside the existing `dsh-worker` Python container via `subprocess`.
   - Pass input as a file/JSON, capture stdout/stderr.
   - **Pros:** leverages DeepSeek's agent loop, tool use, and session replay without replacing Redis Streams.
   - **Cons:** process spawn overhead, two runtimes, secret sharing, no Redis Streams integration out of the box.
   - **Effort:** medium. **Risk:** medium.

3. **Replace `dsh-worker` with a Node/Cordis sidecar**
   - Build a custom `dsh` profile/bundle for Nowing: register tools for `batch_ingest_leads`, `chainlens.research`, `portal.scrape`.
   - Implement a persistence plugin writing `SessionEvent` to PostgreSQL (`dsh_missions` table) and a Redis Stream consumer plugin for dispatch.
   - **Pros:** fully uses DeepSeek Harness architecture; session replay, tool sandbox, subagent orchestration.
   - **Cons:** major rewrite; new runtime; new deployment; PII/secret boundary; team must learn Cordis.
   - **Effort:** high (2–4 sprints). **Risk:** high.

4. **Use DeepSeek Harness for local/self-host user experience only**
   - Ship `dsh` as an optional local IDE/agent experience for self-host users, connected to Nowing MCP server.
   - Keep the cloud sidecar as Python.
   - **Pros:** PLG-friendly; uses the right tool for the right audience.
   - **Cons:** splits the codebase; two sidecars to maintain.
   - **Effort:** medium. **Risk:** medium.

### Development Workflows and Tooling

**If adopting DeepSeek Harness:**
- Build pipeline needs Node.js 22.19+, `pnpm`, and TypeScript compilation.
- Add `dsh` profile/bundle packaging to CI.
- Profile/bundle versions must be pinned to avoid Cordis peer-dependency drift.
- The `dsh plugin` CLI manages plugins via pnpm; this adds a new package-management surface.

**Current Nowing workflow:**
- `uv` for Python, `pnpm` for web/ChainLens, Docker Compose for local, Dokploy for prod.
- Adding a Node sidecar means another Dockerfile, another image, and potentially a new Dokploy app.

### Testing and Quality Assurance

- **DeepSeek Harness** has its own test harness for plugins (`pnpm run verify-config-catalog`, doc-sync).
- **Nowing** has `pytest`, `nowing_evals`, Playwright, and hermetic gates.
- Integration would require:
  - Unit tests for Cordis plugins.
  - End-to-end tests for sidecar → Nowing REST/MCP.
  - Hermetic cassettes for `dsh` tool calls (if using headless runner).

### Deployment and Operations Practices

- **Headless bundle** is the best fit for a sidecar: `dsh --profile headless "task"` exits after one turn.
- For long missions (1–8h), headless is not enough; would need a custom long-running bundle or keep the session alive.
- **Persistence plugin** must be durable; PostgreSQL is the natural choice (there is already a `dsh-session-persistence` abstract service and a community `session-teleport` plugin using PostgreSQL).
- **Monitoring:** Cordis plugins can emit telemetry; Nowing's observability stack (OpenTelemetry spans, `TokenUsage`, `BillingEvent`) would need to ingest `dsh` events.

### Team Organization and Skills

- **Nowing team:** Python/FastAPI, SQLAlchemy, Next.js, Zero-Cache.
- **DeepSeek Harness team:** TypeScript/Cordis, plugin authoring, LLM tool-calling.
- Adoption requires at least one engineer to own Cordis plugin lifecycle and `dsh` profile/bundle maintenance.

### Cost Optimization and Resource Management

- **DeepSeek Harness headless** itself does not charge; the cost is the underlying LLM calls (DeepSeek Cloud, Gemini, local vLLM).
- **Local vLLM 14B AWQ** is the cost target in Nowing architecture (AD-103); DeepSeek Harness can use local adapters.
- **Risk of cost bleed:** DeepSeek Harness's tool use can be verbose; must meter `TokenUsage` and apply `cost_micros` per tool/model call.

### Risk Assessment and Mitigation

| Risk | Severity | Mitigation |
|---|---|---|
| `dsh` in preview; APIs may break | High | Pin versions, vendor fork if needed, stay on internal sidecar as fallback. |
| Two runtimes (Node + Python) | High | Single Docker image with both? Or separate sidecar? Increase ops complexity. |
| PII leakage into `dsh` session log | High | Filter PII before it reaches `dsh`; keep `verified_contacts` in PostgreSQL. |
| Redis Streams replacement churn | Medium | Wrap Cordis events around Redis Streams, or keep Python worker. |
| Team skill gap | Medium | Assign owner, document Cordis primer, prototype one tool. |
| Vendor lock-in to DeepSeek | Medium | Use local vLLM + model adapter abstraction in `HybridLLMRouter`. |

---

## Technical Research Recommendations

### Implementation Roadmap

**Option A — Clarify & Continue In-House (short term, 1–2 weeks):**
1. Update architecture docs to say `DSH` = "Deep lead-research Sidecar with Harness-inspired patterns" (or rename to avoid confusion with `deepseek-harness` repo).
2. Remove/correct `.memlog` line that says `DeepSeek Harness (dsh) is deployed...` unless there is a real plan to import the repo.
3. Continue Story 26.2 Python sidecar.

**Option B — Pilot `dsh` Headless (medium term, 4–6 weeks):**
1. Prototype one mission type (e.g., `noop` or `lead enrichment`) running through `dsh --profile headless`.
2. Build a Nowing tool plugin for `batch_ingest_leads` (via REST or MCP).
3. Compare cost/latency/reliability against Python sidecar.

**Option C — Full Cordis Sidecar (long term, 2–4 months):**
1. Design a `dsh` profile/bundle for Nowing.
2. Implement PostgreSQL persistence plugin for `dsh_missions`/`SessionEvent`.
3. Implement Redis Stream consumer plugin or replace dispatch.
4. Run A/B pilot; deprecate Python sidecar if it wins.

### Technology Stack Recommendations

- **If integrating:** Node.js 22.19+, `pnpm`, `@deepseek-ai/dsh-headless`, custom Cordis plugins, PostgreSQL persistence.
- **If not integrating:** Python `dsh-worker`, Redis Streams, existing FastAPI capabilities.
- **Either way:** keep `HybridLLMRouter` as the inference abstraction; model choice (DeepSeek/Gemini/local) is orthogonal to sidecar runtime.

### Skill Development Requirements

- Cordis plugin lifecycle and `ctx` patterns.
- `dsh` profile/bundle packaging.
- Tool schema design and guarded execution pipeline.
- PII-safe tool outputs.

### Success Metrics and KPIs

- **If piloting:**
  - Mission success rate (vs Python baseline).
  - Cost per lead (including `dsh` overhead).
  - Time-to-completion p50/p95.
  - Tool-call error rate and PII leakage incidents (must be 0).
- **If not integrating:**
  - Architecture doc clarity (no name collision).
  - Python sidecar passes hermetic gates and chaos tests.

### Data Architecture Patterns

- **DeepSeek Harness**: `SessionEvent` log (append-only, possibly JSONL or in-memory) is the core audit artifact.
- **Nowing**: Relational `dsh_missions` table + `checkpoint` JSONB + Zero-Cache publication of PII-safe columns.

**Convergence possibility:**
DeepSeek Harness's session log could become the **audit/replay layer** for `dsh-worker` while PostgreSQL remains the source of truth for leads/chunks. This would require a `dsh` persistence plugin mapping `SessionEvent` → `dsh_missions` rows.

### Deployment and Operations Architecture

- **Nowing dsh-worker**: Docker Compose service, `tini` PID 1, 60s timeout, healthcheck, WAL limits.
- **DeepSeek Harness**: `npx @deepseek-ai/dsh web` or source build, headless `dsh` CLI, no native sidecar contract.

**Deployment option if adopting DeepSeek Harness:**
- Run `dsh-headless` as a container with a custom profile/bundle for Nowing.
- Mount a `cordis.patch.yml` registering Nowing tools (REST/MCP) and persistence plugin.
- Sidecar calls Nowing REST and writes mission state back to PostgreSQL.

### Verdict: Is DeepSeek Harness Actually Integrated?

**No — not as a code dependency.**

Evidence:
- No `package.json`, `pyproject.toml`, `requirements.txt`, or `Dockerfile` in Nowing/ChainLens references `deepseek-harness`, `@deepseek-ai/dsh`, or Cordis.
- Story 26.2 (`dsh-worker Sidecar Container, Redis Streams & Task Resumption`) is implemented entirely in Python inside `nowing_backend`.
- The `.memlog` and `ARCHITECTURE-SPINE.md` use the **name** `DeepSeek Harness (dsh)` and `Agent Team patterns from Harness`, but do not mandate importing the repository.
- The SCP `sprint-change-proposal-2026-08-17-unified-nowing-chainlens-dsh.md` says: *"tận dụng mô hình suy luận sâu DeepSeek-R1 với chi phí siêu rẻ và các mẫu thiết kế Agent Team từ Harness"* — it leverages **DeepSeek-R1 models** and **Agent Team design patterns**, not the DeepSeek Harness codebase.

**Confidence — high** that the repo is not currently integrated. **Confidence — medium** that the architecture intends to align conceptually with DeepSeek Harness or may adopt it later.

---

## Research Synthesis

### Executive Summary

The question at the heart of this research was whether the "DSH" / "Harness" component in the unified Nowing + ChainLens architecture refers to the open-source repository `github.com/deepseek-ai/deepseek-harness`. After reviewing live web sources, the architecture spine, the sprint change proposal, `.memlog` decisions, and the working story backlog, the answer is **conceptually yes, but not as a code dependency today**.

**Key findings:**

- `github.com/deepseek-ai/deepseek-harness` is a real, MIT-licensed, TypeScript/Node.js agent harness built on the Cordis plugin framework. It is currently in developer preview.
- Nowing's architecture uses the name `DeepSeek Harness (dsh)` and describes a sidecar orchestrator that applies "Harness Hierarchical Delegation" and "Supervisor-Specialist" patterns.
- The `.memlog` for the architecture explicitly states: `DeepSeek Harness (dsh) is deployed as a decoupled Sidecar container (dsh-worker)` communicating via Redis Streams and FastMCP.
- However, the actual implementation in **Story 26.2** is a custom Python sidecar inside `nowing_backend` with no Node.js, Cordis, or `deepseek-harness` package dependency.
- There is **no evidence in code or dependency manifests** that the `deepseek-harness` repo has been imported, installed, or wrapped.

**Strategic implication:** The architecture is using the name and design vocabulary of DeepSeek Harness, but the engineering backlog has built an in-house equivalent. This creates ambiguity that should be resolved before closed beta, either by clarifying the documentation or by making an explicit decision to adopt or reject the open-source project.

### Table of Contents

1. Research Overview
2. Technical Research Scope Confirmation
3. Technology Stack Analysis
4. Integration Patterns Analysis
5. Architectural Patterns and Design
6. Implementation Approaches and Technology Adoption
7. Technical Research Recommendations
8. Research Synthesis

### Strategic Technical Recommendations

1. **Short term (1–2 weeks): clarify architecture vocabulary.** Update `ARCHITECTURE-SPINE.md`, `.memlog.md`, and sprint change proposal to state explicitly whether `dsh` is the internal Python sidecar, a planned DeepSeek Harness integration, or an inspiration. Rename if needed to prevent confusion.

2. **Medium term (4–6 weeks): run a bounded pilot.** If the team wants to evaluate DeepSeek Harness, wrap `dsh --profile headless` for a single non-PII mission type and compare cost, latency, and reliability against the Python sidecar.

3. **Long term (2–4 months): decide adopt vs. in-house.** If the pilot wins, design a Nowing `dsh` profile/bundle with a PostgreSQL persistence plugin, Redis Stream dispatch, and PII-safe tool adapters. If it loses, formalize the in-house sidecar as the canonical `dsh` and close the architecture gap.

### Risk-Adjusted Recommendation

Given that:
- Story 26.2 is already implemented and working in Python;
- DeepSeek Harness is in developer preview and introduces a second runtime;
- The team is in the final sprint before closed beta (Story 26.7 is done; launch target is ~2026-09-10);

**the lowest-risk action is Option A:** update docs to clarify that `DSH` is an in-house sidecar inspired by Harness patterns, and defer any repo integration to a post-beta epic.

### Future Outlook

DeepSeek Harness's plugin architecture, session replay, and subagent orchestration are attractive for a self-host/PLG future. If Nowing later wants a local agent IDE or an OSS sidecar runtime, `dsh` is a strong candidate. Until then, the Python `dsh-worker` aligned with AD-102/AD-106 is the right production choice.

### Technical Research Methodology and Source Verification

- **Web sources:** `github.com/deepseek-ai/deepseek-harness`, `https://deepseek.com/harness/en/`, Cordis and DSH reference docs, DSH MCP client and OpenAPI plugin docs, agent-pattern literature.
- **Nowing sources:** `ARCHITECTURE-SPINE.md` (2026-08-17), `.memlog.md`, `sprint-change-proposal-2026-08-17-unified-nowing-chainlens-dsh.md`, `Story 26.2`, `Story 26.1`, `epics.md`.
- **Code verification:** `grep` for `deepseek-harness`, `dsh-worker`, `DSH`, and `Harness` across `nowing` and `chainlens-research` repositories; inspection of `nowing_backend` dependency and Docker files.
- **Confidence levels:** high for repo existence and current non-integration; medium for architecture intent; medium for future adoption feasibility.

### Conclusion

`github.com/deepseek-ai/deepseek-harness` has **not been integrated** into Nowing/ChainLens. The architecture uses its name and patterns, but the working sidecar is a custom Python implementation. The immediate next step is to **resolve the naming/dependency ambiguity in documentation** and, if desired, **pilot the open-source harness after closed beta** under a separate epic.

