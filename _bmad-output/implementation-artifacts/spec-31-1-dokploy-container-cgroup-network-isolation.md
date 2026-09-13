---
title: '31-1 Dokploy container cgroup limits & network isolation'
type: 'feature'
created: '2026-09-11'
status: 'done'
review_loop_iteration: 0
baseline_commit: '92028fe862072331da05ff9fd70afb97c90d7237'
context: ['_bmad-output/implementation-artifacts/stories/31-1-dokploy-container-cgroup-network-isolation.md']
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** User web-app runtime containers on Dokploy run with hardcoded limits (`512m`/`0.5` CPU/`100` pids) on the shared `dokploy-network` — no per-tier quotas, no tenant isolation (backend `backend:8000` is reachable from it), and no swap/cap/read-only hardening. The TCP healthcheck to `{container_name}:3000` also silently depends on backend sharing that network.

**Approach:** Resolve `ws.plan_tier` → a tier→limits map in `web_builder.py` config (env-overridable), thread `plan_tier` into `deploy_container` from BOTH callers, harden the `docker run` flags, attach apps to a dedicated app bridge network, and replace the TCP healthcheck with `docker inspect` `.State.Health.Status` polling.

## Boundaries & Constraints

**Always:**
- `--memory-swap` set equal to `--memory` (swap disabled); dynamic `--memory`/`--cpus`/`--pids-limit`; add `--cap-drop=ALL` + `--read-only --tmpfs /tmp:rw,noexec,nosuid,size=64m`
- Both `deploy_container` callers pass the tier: `deploy_app.py:191` (`ws.plan_tier` already loaded) and `custom_domain.py:203` (resolve via existing `session` param)
- Healthcheck polls `docker inspect` `.State.Health.Status` (image already has `HEALTHCHECK`); fallback `.State.Running` + exit code if absent. Never TCP-connect to container name.
- Refuse deploy (clear error naming the env var) when `WEB_BUILDER_DOKPLOY_NETWORK` resolves empty while `WEB_BUILDER_CONTAINER_DEPLOY_ENABLED=TRUE` — never silently land on `docker0`
- Unknown/empty/`None` tier → `free`; malformed env-map JSON → code defaults + warning log
- Inspect `.State` (OOMKilled/ExitCode/Running) in ONE call BEFORE removing a failed container
- Keep existing `--restart unless-stopped`, `-d`, `--security-opt=no-new-privileges`, `USER node`

**Ask First:**
- Changing the default of `WEB_BUILDER_DOKPLOY_NETWORK` or creating `nowing-web-apps-net` on the Dokploy host (operator decision — ingress must join it)
- Adding columns/migration to `WorkspaceLimit` (not needed — config map covers it)

**Never:**
- Mount `/var/run/docker.sock` or host paths into user containers
- Attach user containers to `default` compose network or keep them on `dokploy-network` in the hardened config
- Add a `session` param to `deploy_container`, or refactor docker CLI subprocess calls to the docker SDK
- Rely on daemon-level `--icc=false` (docker0 only) — tenant isolation needs `com.docker.network.bridge.enable_icc=false` on the app network

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| free tier | `plan_tier="free"` | `--memory=256m --memory-swap=256m --cpus=0.25 --pids-limit=50` | N/A |
| unknown/empty tier | `None`, `""`, `"platinum"`, `"ENTERPRISE"` | normalize `.lower()`; unknown → `free` limits | N/A |
| malformed env map | `WEB_BUILDER_TIER_MEMORY_MAP="{bad"` | code defaults + warning log naming the var | no crash |
| partial env override | `WEB_BUILDER_TIER_CPUS_MAP={"growth":"1.5"}` | only `growth.cpus` overridden | N/A |
| empty network | `WEB_BUILDER_DOKPLOY_NETWORK=""` + deploy enabled | refuse deploy | error names the env var |
| network missing | `docker run` fails "network not found" | `deploy_failed`, stderr surfaced | message contains network name |
| startup OOM | inspect `OOMKilled=true ExitCode=137` | capture state → `rm -f` → `deploy_failed` | message contains `OOMKilled`/`137` |
| healthcheck | poll `.State.Health.Status` until `healthy`/timeout | no TCP to container name | timeout → cleanup + `deploy_failed` |
| no HEALTHCHECK in image | `.State.Health` nil | fallback `.State.Running` + exit code | graceful |
| custom-domain redeploy | `verify_and_bind_custom_domain` on `growth` ws | `deploy_container` receives `plan_tier="growth"` | ws lookup `None` → `free` fallback |

</frozen-after-approval>

## Code Map

