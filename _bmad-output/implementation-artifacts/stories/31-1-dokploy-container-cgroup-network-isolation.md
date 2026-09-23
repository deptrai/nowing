# Story 31.1: Dokploy Multi-Tenant Container Resource Constraints (Cgroup CPU/Memory) & Network Isolation

Status: ready-for-dev

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a Platform Administrator,
I want deployed user web app containers to be constrained by Cgroup CPU and memory quotas and placed in isolated Docker networks,
so that no single user application can exhaust server resources or inspect other tenant containers on Dokploy.

## Acceptance Criteria

1. **Explicit Cgroup Resource Constraints from Workspace Tier Config**  
   - **Given** a web app container deploy request on Dokploy (`WebAppDeployService.deploy_container`),  
   - **When** the service prepares and starts the runtime container (`docker run`),  
   - **Then** it must resolve the workspace plan tier and enforce explicit CPU quota (`--cpus`) and memory limits (`--memory` with `--memory-swap` set equal to `--memory` to disable swap abuse), replacing the current hardcoded `--memory=512m --cpus=0.5 --pids-limit=100` in `service.py:630-632`.  
   - **And** the resource limits must support plan-tier overrides:
     - `free`: default memory `256m` / `0.25` CPU (max 50 pids).
     - `team`: default memory `512m` / `0.5` CPU (max 100 pids).
     - `growth`: default memory `1024m` / `1.0` CPU (max 200 pids).
     - `enterprise`: default memory `2048m` / `2.0` CPU (max 400 pids).  
   - **And** environment variable overrides (`WEB_BUILDER_TIER_MEMORY_MAP`, `WEB_BUILDER_TIER_CPUS_MAP`, `WEB_BUILDER_TIER_PIDS_MAP` — JSON dicts keyed by tier name) allow runtime tuning without code changes.  
   - **And** unknown/empty tiers fall back to the `free` limits (same normalization rule as `workspace_limits.py`: `(plan_tier or "free").lower()`).

2. **Isolated Docker Bridge Network & Non-Ingress Namespace**  
   - **Given** user-deployed web app containers on Dokploy,  
   - **When** the container is created,  
   - **Then** it is connected to a dedicated app bridge network (`nowing-web-apps-net`, created externally with `-o com.docker.network.bridge.enable_icc=false` or equivalent) via `WEB_BUILDER_DOKPLOY_NETWORK` — NOT the shared `dokploy-network`, because the `backend` service is attached to `dokploy-network` (docker-compose.yml:131-133) and user containers on it could reach `backend:8000` directly.  
   - **And** the chosen network must also be attached by the ingress proxy (Dokploy Traefik, or the `proxy`/Caddy service in self-host) — otherwise ingress routing breaks. Ingress attachment is an operator/infra concern; the code MUST fail loudly (deploy error) rather than silently if the configured network does not exist.  
   - **And** user containers MUST NOT be attached to the `default` compose network (which carries `db`, `redis`, `zero-cache`), the Docker daemon socket (`/var/run/docker.sock`), or internal metadata services.  
   - **And** tenant-vs-tenant traffic on the shared app bridge is blocked via `com.docker.network.bridge.enable_icc=false` on that network (daemon-level `--icc=false` only affects `docker0` and does NOT apply here); if that option is unavailable, document that one-network-per-app is the fallback isolation model.

3. **Cgroup Hardening & Security Profile Options**  
   - **Given** untrusted user application code executed in Next.js standalone runtime,  
   - **When** the container is launched,  
   - **Then** the container parameters must enforce, in addition to the existing `--security-opt=no-new-privileges` and `USER node` in `docker/web-app.Dockerfile` (already present — do not duplicate):  
     - `--memory-swap={tier_memory}` (equal to `--memory`; disables swap)  
     - `--pids-limit` based on tier (prevent fork bombs)  
     - `--cap-drop=ALL` (Next.js standalone on port 3000 needs no capabilities; `NET_BIND_SERVICE` is unnecessary for unprivileged ports)  
     - Read-only root filesystem with dedicated temporary writable tmpfs where appropriate (`--read-only --tmpfs /tmp:rw,noexec,nosuid,size=64m`); if the standalone server writes runtime artifacts (e.g. Next image cache), scope tmpfs/writable mounts accordingly rather than dropping the flag silently.

