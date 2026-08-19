# DSH Self-Host Pilot Plan — DeepSeek Harness (`deepseek-harness`) cho local/self-host experience (Post-Closed Beta)

**Project:** Nowing  
**Date:** 2026-08-19  
**Status:** 🟡 **DEFERRED — post Closed Beta**  
**Depends on:** Closed Beta launch milestone (target 2026-09-10) and PO ratification of `sprint-change-proposal-2026-08-19-dsh-no-deepseek-harness-pre-beta.md`.

---

## 1. Goal

Evaluate whether `github.com/deepseek-ai/deepseek-harness` can become an **optional, self-host-only agent runtime** connected to Nowing via MCP/REST, without replacing the cloud `dsh-worker` sidecar.

**Success criteria:**
- Self-host users can run `dsh` locally and delegate simple lead-research missions to their own hardware.
- Nowing cloud sidecar remains unchanged and retains PII/compliance control.
- Pilot produces a go/no-go decision with cost, latency, and PII-leak metrics.

## 2. Scope

### In scope
- `dsh-headless` bundle for one non-PII mission type (e.g., `noop` or `lead-enrichment` mock).
- One Nowing MCP tool plugin: `batch_ingest_leads` exposed through `nowing_mcp`.
- One persistence adapter mapping `dsh` `SessionEvent` → Nowing `dsh_missions` rows.
- PII filtering at the boundary (no phone/email in session log).

### Out of scope
- Replacing the Python `dsh-worker` in cloud.
- Full Cordis plugin productionization.
- PII processing inside `dsh`.

## 3. Pre-requisites

- Closed Beta is live and stable.
- `nowing_mcp` server is production-ready and documented.
- A non-PII mission sandbox (test workspace with synthetic leads).
- One engineer owns Cordis/TypeScript ramp-up.

## 4. Phases

### Phase 1 — Spike (1 week)
- Install `dsh` headless locally.
- Run `dsh --profile headless "..."` against a mock Nowing MCP server.
- Verify tool-call roundtrip, timeout, and session log.

### Phase 2 — Nowing MCP plugin (2 weeks)
- Expose `batch_ingest_leads` as an MCP tool with workspace-scoped auth.
- Ensure `dsh` can call it with `mcp__nowing__batch_ingest_leads`.
- Add telemetry: `TokenUsage`, `BillingEvent`, `mission_id` correlation.

### Phase 3 — Persistence bridge (1–2 weeks)
- Write a `dsh` persistence plugin or adapter that writes checkpoint/session events to PostgreSQL `dsh_missions`.
- Do NOT store PII in `SessionEvent`; only mission phase, progress, and subtask IDs.

### Phase 4 — Self-host packaging (1 week)
- Docker Compose service `dsh-local` with `DSH_HOME` mount, PAT injection, and `tini` PID 1.
- Document `.env` variables and profile/bundle setup.

### Phase 5 — Evaluation (2 weeks)
- Run 50 missions on local vLLM + DeepSeek Cloud.
- Metrics: success rate, p50/p95 latency, cost per lead, tool-call error rate, PII leakage (must be 0).
- Compare against cloud Python sidecar baseline.

## 5. Go / No-Go Criteria

| Criteria | Go | No-Go |
|---|---|---|
| PII leakage | 0 incidents | >0 |
| Mission success rate | ≥ cloud baseline -5% | < baseline -5% |
| Cost per lead | ≤ cloud baseline +20% | > +20% |
| p95 latency | ≤ 2× cloud baseline | > 2× |
| Ops overhead | One extra container, one engineer owner | Requires >1 FTE or new infra class |

## 6. Risks & Mitigations

| Risk | Mitigation |
|---|---|
| `dsh` API changes in preview | Pin to a specific commit; vendor fork if needed. |
| Local users misuse for PII | Hard block PII fields in tool schemas; validate server-side. |
| MCP tool auth bypass | Use PAT with limited scopes and short TTL. |
| Session log grows unbounded | Set retention policy aligned with `RUNS_RETENTION_DAYS`. |

## 7. Deliverables

- `dsh-local-nowing` profile/bundle repository or directory.
- ADR documenting go/no-go.
- Updated self-host docs (`README.md`, `docs/self-host.md`).
- Decision to (a) adopt for self-host, (b) defer, or (c) discard.

## 8. Deferred Until

- Closed Beta launch is complete.
- PO/Architect approve post-beta research epic.
- `nowing_mcp` is stable and has at least one production MCP tool.