- `nowing_backend/app/config/web_builder.py` — add `WEB_BUILDER_TIER_LIMITS` dict + `WEB_BUILDER_TIER_{MEMORY,CPUS,PIDS}_MAP` JSON env vars + `get_web_builder_tier_limits(plan_tier)`; update `__all__`. Ignore stale "line 1808" comment (:12) — this file IS canonical (`app/config/__init__.py` re-exports it).
- `nowing_backend/app/services/web_builder/deploy/service.py:525` `deploy_container` — add `plan_tier: str | None = None` kwarg. Hardcoded flags at :630-632. Healthcheck at :659-676 → replace TCP-connect internals with inspect polling; KEEP method name `_healthcheck_container` (existing test patches it, test:537). `_is_container_running` (:164-187) shows the `docker inspect --format` subprocess pattern to mirror.
- `nowing_backend/app/services/web_builder/deploy/deploy_app.py:44-52` — `ws` row already fetched → pass `ws.plan_tier` at the call site :191.
- `nowing_backend/app/services/web_builder/deploy/custom_domain.py:203` — second caller; resolve `select(Workspace.plan_tier)` via its `session` param before calling.
- `nowing_backend/app/services/web_builder/builder.py:523-554` — existing hardened `docker run` arg style (build sandbox); match flag style, no shared helper needed.
- `nowing_backend/app/models/workspaces.py:62` — `Workspace.plan_tier` column; tier names `free/team/growth/enterprise` at :510-515.
- `nowing_backend/app/services/web_builder/deploy_service.py` — facade: tests import `WebAppDeployService`, `disambiguate_slug`, `record_token_usage` from here; keep exports working.
- `nowing_backend/tests/unit/services/web_builder/test_deploy_service.py` — conventions: `mock_deploy_locks` autouse fixture, `mock_db_session` with `execute.side_effect` result lists, `asyncio.create_subprocess_exec` `side_effect=[build_proc, rm_proc, run_proc]` proc factories (:523-536).
- `docker/docker-compose.yml` — `backend`+`proxy` on `dokploy-network` (:99-133); `db`/`redis`/`zero-cache` on `default` only; declare `nowing-web-apps-net` + attach `proxy` (self-host path only).
- `docker/web-app.Dockerfile` — `USER node` (:26), `HEALTHCHECK` (:31-32) — enables inspect-based health; read-only, no changes needed.
- Full requirements: `_bmad-output/implementation-artifacts/stories/31-1-dokploy-container-cgroup-network-isolation.md` (ACs, Challenge Log edge cases, ATDD checklist `_bmad-output/test-artifacts/atdd-checklist-31-1-*.md`).

## Tasks & Acceptance

**Execution:**
- [x] `nowing_backend/app/config/web_builder.py` — add tier-limit defaults + env-map overrides + `get_web_builder_tier_limits()` — single owner of tier→cgroup mapping
- [x] `nowing_backend/app/services/web_builder/deploy/service.py` — `plan_tier` kwarg, dynamic cgroup + hardening flags, empty-network refusal, inspect-based healthcheck + OOMKilled capture before cleanup — core of the story
- [x] `nowing_backend/app/services/web_builder/deploy/deploy_app.py` — pass `ws.plan_tier` — publish path
- [x] `nowing_backend/app/services/web_builder/deploy/custom_domain.py` — resolve + pass tier — re-deploy path
- [x] `docker/docker-compose.yml` — declare `nowing-web-apps-net`, attach `proxy` — self-host ingress keeps working
- [x] `nowing_backend/tests/unit/services/web_builder/test_deploy_service.py` — tests per ATDD checklist (tier flags exact values, empty-network refuse, malformed JSON fallback, OOMKilled message, both callers pass tier)

**Acceptance Criteria:**
- Given a deploy request, when `docker run` is assembled, then memory/cpus/pids come from the workspace's resolved tier (defaults: free `256m`/`0.25`/`50`, team `512m`/`0.5`/`100`, growth `1024m`/`1.0`/`200`, enterprise `2048m`/`2.0`/`400`) with `WEB_BUILDER_TIER_*_MAP` env overrides and `--memory-swap` == `--memory`.
- Given `WEB_BUILDER_DOKPLOY_NETWORK` set to a dedicated app bridge, when the container starts, then it attaches only to that network and never `default`/docker0/docker.sock; empty value while deploy enabled → refused with clear error.
- Given a container failing healthcheck or OOM-killed at startup, when the failure is handled, then `.State` is captured in one inspect before `rm -f`, `deploy_failed` is set, and the message contains the exit reason.
- Given a custom-domain bind on a non-free workspace, when re-deploy runs, then the workspace's tier — not the default — drives the container limits.

## Spec Change Log

