---
stepsCompleted: [1]
inputDocuments: []
workflowType: 'research'
lastStep: 1
research_type: 'technical'
research_topic: 'Python-based agent harness alternatives to deepseek-harness and more complete solutions'
research_goals: 'Identify agent orchestration/harness frameworks that run on Python (matching Nowing stack) or are more complete/mature than deepseek-harness, and evaluate fit for Nowing dsh-worker.'
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

Investigate Python-based agent orchestration frameworks and more complete alternatives to `github.com/deepseek-ai/deepseek-harness` that could be used with Nowing's Python/FastAPI stack, or evaluate whether a more mature/commercial solution fits better.

## Technical Research Scope Confirmation

**Research Topic:** Python-based agent harness alternatives to deepseek-harness and more complete solutions
**Research Goals:** Identify agent orchestration/harness frameworks that run on Python (matching Nowing stack) or are more complete/mature than deepseek-harness, and evaluate fit for Nowing dsh-worker.

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


## Executive Summary

The search for alternatives to `github.com/deepseek-ai/deepseek-harness` focused on **Python-native or Python-supported agent orchestration and durable execution frameworks** that can be adopted by Nowing without adding a Node.js/Cordis runtime. The landscape in 2026 is mature and fragmented.

**Verdict:** There is no single framework that is a drop-in replacement for Nowing's bespoke `dsh-worker`, but **LangGraph** and **Agentspan** are the strongest alternatives depending on the adoption posture:

- **LangGraph** is the most production-proven Python orchestration framework, with durable execution, checkpointing, human-in-the-loop, and Postgres persistence. It matches the Nowing stack and can be incrementally introduced.
- **Agentspan** is the most complete *durable execution runtime* for agents, built on top of Netflix Conductor. It is closer to a true "harness as a service" but introduces a Conductor server dependency.
- **CrewAI** and **OpenAI Agents SDK** are simpler and faster to prototype, but lack the long-running, durable mission semantics Nowing needs out of the box.
- **Microsoft Agent Framework** is powerful but Azure-aligned and still converging from AutoGen/Semantic Kernel.
- **Mash** is the closest conceptual fit to what `dsh-worker` does today (Python durable workflows + agent harness) but is a small, early-stage project.

**Recommendation for Nowing:** Do not replace the custom `dsh-worker` before closed beta. Post-beta, run a **2-week spike on LangGraph** as the first candidate for Hướng B and a **2-week spike on Agentspan** if a durable runtime service is acceptable. Continue to avoid `deepseek-harness` as the primary runtime.

---

## 1. Alternative Landscape

### 1.1 Comparison Matrix

| Framework | Language | Runtime Model | Durability | Self-Host | Multi-Agent | MCP | Maturity | Best For |
|---|---|---|---|---|---|---|---|---|
| **LangGraph** | Python (+ JS) | StateGraph runtime in-process | Checkpoints, Postgres/Redis, time travel | ✅ | ✅ Supervisor/subgraphs | ✅ | High (Klarna, Replit, Uber cited) | Stateful long-running agents |
| **CrewAI** | Python | Role-based crews + Flows | `@persist` SQLite/Postgres (2026) | ✅ | ✅ Roles + Flows | ✅ | High, but production case studies anonymized | Fast multi-agent prototypes |
| **OpenAI Agents SDK** | Python (TS coming) | Client loop + Sessions | Sessions; no durable resume across crashes | ✅ | ✅ Handoffs / agents-as-tools | ✅ | High, lightweight | OpenAI-first agent apps |
| **Microsoft Agent Framework** | Python / C# / .NET | Pregel supersteps, workflow engine | Checkpoints, supersteps, durable task worker | Partial | ✅ Agent groups, executors | ✅ | GA 2026, converging SK+AutoGen | Enterprise Microsoft shops |
| **PyAgent** | Python + YAML adapters | Adapter/runtime-agnostic | Blueprint compiled to other runtimes | ✅ | ✅ 18 patterns incl. Supervisor | ✅ | Newer, spec-driven | Multi-runtime abstraction |
| **Mash** | Python | FastAPI host + durable workflow engine | Built-in durable step engine, Postgres | ✅ | ✅ AgentSpec + WorkflowSpec | Not clear | Early (small GitHub footprint) | Self-hosted durable agent pipelines |
| **Agentspan** | Python, TS, C# | Conductor durable workflow server | Conductor event history, crash recovery, HIL | ✅ (Conductor server) | ✅ Plan-Execute, pipelines, worker pools | ✅ | Newer, but built on Conductor | Durable long-running agents as service |
| **Temporal** | Python SDK on Go service | Workflow-as-code + Activities | Durable execution, replay, years-long | ✅ (Temporal cluster) | ✅ Child workflows, signals | Manual | Battle-tested (Netflix, Stripe, Doordash) | Mission orchestration, not AI-specific |
| **Prefect** | Python | Task/flow orchestration | Result caching, resume, exactly-once | ✅ (Prefect server) | Manual | Manual | Mature data workflow | Background jobs, durable Python tasks |
| **PyErgon** | Python | SQLite/Redis durable executor | Step log, resume, suspend, DAGs | ✅ | Workflow parent/child | No | Very early | Lightweight durable execution |
| **deepseek-harness** | TypeScript/Node.js | Cordis plugin runtime | SessionEvent append-only | ✅ | ✅ Subagent, workflow | ✅ | Developer preview | Reference only, already assessed |

