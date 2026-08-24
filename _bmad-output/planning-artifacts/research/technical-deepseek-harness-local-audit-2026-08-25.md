# DeepSeek Harness (deepseek-harness) — Local repo audit & Nowing integration potential

**Date:** 2026-08-25
**Repo read:** /Users/luisphan/Documents/GitHub/deepseek-harness (v0.1.1-rc.2, MIT)
**Context:** Follow-up to technical-deepseek-harness-nowing-chainlens-dsh-research-2026-08-19.md

---

## 1. Executive summary

`deepseek-harness` is a real TypeScript/Node/Cordis agent harness in developer preview. It is MIT licensed, version 0.1.1-rc.2, and its architecture is genuinely modular ("everything is a plugin"). The local repo confirms the 2026-08-19 research: it is not a drop-in replacement for the Nowing `dsh-worker` Python sidecar, ChainLens deep-research engine, or the Epic 27 web-builder container/deploy pipeline.

Three strongest integration points for post-Closed Beta:
1. Optional self-host agent runtime driven from Python via deepseek-harness-sdk (JSON-RPC over stdio).
2. MCP client bridge to nowing_mcp tools, including nowing_chainlens_research.
3. Sandboxed shell/subprocess capability as a possible build/preview executor for Epic 27.1b.

The pre-beta recommendation remains: do not integrate into the cloud runtime; keep the 2026-08-19 DSH naming clarification and the dsh-self-host-pilot-plan-2026-08-19.md scope.

---

## 2. Core architecture (from local repo)

### Cordis plugin model
- Every component is a Cordis plugin: model adapter, tool registry, session log, agent loop, UI.
- Plugins declare dependencies via `inject`, register services at `ctx.<key>` (e.g. ctx.tools, ctx.llm), and clean up on unload.
- Events are typed and dispatched as emit, waterfall, parallel, serial; registrations are reversible ctx.effect() / ctx.on().
- Source of truth: docs/architecture.md, docs/cordis-primer.md.

### Profile / bundle / patch
- A running dsh is a composition of bundles and cordis.patch.yml layers.
- dsh-base ships model adapters, tools, persistence, sandbox, settings, credentials, telemetry.
- dsh-headless is a one-shot runner; dsh-web-app is the browser UI.
- This supports building a custom dsh-local-nowing profile later.

### Session log is the source of truth
- core/session owns the append-only SessionEvent log.
- Rule: "Model-visible means logged" — anything the model sees must be reconstructable from the log.
- Fork, resume, replay, and telemetry derive from the event stream.
- Integrating with Nowing means bridging this log to PostgreSQL/Zero-Cache or accepting dual sources.