- **2026-09-12 (defer resolution)** — All 6 review-deferred items resolved post-commit `41bee360c`:
  1. *Tenant-vs-tenant* → opt-in `WEB_BUILDER_PER_APP_NETWORK` mode: each app gets its own bridge `nowing-app-{ws}-{app}-net` (`_app_network_name`/`_ensure_app_network`/`_cleanup_app_network`); isolation by membership; requires `WEB_BUILDER_INGRESS_PROXY_CONTAINER`; off by default = zero regression.
  2. *Egress* → documented resolution: Docker can't do partial egress per-network; host-firewall guidance (`iptables -I DOCKER-USER -d 169.254.169.254 -j DROP`) in env examples + compose comment.
  3. *Rollout* → `nowing_backend/scripts/redeploy_web_apps.py` (dry-run default, `--apply`, fresh session per app) + OOM-watch note for the 512m→256m free-tier drop.
  4. *Log bounding* → `--log-opt max-size=10m max-file=3` on `docker run`; build phase noted as inherently safe (runtime Dockerfile has zero RUN steps + existing wait_for timeout).
  5. *No-HEALTHCHECK fallback* → `_exec_health_probe` runs the image's own HTTP check via `docker exec` — running alone no longer counts as healthy.
  6. *Restart dead-window* → 3-consecutive-dead-sample streak in `_healthcheck_container` tolerates `unless-stopped` restart gaps.

## Design Notes

- Healthcheck reason: `_healthcheck_container` TCP-connects to `{container_name}:3000`, which only resolves while backend shares the app network. Moving apps to `nowing-web-apps-net` breaks that DNS — inspect-based polling removes the dependency entirely (Dockerfile HEALTHCHECK already exists).
- Ingress caveat (operator-side, not code): Traefik (Dokploy) / `proxy` (self-host Caddy) must also join `nowing-web-apps-net` or public URLs 502. `docker run` cannot detect this — document in compose comment.

## Verification

**Commands:**
- `cd nowing_backend && uv run pytest tests/unit/services/web_builder/test_deploy_service.py -m unit -q` — expected: all pass (21 existing + new)
- `cd nowing_backend && uv run ruff check app/config/web_builder.py app/services/web_builder/` — expected: clean

## Suggested Review Order

**Tier → cgroup resolution (entry point)**

- Tier defaults table — the contract every docker run flag derives from.
  [`web_builder.py:71`](../../nowing_backend/app/config/web_builder.py#L71)
- `get_web_builder_tier_limits` — normalization, env-merge, per-key validation, unknown-tier fallback.
  [`web_builder.py:149`](../../nowing_backend/app/config/web_builder.py#L149)

**Deploy path**

- `plan_tier` kwarg enters `deploy_container` — optional so existing callers/tests keep working.
  [`service.py:634`](../../nowing_backend/app/services/web_builder/deploy/service.py#L634)
- Network guard refuses empty AND reserved names (`default`/`bridge`/`host`/`none`) before any docker call.
  [`service.py:682`](../../nowing_backend/app/services/web_builder/deploy/service.py#L682)
- `run_cmd` — tier cgroup flags, swap disabled, `--cap-drop=ALL`, read-only rootfs + dual tmpfs.
  [`service.py:703`](../../nowing_backend/app/services/web_builder/deploy/service.py#L703)
- `_inspect_container_state` — single `.State` snapshot; immune to restart races, safe-id guarded.
  [`service.py:227`](../../nowing_backend/app/services/web_builder/deploy/service.py#L227)
- `_healthcheck_container` — polls `.State.Health.Status`; never TCP-connects across networks.
  [`service.py:302`](../../nowing_backend/app/services/web_builder/deploy/service.py#L302)
- Failure path — inspect snapshot BEFORE `rm -f`; error carries OOMKilled/ExitCode/Error.
  [`service.py:814`](../../nowing_backend/app/services/web_builder/deploy/service.py#L814)

**Callers (both deploy paths thread the tier)**

- Publish path passes the already-loaded `ws.plan_tier`.
  [`deploy_app.py:197`](../../nowing_backend/app/services/web_builder/deploy/deploy_app.py#L197)
- Custom-domain redeploy reuses `ws.plan_tier` — no extra query, `None` → free.
  [`custom_domain.py:206`](../../nowing_backend/app/services/web_builder/deploy/custom_domain.py#L206)

**Network topology (self-host compose)**

- `proxy` joins the app bridge so ingress still resolves container names.
  [`docker-compose.yml:99`](../../docker/docker-compose.yml#L99)
- `nowing-web-apps-net` declaration + operator notes (name must equal the env var; icc caveat).
  [`docker-compose.yml:371`](../../docker/docker-compose.yml#L371)

**Tests & docs**

- New test classes: `TestWebBuilderTierLimits`, `TestContainerCgroupAndIsolation`, `TestDeployCallersThreadPlanTier`.
  [`test_deploy_service.py:623`](../../nowing_backend/tests/unit/services/web_builder/test_deploy_service.py#L623)
- Env vars documented for operators.
  [`docker/.env.example`](../../docker/.env.example)