*MCP = Model Context Protocol. Data is current as of 2026-08-19 based on project documentation and repository metadata.*

---

## 2. Detailed Analysis

### 2.1 LangGraph (LangChain Inc.)

**Architecture**
- Low-level graph-based orchestration. Workflows are directed (or cyclic) graphs of nodes and edges.
- State is a typed dictionary. Conditional edges branch on state.
- Checkpointers persist state at each super-step to Postgres, Redis, SQLite, or memory.
- Supports time travel: replay from a prior checkpoint or fork from a checkpoint with modified state.

**Why it fits Nowing**
- Python-native; Nowing is already on Python/FastAPI/SQLAlchemy/PostgreSQL.
- `PostgresSaver` can use Nowing's existing Postgres 16.
- Hierarchical delegation can be modelled as parent graph → subgraph (Supervisor → specialist).
- Durable execution, HITL, streaming, and observability (LangSmith) are built-in.
- License: MIT.

**Caveats**
- StateGraph mental model is not trivial; the learning curve is steep.
- LangChain/LangGraph have a history of frequent breaking changes.
- LangSmith is a commercial dependency for visual tracing; can be avoided by building custom telemetry.
- PII must still be filtered before state enters checkpoints.

**Relevant citation:** LangGraph durable execution docs describe `checkpointers` for short-term thread memory and `stores` for cross-thread memory, with `PostgresSaver` for production and retention recommendations.

### 2.2 CrewAI

**Architecture**
- Role-based agents ("crews") with tasks, tools, and processes.
- `Flow` (post-2025) adds orchestration: `@start`, `@listen`, `@router` decorators, Pydantic state, and `@persist` for checkpointing.
- `@persist` stores state to SQLite/Postgres and supports resume and fork.

**Why it fits Nowing**
- Pure Python, very fast to prototype.
- Role-based model maps naturally to Nowing's Specialist Team pattern (Research, Scraper, Valuation, PII Auditor).
- `Flow` gives control loops and persistence.

**Caveats**
- Role/crew abstraction is opinionated and can become a leaky abstraction.
- Durable execution is newer (`@persist`) and less battle-tested than LangGraph's checkpointer.
- Less fine-grained control over state transitions than LangGraph.

**Relevant citation:** CrewAI production architecture docs recommend starting with a Flow and using `@persist` to survive crashes.

### 2.3 OpenAI Agents SDK

**Architecture**
- Minimal set of primitives: Agent, Runner, tools, handoffs, guardrails, sessions, tracing.
- Runtime manages turns, tool execution, guardrails, handoffs.
- Sessions (SQLite/Redis/Postgres/Mongo/Dapr/Encrypted) maintain conversation history.
- Sandbox agents for isolated, resumable execution.

**Why it fits Nowing**
- Python-first, lightweight.
- Handoffs and agents-as-tools map to supervisor/specialist.
- Built-in tracing and MCP server support.