4. **Failure Handling, Healthcheck & Rollback Integrity**  
   - **Given** a container deployment with invalid resources or failing health check,  
   - **When** container start exceeds timeout or exits with non-zero status (e.g. OOMKilled by Cgroup during startup),  
   - **Then** `WebAppDeployService` catches the failure, inspects container exit reason (surfacing `OOMKilled` or resource constraint failure via `docker inspect --format '{{.State.OOMKilled}} {{.State.ExitCode}}'` BEFORE removing the container), cleanly stops/removes the failed container, rolls back/marks status `deploy_failed`, and preserves error logs for debugging.  
   - **And** the post-start healthcheck MUST NOT depend on the backend sharing a network with the user container: the current `_healthcheck_container` TCP-connects to `{container_name}:3000`, which only resolves while backend and app share `dokploy-network`. After the network move in AC2, healthcheck MUST instead poll `docker inspect` `.State.Health.Status` (the image already defines HEALTHCHECK in `docker/web-app.Dockerfile:31-32`) or the container IP on the app network — never the container name on a network the backend is no longer part of.

5. **Both Deploy Callers & Automated Tests**  
   - **Given** `deploy_container` has TWO callers — `deploy_app.py:191` (publish) and `custom_domain.py:203` (re-deploy on custom-domain bind),  
   - **When** tier-aware limits are threaded through,  
   - **Then** BOTH call sites must pass the resolved tier so a growth-tier app is not silently re-deployed with `free` limits after binding a domain.  
   - **And** `tests/unit/services/web_builder/test_deploy_service.py` + integration tests must pass 100%, verifying tier-based `--memory`, `--memory-swap`, `--cpus`, `--pids-limit`, `--cap-drop`, network attachment, OOM detection, and container failure cleanup without regression to existing `WebAppDeployService` functionality (21 existing tests).

## Tasks / Subtasks

- [ ] Task 1: Tier-Based Cgroup Quota Model & Configuration (AC: 1)
  - [ ] 1.1 In `nowing_backend/app/config/web_builder.py`, define code-level default mapping `WEB_BUILDER_TIER_LIMITS: dict[str, dict]` (`free`/`team`/`growth`/`enterprise` → `memory`, `cpus`, `pids_limit`) plus the three JSON env-override vars (`WEB_BUILDER_TIER_MEMORY_MAP`, `WEB_BUILDER_TIER_CPUS_MAP`, `WEB_BUILDER_TIER_PIDS_MAP`). Add all new names to `__all__`. (Ignore the stale "See line 1808" comment at web_builder.py:12 — `app/config/__init__.py` is only ~140 lines; `web_builder.py` IS the canonical module, re-exported via `from app.config.web_builder import *`.)
  - [ ] 1.2 Add helper `get_web_builder_tier_limits(plan_tier: str | None) -> dict[str, Any]` in `web_builder.py` that normalizes the tier (`(tier or "free").lower()`), applies env-map overrides over code defaults, and returns `{memory, cpus, pids_limit}`.
  - [ ] 1.3 Thread the tier explicitly: add a `plan_tier: str | None = None` parameter to `deploy_container()` (do NOT add a `session` param — it has none today and needs none). In `deploy_app.py` pass `ws.plan_tier` — the `Workspace` row is already loaded at deploy_app.py:44-52, no new query needed. In `custom_domain.py:203` resolve the tier from its existing `session` param (`select(Workspace.plan_tier)`) before calling. Do NOT add columns to `WorkspaceLimit` — that table models app-usage quotas (documents/members/credits), not container resources; a migration is unnecessary.

