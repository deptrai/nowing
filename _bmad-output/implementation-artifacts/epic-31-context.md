# Epic 31 Context: Web Builder Container Isolation, AST Security & Entitlements

<!-- Compiled from planning artifacts. Edit freely. Regenerate with compile-epic-context if planning docs change. -->

## Goal

Epic 31 hardens the Web Builder and Presentation Studio surface shipped in Epic 27 for real multi-tenant production use. It turns the per-app container deploy path into an isolated, quota-bounded runtime on Dokploy (cgroup CPU/memory limits, dedicated networks), upgrades custom-domain binding from a CNAME check to cryptographic TXT-record ownership proof before ingress is configured, gives the Mark Tool a safe static-eval policy so it can match JSX elements with dynamic `className` expressions, and makes Presentation Studio output format (PPTX vs Marp) a plan-tier entitlement rather than a purely UI-driven choice. The epic bundles the blocked hardening findings from Epic 27 code reviews, formalized in the 2026-09-11 deferred-epics roadmap proposal ("Epic A").

## Stories

- Story 31.1: Dokploy Multi-Tenant Container Resource Constraints (Cgroup CPU/Memory) & Network Isolation
- Story 31.2: Strict CNAME DNS/Ingress Ownership Verification
- Story 31.3: AST Static-Eval Policy for Dynamic JSX Expression Matching in Mark Tool
- Story 31.4: Entitlement-driven Presentation Studio Format Selection from Chat Entry Points

## Requirements & Constraints

- Container resource limits must be sourced from workspace tier config — explicit `nano_cpus` and `memory_bytes` applied at container start, not hardcoded constants. The plan catalog may need new container-quota fields.
- Deployed user app containers must sit on an isolated bridge network with no ingress path to the internal Docker daemon or backend databases. The backend itself mounts the Docker socket; user containers must not.
- Custom-domain ownership must be proven via a TXT verification token before any Traefik label or Caddy snippet is written; requests to unverified domains are rejected with HTTP 400.
- The Mark Tool static-eval policy must be *safe*: resolve only statically-known string concatenation and template literals (e.g. `cn("a", "b")`, `` `px-${size}` `` patterns). It must never execute arbitrary JavaScript — this is a security boundary, not just a matching improvement.
- Presentation format entitlement is resolved from the workspace plan: higher tiers get native PPTX export, free workspaces get Marp Markdown. Existing fail-closed gating (global flag + workspace feature field + 403) must be preserved.
- Adjacent deferred findings allocated in the same proposal but not covered by these four stories — broad CSP on published apps, prompt echo in thinking SSE, and prompt retention on deliverables — are out of scope unless a story spec says otherwise.

## Technical Decisions

- Governed by AD-113 (Web App Builder hosting: Traefik in production/Dokploy, Caddy file-provider for self-host/dev), AD-113a (static-snapshot hosting is a deliberate transient exception — do not regress it), AD-114 (Mark Tool AST mutator), AD-120 (ChatMode registry — no inline `if/elif` mode branches), AD-121 (ArtifactKind extension registry).
- Deploy surface already built by Story 27.1c: `WebAppDeployService` (`app/services/web_builder/deploy/`) generates Traefik labels (`Host`/`HostRegexp` rules, TLS certresolver, loadbalancer port) and Caddy snippets, names containers `nowing-app-{workspace_id}-{slug}`, tags images `nowing-web-app-{workspace_id}-{app_id8}:{slug}`. `WorkspaceApp` already carries `container_id`, `port`, `custom_domain`, `custom_domain_status`. Story 31.1 adds runtime constraints + network attachment on this path; Story 31.2 adds the TXT-token gate inside `verify_and_bind_custom_domain` (currently a dnspython CNAME check against `CNAME_INGRESS_HOST`).
- Build-time sandbox precedent from Story 27.1b is the pattern to reuse for runtime limits: `validate_project_security` AST/regex audit, `_get_sanitized_build_env` credential scrubbing, and the Docker build runner (`WEB_BUILDER_DOCKER_SANDBOX_ENABLED`) already uses `--network none --memory 1024m --cpus 2.0 --security-opt no-new-privileges`.
- Entitlement plumbing exists: `WorkspaceLimit`/`WorkspaceLimitService` resolves effective limits via workspace override → plan default (`Workspace.plan_tier`: free/team/growth/enterprise) → env override → free fallback. Chat modes are gated by the `CHAT_MODES` registry + `is_chat_mode_enabled` (global flag, then workspace feature field, fail-closed). Format selection should plug into the `generate_presentation` input schema — do not fork the single `presentation_studio` ChatMode id, which is a deliberate design choice.
- Mark Tool matching lives in `MarkToolASTMutator` (`app/services/web_builder/mark_tool.py`); selector→JSX-node matching currently assumes string-literal `className` because the generator only emits literals. The static-eval policy is required once generated or user-edited JSX uses `cn()`/clsx/template expressions.

## UX & Interaction Patterns

- CNAME modal flow (per Epic 27 UX contract): user enters a domain → modal shows required DNS records and SSL provisioning status → success returns to the publish drawer. Story 31.2 adds a TXT ownership-token record to this surface and an inline error state for unverified domains.
- Presentation entry points: quick chips ("Create a pitch deck (PPTX)" / "Create Marp slides"), slash commands (`/slides pptx`, `/slides marp`), and `?mode=presentation_studio`. With Story 31.4, chip availability and the auto-selected format reflect plan entitlement; follow the existing "not enabled on this workspace plan" 403 + upgrade-prompt pattern.
- Mark Tool UX is unchanged (hover → 2px primary outline → click → inline prompt). Story 31.3 only widens what the backend matcher can resolve.

## Cross-Story Dependencies

- Stories 31.1 and 31.2 touch the same deploy path (container run + ingress registration in `WebAppDeployService`): TXT verification should gate route registration regardless of network-isolation work — keep the two changes module-separable.
- Story 31.4 depends on plan-tier entitlement semantics. The plan catalog exists (Stories 8.12, 29.3); the plan→format entitlement mapping must be defined there or in mode config before the tool schema can consume it.
- Story 31.3 has a soft dependency on the generator emitting dynamic class expressions — the improved matcher is only observable end-to-end once generated or user-edited JSX uses `cn()`/template literals.
- The whole epic assumes Epic 27 is complete (it is — 7/7 stories done, retro accepted 2026-09-10). This is hardening on top of delivered features, not new feature surface.