**Caveats**
- Execution is mostly client-side; crash recovery is not as robust as LangGraph/Temporal/Agentspan.
- Strongly OpenAI-centric, though it supports LiteLLM/any-LLM adapters.
- Not designed for hours-long durable missions without extra infrastructure.

**Relevant citation:** OpenAI Agents SDK docs list sessions, tracing, handoffs, and sandbox agents as core primitives; note "resumable execution through Sandbox agents."

### 2.4 Microsoft Agent Framework (formerly AutoGen / Semantic Kernel convergence)

**Architecture**
- Graph execution engine (Pregel-like supersteps).
- `Workflow` = directed graph of `Executor` nodes connected by edge groups.
- Checkpoints at end of each superstep; supports restore, HIL, and Durable Task worker hosting.
- `Harness` composes chat client, pipeline, context providers, middleware, and UX.

**Why it fits Nowing**
- Strong durability model (supersteps, checkpoints, Durable Task worker).
- Supports Python and .NET.
- Semantic Kernel plugin model is enterprise-friendly.

**Caveats**
- Azure and Microsoft ecosystem alignment.
- Convergence is still recent (GA April 2026); AutoGen is in maintenance mode.
- Smaller Python community footprint than LangGraph/CrewAI.

**Relevant citation:** Microsoft Learn "Checkpoints" page describes workflow checkpoints, replayability, and Durable Task worker support.

### 2.5 PyAgent

**Architecture**
- Spec-driven: `pyagent-blueprint` YAML declares agents, workflows, providers, governance.
- Blueprint compiles to multiple runtimes: LangGraph, CrewAI, OpenAI Agents, Semantic Kernel.
- 18 patterns (Supervisor, Pipeline, Debate, Fan-Out, ReAct, ...).
- Includes PII redaction, three-tier memory, cost tracking, OpenTelemetry.

**Why it fits Nowing**
- Could let Nowing write once and target multiple runtimes.
- Diff/review semantics for blueprints is attractive for governance.

**Caveats**
- Newer project; maturity and production footprint unknown.
- Additional abstraction layer may not be worth it if only one runtime is chosen.

**Relevant citation:** PyAgent homepage advertises spec-driven multi-agent architecture and compilation to LangGraph, CrewAI, OpenAI Agents, and Semantic Kernel.

### 2.6 Mash

**Architecture**
- Self-hosted durable runtime for Python automations.
- `WorkflowSpec` = ordered pipeline of typed `CodeStep` and `AgentStep`.
- `AgentSpec` defines agents; `HostBuilder` deploys pool; FastAPI server.
- Every request recorded as replayable runtime event; retries and restarts built-in.
- Single Postgres dependency.

**Why it fits Nowing**
- Conceptually closest to `dsh-worker`: Python sidecar + durable workflow + agent harness.
- Self-host friendly, FastAPI, Postgres.

**Caveats**
- Very small GitHub footprint (3 stars) and early stage; risk of abandonment.
- Not yet proven at scale.

**Relevant citation:** Mash README describes self-hosted durable runtime, `AgentSpec`, `WorkflowSpec`, `HostBuilder`, FastAPI server, and replayable runtime events.

### 2.7 Agentspan

**Architecture**
- Durable runtime built on Netflix Conductor.
- Agent definitions compile into Conductor workflows.
- Execution state lives outside the worker process; tool calls retry; human approvals resume.
- Python SDK; supports LangGraph, OpenAI Agents, Google ADK as inputs.

**Why it fits Nowing**
- True durable execution with crash recovery, scaling, replay, observability.
- Conductor has run billions of executions at Netflix/LinkedIn/Tesla.
- Can wrap existing Python agent code.

**Caveats**
- Requires Conductor server (new infra component).
- Adds a Java/Go orchestrator to a Python stack.
- Alpha status (PyPI 3 - Alpha).

**Relevant citation:** Agentspan homepage/GitHub describe durable runtime, Conductor foundation, plan-execute agents, and HITL.

### 2.8 Temporal

**Architecture**
- Workflow-as-code with deterministic replay.
- Go-based Temporal Service + Python SDK.
- Workflows can run for years; crash recovery via event history replay.
- Activities are the only place side effects happen; workflows are pure.

**Why it fits Nowing**
- Battle-tested for long-running durable workflows.
- Self-hostable.
- Strong exactly-once semantics.