- [ ] Task 2: Multi-Tenant Network Isolation on Dokploy (AC: 2)
  - [ ] 2.1 Keep `WEB_BUILDER_DOKPLOY_NETWORK` as the attachment point but change the deployment docs/default posture: production should run a dedicated `nowing-web-apps-net` (created by the operator with `-o com.docker.network.bridge.enable_icc=false`) that Dokploy Traefik (prod) or the `proxy` Caddy service (self-host) also joins. If the configured network does not exist, `docker run` already fails — surface that error clearly.
  - [ ] 2.2 Verify in `docker/docker-compose.yml` that `db`, `redis`, `zero-cache`, Celery workers stay on `default` only, and document that `backend` remains on `dokploy-network` for platform ingress — which is exactly why user apps must leave `dokploy-network`.
  - [ ] 2.3 In self-host compose, if `WEB_BUILDER_DOKPLOY_NETWORK` is switched to `nowing-web-apps-net`, declare that network and attach `proxy` to it so Caddy can still reach `{container_name}:3000` (see `_caddy_target_for_app`).

- [ ] Task 3: Container Runtime Security Flag Hardening (AC: 3, 4)
  - [ ] 3.1 In `nowing_backend/app/services/web_builder/deploy/service.py:deploy_container()`, update `run_cmd` assembly:
    - Dynamic `--memory={tier_memory}` and `--memory-swap={tier_memory}`.
    - Dynamic `--cpus={tier_cpus}`.
    - Dynamic `--pids-limit={tier_pids}`.
    - Add `--cap-drop=ALL` and `--read-only --tmpfs /tmp:rw,noexec,nosuid,size=64m` (validate standalone still boots; adjust tmpfs targets if Next writes elsewhere).
    - Keep `--security-opt=no-new-privileges`, `--restart unless-stopped`, and never mount `/var/run/docker.sock` or host paths into user app containers.
  - [ ] 3.2 Replace the TCP-connect healthcheck: poll `docker inspect --format '{{.State.Health.Status}}'` until `healthy`/timeout (fallback to `.State.Running` + exit code if the image lacks HEALTHCHECK). On failure, inspect `.State.OOMKilled`/`.State.ExitCode`/`.State.Error` before `_stop_container`, include the reason in the raised error so `deploy_app`/`custom_domain` surfaces it in `WebAppDeployOutput.message` / `app_entity.error_message`.

- [ ] Task 4: Unit & Regression Testing (AC: 4, 5)
  - [ ] 4.1 In `nowing_backend/tests/unit/services/web_builder/test_deploy_service.py`, add test cases verifying:
    - Default resource limits applied for each plan tier (`free`, `team`, `growth`, `enterprise`) and unknown-tier → `free` fallback.
    - JSON env-map overrides for Cgroup parameters.
    - Network arg uses configured `WEB_BUILDER_DOKPLOY_NETWORK`; container never gets `default` network or docker.sock mount.
    - `plan_tier` threaded from BOTH `deploy_app` and `verify_and_bind_custom_domain` call sites (mock `deploy_container` and assert kwargs).
    - Inspect-based healthcheck + OOMKilled detection and cleanup when container exits from Cgroup memory exhaustion.
  - [ ] 4.2 Run `uv run pytest nowing_backend/tests/unit/services/web_builder/test_deploy_service.py` and ensure 100% pass rate (21 existing + new).

## Dev Notes

