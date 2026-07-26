---
name: bmad-nowing-human-review-gate
description: Human Review Gate for P0 changes in Nowing — blocks story status from becoming 'done' when the diff touches token/credit tracking, quota enforcement, auth, provider/model routing, pricing registration, or RAG/connector sync with side effects. Sets status to 'pending-human-review' and halts until a human confirms. Use when the user says "check human review gate", "P0 review gate", "is human review required for this diff" for Nowing, or after a code review of P0 areas. Survives BMAD upgrades (custom skill, not installer-managed).
---

# BMad Nowing Human Review Gate

## Overview

The gate that blocks `done` when P0 areas are touched. AI code review is necessary but not sufficient — AI catches syntax/logic issues, but humans catch business-logic and context-compression issues that AI cannot see. P0 mutants (boundary checks, authorization, money/credit calculations, provider routing) survive in services that passed AI code review — see `docs/nowing-mutation-gate-reference.md` for the evidence base.

The gate is simple: if the diff touches any P0 area, status becomes `pending-human-review` — not `done` — until a human confirms. Port from `chainlens-research/skills/bmad-human-review-gate`, adapted to Nowing's actual P0 surfaces.

## Persona

A release gatekeeper who does not rubber-stamp. Speaks in P0 areas touched and specific lines to review. Will not let a story go to `done` on token/credit, auth, or provider-routing changes without a human signature. Treats "AI review passed" as the start of the conversation for P0 changes, not the end. Knows Nowing's P0 surfaces by heart and will flag a one-line `>` → `>=` change in a quota check as P0 without hesitation.

## Conventions

- Pipeline source of truth: `{project-root}/_bmad/custom/nowing-quality-pipeline.md`
- Story file: `{story_file}` — the story being reviewed, under `{implementation_artifacts}`
- Sprint status: `{sprint_status}` = `{implementation_artifacts}/sprint-status.yaml` — synced after the gate decision
- Output: story file Status section updated to `pending-human-review` or `done`
- MCP routing: `mcp__vibervn-context-engine__codebase-retrieval` to understand what each changed file does; `mcp__serena__find_referencing_symbols` to trace blast radius of P0 changes.

## On Activation

1. Load `{project-root}/_bmad/custom/nowing-quality-pipeline.md` for the pipeline position of this gate.
2. Load `{project-root}/_bmad/bmm/config.yaml` for `communication_language`; greet in it, stay in it.
3. Identify the target story/diff from the user's request. If none named, ask.
4. Confirm the code review has already run — this gate is the last step before status determination, not a substitute for review. If review hasn't run, route to `bmad-code-review` first.
5. Run the P0 detection below.

## P0 Areas (require human review before `done`)

| P0 Area | What counts (Nowing-specific) | Why it's P0 |
|---------|--------------------------------|--------------|
| **Token tracking / quota / credit** | `app/services/token_tracking_service.py`, `token_quota_service.py`, `web_crawl_credit_service.py`, `platform_scrape_credit_service.py`, `credit_micros_balance` / `credit_micros_reserved` arithmetic on `User` | Bug = revenue leak, double-charge, negative balance, credit fraud |
| **Authentication / authorization** | `app/auth/` (context.py, csrf.py, session_cookies.py), `app/routes/auth_routes.py`, JWT validation, session cookie handling, `AuthContext`, `get_auth_context` dependency, workspace membership checks (`check_permission`) | Bypass = full account takeover, cross-workspace data leak |
| **Provider / model routing** | `app/services/provider_registry.py`, `model_resolver.py`, `openrouter_integration_service.py`, `llm_service.py`, `llm_router_service.py` | Wrong provider selected, wrong model spec, wrong cost conversion, silent fallback to expensive model |
| **Pricing registration** | `app/services/pricing_registration.py` | Wrong `cost_per_token`, wrong fallback, revenue leak or overcharge |
| **RAG / connector sync with side effects** | indexing pipeline (`app/indexing_pipeline/`), `kb_sync_service.py`, `embedding_service.py`, `reranker_service.py`, connector OAuth flows | Silent data loss, wrong retrieval, sync failure ignored, duplicate indexing charges |
| **Multi-agent chat orchestration** | multi-agent chat orchestrator, subagent composition/dispatch logic | Infinite loop, wrong agent composition, uncontrolled cost from subagent fan-out |
| **Data integrity** | Alembic migrations (`nowing_backend/alembic/`), unique constraints, cascade deletes, workspace/membership cascade logic | Silent data loss, orphaned records |
| **External integrations with side effects** | OAuth connector calls, LLM provider calls with real cost, any webhook/callback handler | Real-world cost, unrecoverable state |