### Turn / step / tool pipeline
- A turn contains one or more steps. A step is one model request plus tool calls.
- Key events: turn/start, agent/pre-step, step/start, user/message, agent/request, llm/stream, assistant/message, tool/call, tools/pre-execute, tools/execute, tools/post-execute, tool/result, step/end, agent/turn-stopping, turn/end.
- agent/pre-step, agent/request, llm/stream, and tools/* are waterfall listeners that must call next().
- core/agent-loop is the only concrete loop implementation; new behavior is added via plugins, not by changing the loop.

### Capability seams
- A seam has three roles: Service Definition, Service Provider, Consumer.
- Relevant families: web, subagent, workflow, skill, shell, subprocess, fs, lsp, code-runtime, e2b, mcp-client.

---

## 3. Packages most relevant to Nowing

| Package family | Role | Relevance to Nowing |
|---|---|---|
| mcp/mcp-client | Connects to external MCP servers and registers tools under mcp__<server>__<tool> | Can consume nowing_mcp (tools like nowing_chainlens_research, scrapers) |
| web/ | Exa / Perplexity / DeepSeek search + HTTP fetch | Could be an alternative research path for self-host, not a ChainLens replacement |
| subagent/ | Delegation to child agents with continuation | Matches mission sidecar / multi-agent patterns in AD-106 |
| workflow/ | Model-authored orchestration over subagents | Matches DSH long-running missions |
| skill/ | Skill catalog and loader | Resembles Nowing ChatMode / AgentConfig registry |
| shell/, subprocess/, fs/ | Bash, process tree, filesystem | Useful for sandboxed build/preview runner |
| code-runtime/ | Execute model-generated code | Not a CI/CD runner; not suitable for next build alone |
| e2b/ | POC external sandbox | Not a production deploy engine |
| api/gateway | Typert RPC Host/Client | Required for remote calls between Nowing Python and dsh Node |
| sdk/ + python/ | JSON-RPC protocol and Python SDK over stdio | Primary bridge from Nowing backend |

---

## 4. Integration scenarios

### 4.1. Self-host / local agent runtime (post-beta)
- python/README.md: the Python SDK starts the bundled runtime and communicates over stdio JSON-RPC.
- Use case: a user runs dsh on their own machine, with their own API keys, and delegates long missions without hitting Nowing cloud workers.
- Fits the existing dsh-self-host-pilot-plan-2026-08-19.md.

### 4.2. dsh as MCP client to Nowing
- mcp/mcp-client supports stdio and streamable-http, auth headers, auto-reconnect, and namespaces tools.
- nowing_backend/app/mcp_tools.py already exposes nowing_chainlens_research, scrapers, workspace tools, memory, etc.
- This is a clean separation: dsh orchestrates, Nowing provides data/research tools.

### 4.3. Epic 27.1b build/preview runner
- dsh can execute npm install && next build && next dev in a sandboxed subprocess.
- landlock-run native addon provides lightweight file-system sandboxing on Linux.
- Caveat: it is not a full container orchestrator; Docker/Traefik/Caddy remain needed for 27.1c.

### 4.4. What dsh does NOT solve
- 27.1c container deploy & CNAME: no Docker/Traefik/Caddy providers.
- 27.1d Mark Tool AST mutator: no AST parser/mutator; lsp is read-only language-server.
- ChainLens replacement (Epic 9): dsh is an agent harness, not a low-latency search API. It could consume ChainLens, not replace it.
- Replace dsh-worker Python sidecar (Story 26.2): too much churn pre-beta; Python sidecar already runs.

---

## 5. Integration gaps and risks

| Gap | Description | Severity |
|---|---|---|
| State model | dsh append-only SessionEvent vs Nowing PostgreSQL/Zero-Cache | High |
| Runtime stack | Node/TypeScript Cordis vs Python FastAPI | Medium (bridge via Python SDK) |
| PII boundary | dsh logs everything model sees; PII must be filtered before persistence | High |
| Cost tracking | dsh telemetry not mapped to Nowing TokenUsage | Medium |
| Tool model | dsh function-calling/Code Mode vs Nowing Pydantic capabilities | Medium |
| Deployment | Extra Node container + native landlock-run + pnpm | Medium |
| API stability | v0.1.1-rc.2, preview, breaking changes expected | High |

---

## 6. Recommendations

1. Keep the 2026-08-19 decision: do not integrate deepseek-harness before Closed Beta. Continue treating dsh-worker as the Python sidecar.
2. Proceed with the post-beta self-host pilot in dsh-self-host-pilot-plan-2026-08-19.md.
3. For Epic 27, do not rely on dsh for 27.1c or 27.1d. 27.1b may be explored as a spike only.
4. If adopted later, start from:
   - A custom dsh-local-nowing profile/bundle.
   - mcp-client pointing at nowing_mcp.
   - A SessionEvent -> dsh_missions persistence adapter with strict PII filtering.
   - A 50-mission evaluation against the Python sidecar using the pilot go/no-go criteria.

---

## 7. Sources

- deepseek-harness repo at /Users/luisphan/Documents/GitHub/deepseek-harness
  - docs/architecture.md
  - docs/cordis-primer.md
  - package.json (version, license, engines)
  - LICENSE
  - packages/core/agent-loop/README.md
  - packages/core/session/README.md
  - packages/mcp/mcp-client/README.md
  - packages/api/gateway/README.md
  - packages/web/README.md
  - packages/subagent/README.md
  - packages/workflow/README.md
  - packages/skill/README.md
  - python/README.md
  - packages/sdk/README.md
- Nowing repo:
  - _bmad-output/planning-artifacts/research/technical-deepseek-harness-nowing-chainlens-dsh-research-2026-08-19.md
  - _bmad-output/planning-artifacts/dsh-self-host-pilot-plan-2026-08-19.md
  - _bmad-output/planning-artifacts/sprint-change-proposal-2026-08-19-dsh-no-deepseek-harness-pre-beta.md
  - _bmad-output/planning-artifacts/architecture/architecture-unified-nowing-chainlens-dsh-2026-08-17/ARCHITECTURE-SPINE.md
  - nowing_backend/app/mcp_tools.py