### Architecture Patterns & Invariants
- **AD-113 & AD-113a:** Web Builder multi-tenant runtime isolation on Dokploy. Each user web application container must run in a secure, sandboxed jail with bounded Cgroup resource allocations so noisy neighbors cannot trigger Node OOM on the host VPS or monopolize CPU cores.
- **Fail-Safe & Least Privilege:** User applications MUST NOT have access to host credentials, backend database sockets, or the Docker daemon socket (`/var/run/docker.sock`). The `backend` service mounts it read-only (docker-compose.yml:125) to orchestrate deployments; user containers must NEVER inherit or access it.
- **Tenant Isolation:** Network segregation ensures the ingress router can reach port 3000 of the target container, while tenant containers cannot communicate with each other or probe internal backend APIs.
- **Epic AC terminology note:** epics.md phrases the AC as `nano_cpus`/`memory_bytes` (docker-py SDK names). The implementation shells out to the docker CLI (`asyncio.create_subprocess_exec(docker_bin, ...)`) — `--cpus`/`--memory` are the correct equivalents; do not refactor to docker SDK.

### Caller Map (both must be updated)
- `deploy_app.py:191` — publish path; `ws.plan_tier` already loaded at lines 44-52.
- `custom_domain.py:203` — re-deploy on custom-domain bind; has `session` param, resolve `Workspace.plan_tier` there.
- `deploy_container(self, app_id, workspace_id, project_path, slug, custom_domain=None)` at `service.py:525` — add `plan_tier` keyword param only.

### Source Tree Components to Touch
- `nowing_backend/app/config/web_builder.py` — Add Cgroup tier quotas, env-override maps, and resolver helper.
- `nowing_backend/app/services/web_builder/deploy/service.py` — Dynamic tier param, Cgroup `--memory`/`--memory-swap`/`--cpus`/`--pids-limit`/`--cap-drop`/`--read-only`/`--tmpfs`, inspect-based healthcheck + OOM detection.
- `nowing_backend/app/services/web_builder/deploy/deploy_app.py` — Pass `ws.plan_tier` to `deploy_container`.
- `nowing_backend/app/services/web_builder/deploy/custom_domain.py` — Resolve and pass tier on the re-deploy path.
- `nowing_backend/tests/unit/services/web_builder/test_deploy_service.py` — Comprehensive unit test coverage.
- `docker/docker-compose.yml` — Declare `nowing-web-apps-net` + attach `proxy` (self-host path only; Dokploy Traefik attachment is operator-side).

### Testing Standards Summary
- Framework: `pytest` with `pytest-asyncio`
- Run command: `uv run pytest nowing_backend/tests/unit/services/web_builder/test_deploy_service.py`
- Pre-commit check: `uv run ruff check` (backend)

### Project Structure Notes
- Module path: `nowing_backend/app/services/web_builder/deploy/`
- Config path: `nowing_backend/app/config/web_builder.py`
- Test path: `nowing_backend/tests/unit/services/web_builder/test_deploy_service.py`