**Caveats**
- Not AI-agent-native: no built-in LLM loop, tool registry, or MCP.
- Workflow determinism restrictions make "model decides next step" patterns awkward.
- New service (Go) and ops overhead.

**Relevant citation:** Temporal docs define Workflow Execution as durable, reliable, scalable, with no imposed time limit and full recovery.

### 2.9 Prefect

**Architecture**
- Python workflow orchestration; `@flow` and `@task` decorators.
- Durable execution via result caching, Redis/Postgres locking, resume.
- Exactly-once for side effects via idempotency keys.

**Why it fits Nowing**
- Python-native; Nowing already uses Celery-like patterns.
- Good for durable background tasks.

**Caveats**
- Data workflow, not agent orchestration.
- No built-in LLM loop, subagent, or MCP semantics.

**Relevant citation:** Prefect "Durable Execution" page explains result-based resume, distributed locking, and exactly-once tasks.

### 2.10 PyErgon

**Architecture**
- Minimal durable execution framework using SQLite or Redis.
- `@flow`/`@step` decorators; automatic retry; child flows; DAGs; external signals.

**Why it fits Nowing**
- Lightweight, Python, easy to embed.

**Caveats**
- Very early; small community; no agent-specific primitives.

**Relevant citation:** PyErgon README describes crash recovery, suspend/resume, signal coordination, and type-safe APIs.

---

## 3. Fit Assessment for Nowing

### 3.1 Must-Have Requirements

| Requirement | Nowing Need | Best Matches |
|---|---|---|
| Python stack | FastAPI/SQLAlchemy/PostgreSQL | LangGraph, CrewAI, OpenAI, Mash, PyErgon |
| Long-running missions (1–8h) | Sidecar, crash recovery | LangGraph, Agentspan, Temporal, Mash, MAF |
| Supervisor-Specialist pattern | Expert Pool, fan-out/fan-in | LangGraph, CrewAI, OpenAI, PyAgent, MAF |
| Checkpoint/resumption | Redis `XAUTOCLAIM` today | LangGraph, Agentspan, Temporal, MAF |
| PII-safe session log | Decree 13, PII vault | All require custom filter; LangGraph/Agentspan give more control than Cordis |
| Self-host | OSS/PLG-led | LangGraph, CrewAI, Mash, Agentspan, Temporal |
| Cost attribution per tool | Wallet/billing per tool call | Custom layer needed; LangGraph state easiest to instrument |
| MCP tool calling | `nowing_mcp`, external tools | LangGraph, CrewAI, OpenAI, Agentspan, MAF |

### 3.2 Short-List Verdict

| Candidate | Fit Score | Recommendation |
|---|---|---|
| **LangGraph** | 8/10 | Strongest Python-native candidate; durable, checkpointed, proven. Best for Hướng B. |
| **Agentspan** | 7/10 | Strongest durable runtime, but adds Conductor server. Best if Nowing wants a "harness service." |
| **CrewAI** | 6/10 | Easiest to start, but less control and newer durability. |
| **OpenAI Agents SDK** | 5/10 | Lightweight, but not durable enough for 1–8h missions without extra work. |
| **Mash** | 5/10 | Conceptually closest, but too early. Watch, not adopt now. |
| **Temporal** | 5/10 | Durable, but not AI-native; model-as-workflow is a mismatch. |
| **Microsoft Agent Framework** | 5/10 | Enterprise-grade, but Azure-aligned and recent convergence. |
| **PyAgent** | 4/10 | Interesting abstraction, too new. |
| **Prefect** | 4/10 | Data workflow, not agent harness. |
| **PyErgon** | 3/10 | Too early. |

---

## 4. Recommendations

### 4.1 Pre-Closed Beta (no change)

- **Keep the custom `dsh-worker` Python sidecar.** It is already aligned with AD-102/AD-106 and passes Story 26.7 quality gates.
- **Do not adopt any new harness framework** before closed beta.
- **Continue with the `DSH naming clarification`** (ARCHITECTURE-SPINE.md + .memlog.md + ADR/SCP already done).

### 4.2 Post-Closed Beta Roadmap (Hướng B + optional harness service)