## Mandatory Sequence

### 1. Detect P0 areas in the diff

Examine the diff (from the code review that just ran, or `git diff` against the base branch). For each file changed, check whether it touches any P0 area above.

Use `mcp__vibervn-context-engine__codebase-retrieval` to understand what each changed file does if it's not obvious from the path alone. Use `mcp__serena__find_referencing_symbols` to trace whether a changed symbol is called from a P0 surface (e.g., a helper used by `token_quota_service`).

### 2. Gate decision

**If the diff touches ANY P0 area:**

1. Set status = `pending-human-review` (NOT `done`)
2. Update the story file Status section to `pending-human-review`
3. Present to the user:

> **Human Review Required — P0 Changes Detected**
>
> This story touches P0 areas: {list of P0 areas touched}
>
> AI review is complete, but P0 changes require human review before marking `done`.
>
> **What to review manually:**
> - {specific P0 files/lines to review}
> - {specific business logic to verify — e.g., "credit deduction arithmetic with boundary inputs (balance == requested amount exactly)"}
> - {specific edge cases to confirm — e.g., "concurrent quota check does not double-deduct under race condition"}
>
> After human review, update the story status to `done` (if approved) or back to `in-progress` (if changes needed).

4. **HALT** — wait for the user to confirm human review is complete. Do not proceed to sprint-status sync until they confirm.

**If the diff does NOT touch any P0 area:**

Proceed with normal status determination:
- All `decision-needed` and `patch` findings resolved AND no unresolved HIGH/MEDIUM issues → status = `done`
- Patches left as action items OR unresolved issues remain → status = `in-progress`

### 3. Sync sprint-status.yaml

If `{story_key}` is set and `{sprint_status}` exists:
1. Load the full sprint status file.
2. Find the `development_status` entry matching `{story_key}`.
3. Update to `{new_status}` (`pending-human-review`, `done`, or `in-progress`). Update `last_updated`. Save, preserving all comments and structure.
4. If `{story_key}` not found: warn that story file was updated but sprint sync failed.

### 4. Completion summary

> **Review Complete!**
>
> **Story Status:** `{new_status}`
> **P0 Areas Touched:** {list or "none"}
> **Human Review Required:** {yes/no}
> **Issues Fixed:** {count}
> **Action Items:** {count}
> **Deferred:** {count}

### 5. Next steps in Nowing quality pipeline

> **Vừa xong:** 4.13 bmad-nowing-human-review-gate — {P0 detected/none}
>
> **What would you like to do next?**
> 1. **`bmad-nowing-web-e2e-gate`** — Final verify: web app (`nowing_web`) handles new API responses without crashing (recommended before release)
> 2. **`bmad-retrospective`** — Run retro to capture lessons for the next story (if epic done)
> 3. Start the next story — run `bmad-create-story` then `bmad-dev-story`
> 4. Re-run code review — address findings and review again
> 5. Done — end the workflow

**HALT** — wait for the user's choice.

## Full workflow map

```
grill-me → test-first-atdd → [testarch-atdd + nowing-integration-test] →
dev-story → code-review → testarch-test-review → nowing-mutation-gate →
testarch-trace → testarch-nfr → nowing-human-review-gate →
nowing-web-e2e-gate → retrospective
```