### References
- [Source: _bmad-output/planning-artifacts/epics.md#Epic 31: Web Builder Container Isolation, AST Security & Entitlements]
- [Source: _bmad-output/planning-artifacts/sprint-change-proposal-2026-09-11-deferred-epics-roadmap.md#Epic A]
- [Source: _bmad-output/implementation-artifacts/deferred-work.md#Deferred from code review of 27-1c]
- [Source: _bmad-output/implementation-artifacts/stories/27-1c-web-app-container-deploy-cname.md]
- [Source: nowing_backend/app/services/web_builder/deploy/service.py]
- [Source: nowing_backend/app/services/web_builder/deploy/custom_domain.py]
- [Source: nowing_backend/app/services/workspace_limits.py]
- [Source: nowing_backend/app/models/workspaces.py#WorkspaceLimit]
- [Source: docker/docker-compose.yml]

## Dev Agent Record

### Agent Model Used
claude-sonnet-5[1m]

### Debug Log References
- `uv run pytest nowing_backend/tests/unit/services/web_builder/test_deploy_service.py` verified 21/21 passing prior to Story 31.1 creation.

### Completion Notes List
- Story 31.1 context engineered with exhaustive analysis of existing WebAppDeployService, Dokploy network setup, Cgroup quotas, and workspace plan tiers.

### File List
- `nowing_backend/app/config/web_builder.py` (UPDATE)
- `nowing_backend/app/services/web_builder/deploy/service.py` (UPDATE)
- `nowing_backend/app/services/web_builder/deploy/deploy_app.py` (UPDATE)
- `nowing_backend/app/services/web_builder/deploy/custom_domain.py` (UPDATE)
- `nowing_backend/tests/unit/services/web_builder/test_deploy_service.py` (UPDATE)
- `docker/docker-compose.yml` (UPDATE — self-host network declaration only)

## Challenge Log (grill-me)

### Q1 — Already implemented?
- No duplicate: runtime-container tier limits do not exist — `deploy_container` hardcodes `512m/0.5/100` (service.py:630-632). No `get_*_tier_limits` helper anywhere in `nowing_backend`.
- Existing pattern reference: `builder.py:_run_subprocess` (523-554) already assembles a hardened `docker run` for the BUILD sandbox (`--cap-drop ALL`, `--security-opt no-new-privileges`, `--memory`, `--cpus`, conditional `--network`). Reuse its flag style for consistency; a shared arg-builder helper is optional — do not force an abstraction for two call sites.

### Q2 — Simpler alternative?
- No simpler correct alternative. `WorkspaceLimitsService` resolves plan defaults + workspace overrides, but `workspace_limits` has no container-resource columns — extending it means an alembic migration for no benefit over a config map. `ws.plan_tier` → `get_web_builder_tier_limits()` is the minimal correct path.

### Q3 — Edge cases spec misses (Pattern 3)
- [ ] Boundary: `pids_limit=50` (free) and `--memory=256m` may be too tight for Next standalone (baseline RSS ~80-150MB; node thread pools count toward pids) — expect OOM/pids churn on free tier; tests should assert limits applied, ops should watch for restart loops.
- [ ] Boundary: partial env-map override (e.g. `WEB_BUILDER_TIER_MEMORY_MAP` sets only `growth`) — merge semantics = per-key override over the tier's code defaults; document.
- [ ] Null/empty: `WEB_BUILDER_DOKPLOY_NETWORK=""` → today `network_args=[]` silently puts the container on `docker0` (ICC on, no ingress) — MUST refuse to deploy when network resolves empty while `WEB_BUILDER_CONTAINER_DEPLOY_ENABLED=TRUE`.
- [ ] Null/empty: malformed JSON in `WEB_BUILDER_TIER_*_MAP` → helper must log + fall back to code defaults, never crash the deploy path.
- [ ] Concurrent: per-app deploy lock already serializes same-app deploys; concurrent different-app deploys are safe (independent containers). Tier change mid-deploy is benign (limits fixed at `docker run`).

### Q4 — Failure modes unspecified (Pattern 2, 4)
- [ ] Post-deploy OOM flap: `--restart unless-stopped` + too-low `--memory` → container OOM-restarts AFTER successful healthcheck; `WorkspaceApp.status` stays `published` while the app is down. Out of scope to fully solve — document as known limitation + recommend external container-health monitoring.
- [ ] Ingress not attached to `nowing-web-apps-net`: `docker run` succeeds and inspect-healthcheck passes, but public URL 502s because Traefik/Caddy never joined the app network — not detectable from the deploy call; belongs in operator runbook (list in Task 2.1 docs).
- [ ] Negative/invalid values in env maps (`--memory=-1`) → `docker run` fails loudly — acceptable; optionally clamp/validate in the helper.
- [ ] `docker inspect` race: container may auto-restart between inspect calls; capture `.State` snapshot in ONE inspect before `_stop_container`.
- [ ] Image without HEALTHCHECK → `.State.Health` is nil; story already specifies `.State.Running`+exit-code fallback.

### Triage
- Clean — no duplicates, no simpler alternative, no blocking security/money gaps. Proceed to test-first-atdd with the Q3/Q4 items folded into the test skeleton.