| Phase | Candidate | Goal | Timebox |
|---|---|---|---|
| **Spike 1** | **LangGraph** | Port a single non-PII mission type (e.g. lead enrichment mock) to a LangGraph `StateGraph`; evaluate checkpointing with `PostgresSaver`, subgraphs for specialists, and MCP tool calling. | 2 weeks |
| **Spike 2** | **Agentspan** | Wrap an existing `dsh` mission with Agentspan Conductor runtime; evaluate crash recovery, worker pool, and HITL. | 2 weeks |
| **Decision** | — | Compare spikes on: PII safety, cost per mission, p95 latency, ops overhead, team ramp-up. Choose one, or stay custom. | 1 week |
| **Adopt (if LangGraph wins)** | LangGraph | Incrementally migrate `dsh-worker` to LangGraph `StateGraph`; add `dsh_mission_events` table, trajectory viewer, and cost per tool. | 2–3 sprints |
| **Adopt (if Agentspan wins)** | Agentspan | Run `dsh-worker` as Conductor worker tasks; build persistence bridge; keep Nowing as product/observability layer. | 2–3 sprints |
| **Adopt (if neither wins)** | Custom | Continue Hướng B manually: mission event log, subagent dispatcher, model-written plan, PII sanitizer. | 2–4 sprints |

### 4.3 What "Hướng B" specifically upgrades

If Nowing adopts LangGraph as the harness-like layer for the Python sidecar, the concrete upgrades are:

1. **Durable state graph** for missions with automatic checkpoint/resume.
2. **Subgraph per specialist** (Research, Scraper, Valuation, PII Auditor).
3. **Time-travel debugging** and replay for failed missions.
4. **Postgres-backed checkpointing** using the same DB as the product.
5. **Streaming and HITL** built into the runtime.
6. **MCP tool integration** through LangChain MCP adapters.
7. **Cost/TokenUsage instrumentation** via graph state hooks.

If Agentspan is chosen, the upgrades are:

1. **True durable execution** outside the worker process (survives worker crash).
2. **Distributed worker pool** for missions.
3. **Conductor-driven replay, retries, and human approval**.
4. **Plan-execute pattern** where the LLM emits a JSON plan that Conductor executes deterministically.

---

## 5. Risks and Mitigations

| Risk | Mitigation |
|---|---|
| LangGraph breaking changes | Pin version; fork or vendor if needed; abstract behind `dsh` service boundary. |
| Conductor/Agentspan ops overhead | Run as optional self-host addon, not cloud default. |
| PII in checkpoints | Filter/mask PII before writing state; keep PII only in `verified_contacts` (encrypted). |
| Team ramp-up | Start with 2-week spike; avoid full migration until success is proven. |
| Losing control of custom logic | Keep `dsh-worker` as a thin adapter; business rules stay in Nowing backend. |

---

## 6. Conclusion

For Nowing's Python stack, **LangGraph** is the most credible alternative to `deepseek-harness` for Hướng B. It provides durable execution, checkpointing, subagent orchestration, and MCP support in Python. **Agentspan** is the most complete *durable runtime* but requires Conductor. **CrewAI** and **OpenAI Agents SDK** are simpler but less suitable for hours-long, crash-resilient missions. **Mash** is conceptually closest but too immature.

**Final recommendation:** no change before closed beta; post-beta, **spike LangGraph first**, then **spike Agentspan**, then decide. Continue to avoid the `deepseek-harness` Node/Cordis runtime as the primary sidecar.

---

## Research Methodology and Source Verification

- **Web sources:** LangGraph docs, CrewAI docs, OpenAI Agents SDK docs, Microsoft Learn, PyAgent homepage, Mash GitHub, Agentspan homepage/GitHub/PyPI, Temporal docs, Prefect docs, PyErgon GitHub, FutureAGI/Scrimba/DecodeTheFuture/ODSEA comparison articles.
- **Verification method:** Cross-checked claims across multiple sources (e.g., AutoGen maintenance mode is confirmed by Microsoft docs and third-party articles). Maturity and feature claims are based on official documentation and repository metadata.
- **Confidence:** High for stack/runtime language and durability features; medium for production scale claims when only vendor case studies are available; low for very early projects (Mash, PyAgent, PyErgon) where only README/PyPI data exists.

---
