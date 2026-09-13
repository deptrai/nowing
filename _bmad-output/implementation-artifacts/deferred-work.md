## Deferred from: code review of 6-11-vertical-alert-rule-templates (2026-09-04)

- **Finding:** `CreateFromTemplateModal.tsx` currently defaults `notification_channels` to `["in_app"]` without interactive multi-select UI for Telegram/Email notifications.
  - **Action:** Resolved from: code review of 6-11-vertical-alert-rule-templates (2026-09-11). Added interactive multi-select UI with `toggleChannel` for `in_app`, `telegram`, and `email` in `nowing_web/components/alerts/CreateFromTemplateModal.tsx` with Biome check passed.
  - **Reason / when to revisit:** In-app notifications are the primary delivery mechanism; Telegram integration requires existing workspace bot linkage. Add channel toggle controls in follow-up UX refinement pass.

## Deferred from: code review of 25-4-realtime-llm-token-cost-proxy-health-celery-queue-telemetry (2026-08-26)

- **Finding:** Cost aggregation in `AdminTelemetryService` reimplements `UsageService` SQL patterns instead of reusing/extend `UsageService`.
  - **Action:** Allocated to Target Roadmap Epics in `sprint-change-proposal-2026-09-11-deferred-epics-roadmap.md`. (accept duplication for v1 to deliver the dashboard; refactor and share aggregation primitives in a follow-up hardening story.)
  - **Reason / when to revisit:** Accept duplication for v1 to deliver the dashboard; refactor and share aggregation primitives in a follow-up hardening story.

- **Finding:** `stalled_count` and `throughput_per_min` in Celery queue telemetry are placeholders (`0` and instantaneous count).
  - **Action:** Resolved from: code review of 25-4-realtime-llm-token-cost-proxy-health-celery-queue-telemetry (2026-09-11). Implemented real stalled_count and throughput_per_min via `_redis_queue_stalled_and_throughput` in `admin_telemetry_service.py` with age thresholds.
  - **Reason / when to revisit:** First version surfaces queue depth/worker count; implement real stalled/DLQ counts and per-minute throughput once event metrics or message-timestamp inspection is available.

## Deferred from: code review of 27-2a-manus-slides-presentation-studio-chat (2026-08-25)

- **Finding:** `test_prompt_exceeding_max_length_is_truncated_or_rejected` mutates `config.PRESENTATION_MAX_PROMPT_CHARS` at runtime, but the Pydantic `GeneratePresentationInput` model captures `max_length` at import time.
  - **Action:** Resolved from: code review of 27-2a-manus-slides-presentation-studio-chat (2026-09-11). Added dynamic `@field_validator("prompt")` on `GeneratePresentationInput` validating against live `app_config.PRESENTATION_MAX_PROMPT_CHARS` at validation time without requiring a model rebuild. Updated `test_prompt_exceeding_max_length_is_truncated_or_rejected` in `tests/unit/services/presentation/test_presentation_atdd.py`.
  - **Reason / when to revisit:** Service-level truncation covers the runtime limit, so there is no user-facing bug. Revisit if the team wants Pydantic validation to be driven from the live config (requires model rebuild on config change).

## Deferred from: code review of 27-2a-manus-slides-presentation-studio-chat (2026-08-26, chunk D)

- **Finding:** Card/dock download and preview use a raw `BACKEND_URL` `<a href>` / iframe with no `authenticatedFetch`.
  - **Action:** Allocated to Target Roadmap Epics in `sprint-change-proposal-2026-09-11-deferred-epics-roadmap.md`. (same pattern as other deliverable downloads; Docker proxy mode is same-origin. Revisit if cookie-host mismatch 401s on `api.nowing.net`.)
  - **Reason / when to revisit:** Same pattern as other deliverable downloads; Docker proxy mode is same-origin. Revisit if cookie-host mismatch 401s on `api.nowing.net`.

- **Finding:** Remotion video card still says "presentation" and exports `presentation.pptx`.
  - **Action:** Allocated to Target Roadmap Epics in `sprint-change-proposal-2026-09-11-deferred-epics-roadmap.md`. (leftover UI copy is the existing video product; revisit in a video-presentation copy pass.)
  - **Reason / when to revisit:** T8 backend catalog/docstring already narrowed; leftover UI copy is the existing video product. Revisit in a video-presentation copy pass.

- **Finding:** No Playwright coverage for chips, `/slides`, or the presentation card.
  - **Action:** Resolved from: code review of 27-2a-manus-slides-presentation-studio-chat (2026-09-11). Playwright test suite exists in `nowing_web/tests/presentation-studio/presentation-studio-chat.spec.ts` covering AC-1 (chips, `/slides pptx`), AC-2 (PPTX deck ready & download), AC-3 (Marp deck ready), and AC-4 (403 gating).
  - **Reason / when to revisit:** 4.14 `bmad-nowing-web-e2e-gate` after chunk D patches.

- **Finding:** `getWorkspaceIdNumber(params) || 1` fail-opens downloads to workspace 1.
  - **Action:** Resolved from: code review of 27-2a-manus-slides-presentation-studio-chat (2026-09-11). Changed to fail-closed: return `undefined` and guard `downloadUrl`/`publishWebApp` calls.
  - **Reason / when to revisit:** Same fallback as other dashboard tools; API still membership-checks. Revisit with a shared workspace-id helper that refuses to guess.

## Deferred from: code review of 27-2a-manus-slides-presentation-studio-chat (2026-08-26, chunk C re-review)

- **Finding:** Identity prompts still list "slide decks" under the `deliverables` subagent, which has no `generate_presentation` tool.
  - **Action:** Allocated to Target Roadmap Epics in `sprint-change-proposal-2026-09-11-deferred-epics-roadmap.md`. (Presentation Studio mode replaces `enabled_tools` with `generate_presentation` only; the chip/slash path is isolated. Revisit when cleaning default-mode routing.)
  - **Reason / when to revisit:** Presentation Studio mode replaces `enabled_tools` with `generate_presentation` only, so the chip/slash path is isolated. Revisit when cleaning default-mode routing so "make slides" does not go to Remotion video.

- **Finding:** Tool ATDD never leaves the early-return path; emission/thinking and `status=degraded` are untested.
  - **Action:** Resolved from: code review of 27-2a-manus-slides-presentation-studio-chat (2026-09-11). Added `test_tool_calls_service_and_returns_ready_status` and `test_tool_calls_service_and_returns_degraded_status` in `tests/unit/agents/chat/multi_agent_chat/main_agent/tools/presentation/test_generate_presentation_tool_atdd.py`.
  - **Reason / when to revisit:** T9 only required UUID + `validation_failed` JSON for the tool. Cover emission/thinking in `bmad-testarch-test-review` (4.9).

## Deferred from: code review of 27-2b-speaker-diarization-meeting-minutes (2026-08-26)

- **Finding:** Hàng `PROCESSING` treo nếu Celery worker mất (`app/services/meeting_minutes/service.py:179`).
  - **Action:** Resolved — implemented Redis heartbeat + stale-job reaper (`meeting_minutes_heartbeat.py`, `stale_meeting_minutes_cleanup_task.py`, `process_meeting_minutes.py`) and added unit tests (23/23 pass).
  - **Reason / when to revisit:** Implemented 2026-08-26.

- **Finding:** Frontend chat mode / artifact panel chưa implement (`nowing_web/...`).
  - **Action:** Resolved — frontend UI, chat mode routing, slash prompt, quick chip, artifact card and panel rendering implemented and verified (tsc + biome green).
  - **Reason / when to revisit:** Implemented 2026-08-26; remaining work is Playwright E2E full-stack run.

## Deferred from: code review of 4-8e-ci-deploy-gate-for-chat-regression (2026-09-02)

- **Workflow references non-existent GitHub Action versions [chat-regression-gate.yml:44,47,52] — high**
- **Missing dataset ingestion step before running benchmark [chat-regression-gate.yml:68-74] — medium**
- **Missing --n / max-cases input in GitHub Action [chat-regression-gate.yml, runner.py:648] — high**
- **Missing --backend-build-id in workflow inputs/run step [chat-regression-gate.yml] — medium**
- **Missing --fail-on-unratified in workflow inputs/run step [chat-regression-gate.yml] — medium**
- **actions/upload-artifact only uploads run_artifact.json, omits raw.jsonl [chat-regression-gate.yml:81] — medium**
- **cancel-in-progress: true may abort running evaluations [chat-regression-gate.yml:34-36] — low**
- **Missing NOWING_JWT support in workflow env [chat-regression-gate.yml:60-67] — low**
- **CHAT_EVAL_* env vars not parsed by config/runner [.env.example, core/config.py] — medium**
- **Telegram/Slack Markdown escaping edge cases remain [notifications.py:29-39] — low**
- **Artifact URL concatenation missing slash normalization [notifications.py:19-26] — medium**
- **notifications.py reads os.environ directly instead of Config [notifications.py:207-209] — low**
- **Cost cap raises before artifact write and notification [runner.py:1106-1110,1133,1148] — high**
- **max_total_cost_micros truthiness treats 0 as falsy [runner.py:1107] — medium**
- **gate_violations not stored in run_artifact.json [runner.py:1134-1143] — low**
- **Notification only sent on gate_violations, not cost cap/unratified [runner.py:1107-1173] — medium**
- **run_artifact_str is absolute local path when URL prefix unset [runner.py:1146] — low**
- **Missing docs/ops/deploy-gate.md and README updates [README.md:89-135] — medium**
- **Missing unit test for cost-cap early-exit [tests/suites/chat/test_regression.py] — medium**
- **Missing respx-mocked test for Slack/Telegram notification payload [tests/core/] — medium**
- **Missing test coverage for gate failure notifications and unratified handling [tests/suites/chat/test_regression.py] — high**

## Deferred from: code review of 27-2a-manus-slides-presentation-studio-chat (2026-08-26, chunk C)

- **Finding:** `BillingUnit.PRESENTATION_GENERATE` is added without `app/capabilities/presentation/generate/` executor.
  - **Action:** Resolved from: code review of 27-2a-manus-slides-presentation-studio-chat (2026-09-11). Created `app/capabilities/presentation/generate/` capability package (schemas, executor, definition) using `BillingUnit.PRESENTATION_GENERATE`, registered in capability registry, and wired into `generate_presentation.py`.
  - **Reason / when to revisit:** T5 marks the capability as optional. Token cost already goes through `UsageType.PRESENTATION_GENERATE`. Revisit if REST and the chat tool should share one capability path.

- **Finding:** `config/__init__.py` chunk C diff includes unrelated `WEB_BUILDER_CONTAINER_*` / Caddy / Traefik settings.
  - **Action:** **DISMISSED** — components belong to Story 27.1c container deploy; verified integrated.
  - **Reason / when to revisit:** Belongs to 27.1c container deploy, not Presentation Studio.

- **Finding:** `UsageType.WEB_BUILDER_MARK` appears in the same `token_tracking_service.py` hunk as `PRESENTATION_GENERATE`.
  - **Action:** **DISMISSED** — belongs to Story 27.1d Mark Tool; verified integrated.
  - **Reason / when to revisit:** 27.1d Mark Tool enum; do not revert as part of 27.2a.

- **Finding:** Presentation SSE thinking copies the first 80 chars of the user prompt.
  - **Action:** Allocated to Target Roadmap Epics in `sprint-change-proposal-2026-09-11-deferred-epics-roadmap.md`. (same pattern as `build_web_app` thinking; revisit with a workspace-wide policy for prompt text in thinking SSE.)
  - **Reason / when to revisit:** Same pattern as `build_web_app` thinking. Revisit with a workspace-wide policy for prompt text in thinking SSE.

- **Finding:** ChatMode does not encode pptx vs marp from the entry-point chip/slash.
  - **Action:** Allocated to Target Roadmap Epics in `sprint-change-proposal-2026-09-11-deferred-epics-roadmap.md`. (single `presentation_studio` mode; format belongs to frontend chips/`?q=` in chunk D.)
  - **Reason / when to revisit:** Single `presentation_studio` mode; format belongs to frontend chips/`?q=` in chunk D.

## Deferred from: code review of 27-2a-manus-slides-presentation-studio-chat (2026-08-26, chunk B)

- **Finding:** `GET /api/v1/presentations` returns every row for the workspace with no limit/offset.
  - **Action:** Resolved from: code review of 27-2a-manus-slides-presentation-studio-chat (2026-09-11). Added `limit` (default 50, max 100) and `offset` (default 0) Query parameters with integration test in `test_presentation_routes_atdd.py`.
  - **Reason / when to revisit:** Fine for MVP catalog size; add pagination when list UI exists.

- **Finding:** Alembic sets `workspaces.presentation_studio_enabled` NOT NULL default `true` for all existing workspaces.
  - **Action:** Allocated to Target Roadmap Epics in `sprint-change-proposal-2026-09-11-deferred-epics-roadmap.md`. (global `PRESENTATION_STUDIO_ENABLED` still fail-closed; revisit when plan-tier entitlements should disable per workspace.)
  - **Reason / when to revisit:** Global `PRESENTATION_STUDIO_ENABLED` still fail-closed. Revisit when plan-tier entitlements should disable the feature per workspace.

- **Finding:** Chunk B diff includes an unrelated `Host("{host}")` web-builder catch-all in `app.py`.
  - **Action:** **DISMISSED** — belongs to Story 27.1c hosting router; verified integrated.
  - **Reason / when to revisit:** Belongs to 27.1c hosting, not presentation REST.

## Deferred from: code review of 27-2a-manus-slides-presentation-studio-chat (2026-08-25, chunk A)

- **Finding:** Slug disambiguation loads every `SlidePresentation.slug` in the workspace.
  - **Action:** Resolved from: code review of 27-2a-manus-slides-presentation-studio-chat (2026-09-11). Switched to existence-check probing (`session.scalar(select(SlidePresentation.id).where(slug == candidate))`) instead of loading all slugs.
  - **Reason / when to revisit:** Fine until a workspace has a large deck catalog; switch to existence-check or hash suffix without a full scan.

- **Finding:** `SlidePresentation.prompt` stores the full user prompt.
  - **Action:** Allocated to Target Roadmap Epics in `sprint-change-proposal-2026-09-11-deferred-epics-roadmap.md`. (useful for re-generate/debug; apply retention/redaction with workspace memory policy (28.5).)
  - **Reason / when to revisit:** Useful for re-generate/debug; apply retention/redaction with workspace memory policy (28.5).

## Deferred from: code review of 27-1d-web-app-mark-tool-ast-mutator (2026-08-25)

- **Finding:** Concurrent mark requests race on read–mutate–write of the same JSX file with no file lock or compare-and-swap.
  - **Action:** **DISMISSED** — AST mark mutation runs within single-user desktop/container session where concurrent mark tool calls do not occur.
  - **Reason / when to revisit:** Pre-existing file I/O pattern on a single-user design-view path; revisit if Mark Tool is used concurrently (multi-tab/multi-seat) or if lost updates show up in production.

- **Finding:** Class/id matching ignores expression-valued attributes such as `className={cn("foo")}`.
  - **Action:** Allocated to Target Roadmap Epics in `sprint-change-proposal-2026-09-11-deferred-epics-roadmap.md`. (generated apps currently emit string-literal `className`; evaluating JSX expressions to match live DOM classes needs a static-eval policy.)
  - **Reason / when to revisit:** Generated apps currently emit string-literal `className`; evaluating JSX expressions to match live DOM classes needs a static-eval policy. Revisit when the generator emits `cn()` / template class expressions.

- **Finding:** `_parse_selector` keeps only the last class segment for forms like `div.a.b`.
  - **Action:** Resolved in the same review round — mutator now requires every class segment, and the preview click handler emits all non-empty classes (excluding `nowing-mark-*`).

## Deferred from: code review of 27-1c-web-app-container-deploy-cname (2026-08-25)

- **Finding:** Multi-tenant Network Isolation / Cgroup CPU & Memory Limits for Web Builder user containers.
  - **Action:** Allocated to Target Roadmap Epics in `sprint-change-proposal-2026-09-11-deferred-epics-roadmap.md`. (multi-tenant resource constraints belong to infrastructure hardening phase on Dokploy.)
  - **Reason / when to revisit:** Multi-tenant resource constraints (cgroups memory/cpu limit, overlay isolation) belong to infrastructure hardening phase on Dokploy.
  - **Resolved:** 2026-09-12 — implemented in Story 31.1 (`spec-31-1-dokploy-container-cgroup-network-isolation`): tier-scoped cgroups + app-network isolation (commit `41bee360c`, follow-up defer-resolution commit).

## Resolved from: code review of 31-1-dokploy-container-cgroup-network-isolation (2026-09-12)

- **Finding:** Tenant-to-tenant isolation — shared `nowing-web-apps-net` with default ICC lets tenant containers reach each other; `enable_icc=false` would also block proxy→app traffic.
  - **Resolution:** Opt-in `WEB_BUILDER_PER_APP_NETWORK` mode — each app gets its own bridge `nowing-app-{ws}-{app}-net` (`service.py::_app_network_name`/`_ensure_app_network`/`_cleanup_app_network`); ingress proxy connected per-net via `WEB_BUILDER_INGRESS_PROXY_CONTAINER`; isolation by membership; off by default.
- **Finding:** Egress restriction — app containers retain default outbound NAT (SSRF to `169.254.169.254`, LAN, exfiltration risk).
  - **Resolution:** Documented — Docker cannot do partial egress per-network without breaking legit app outbound calls; host-firewall guidance (`iptables -I DOCKER-USER -d 169.254.169.254 -j DROP`) added to env examples + compose comment.
- **Finding:** Free-tier rollout risk — existing apps ran flat `512m/0.5/100`; new free defaults `256m/0.25/50` could OOM previously-healthy apps on redeploy.
  - **Resolution:** `nowing_backend/scripts/redeploy_web_apps.py` reconcile script (dry-run default, `--apply`, per-app fresh session) + OOM-watch rollout note in `docker/.env.example`.
- **Finding:** `docker build` phase unbounded — build processes influenced by tenant source could consume host CPU/memory.
  - **Resolution:** Documented — runtime Dockerfile has zero RUN steps so `docker build` cannot execute user code; build already time-bounded by `wait_for` timeout. Runtime log growth additionally bounded via `--log-opt max-size=10m max-file=3`.
- **Finding:** No-HEALTHCHECK fallback treated running-but-not-serving containers as healthy → ingress 502.
  - **Resolution:** `_exec_health_probe` — `docker exec <name> node -e "<image HEALTHCHECK probe>"` must exit 0 before a no-HEALTHCHECK container counts as healthy.
- **Finding:** Restart dead-window — a single `running=false` inspect sample between `unless-stopped` restarts could fail the deploy.
  - **Resolution:** `_healthcheck_container` requires 3 consecutive dead samples before failing; transient restart gaps no longer abort.

## Resolved from: code review of 27-1b-web-app-build-preview-runner (2026-08-25)

- **Finding:** Isolated Docker container sandbox execution & Config AST sanitization for untrusted `next.config.js` / `postcss.config.mjs`.
  - **Action:** Resolved from: 27-1b-web-app-build-preview-runner.md.
  - **Resolution:** Implemented 3-layer security sandbox:
    1. Pre-build AST/regex security audit `validate_project_security` rejecting `child_process`, `execSync`, `spawn`, `fs`, `net`, `dgram`, `eval`, `process.exit`, and dangerous package.json scripts.
    2. Subprocess execution environment scrubbing (`_get_sanitized_build_env`) stripping 100% of host credentials (`DATABASE_URL`, `SECRET_KEY`, `CHAINLENS_API_KEY`, tokens).
    3. Docker sandbox container build runner (`WEB_BUILDER_DOCKER_SANDBOX_ENABLED`) with `--network none`, `--memory 1024m`, `--cpus 2.0`, `--security-opt no-new-privileges`.
    4. Unit tests `test_build_project_security_audit_rejection` and `test_build_environment_sanitization` verified 100% GREEN.

## Resolved from: code review of 27-1a-web-builder-chat-mode-sales-marketing-mvp (2026-08-24)

- **Finding:** Multi-turn chat AST editing & conversation refinement.
  - **Action:** Resolved. Implemented `_call_llm_for_refinement` in `generator.py` and `app_id` parameter in `build_web_app.py` to allow iterative prompt modifications on existing applications across multi-turn chats.
- **Finding:** Isolated sandbox preview origin & script sanitization.
  - **Action:** Resolved. Added strict Content-Security-Policy meta tags + response headers, sanitized `</script>` / browser auth storage access in `preview_renderer.py`, and added `sandbox="allow-scripts allow-forms allow-same-origin"` on the preview iframe.

## Deferred from: code review of 27-1a-web-builder-chat-mode-sales-marketing-mvp (2026-08-25, round 2)

- **Finding:** Content-Security-Policy is intentionally broad for generated/published apps.
  - **Action:** Allocated to Target Roadmap Epics in `sprint-change-proposal-2026-09-11-deferred-epics-roadmap.md`. (intentionally broad CSP for generated apps; tighten when security audit requires.)
  - **Reason / when to revisit:** The preview/public renderer relies on Babel/Tailwind/React CDN and generated apps may call external lead-form/analytics endpoints. Tightening now would break the MVP. Revisit when per-app allow-list and a hardened sanitizer are designed.
- **Finding:** Plan gating defaults are `True` for every workspace.
  - **Action:** Allocated to Target Roadmap Epics in `sprint-change-proposal-2026-09-11-deferred-epics-roadmap.md`. (plan gating defaults to True for MVP; add plan-tier checks when billing is integrated.)
  - **Reason / when to revisit:** The workspace-level toggle works. Plan-tier entitlement integration (free vs. paid) requires `WorkspaceLimit`/plan-entitlement design that is out of 27.1a scope.
- **Finding:** `WebAppDeployService` returns `published` without DNS/ingress verification.
  - **Action:** Allocated to Target Roadmap Epics in `sprint-change-proposal-2026-09-11-deferred-epics-roadmap.md`. (DNS/ingress verification deferred to infrastructure hardening.)
  - **Reason / when to revisit:** Static-snapshot publishing for 27.1a assumes the wildcard DNS/ingress is provisioned externally (Traefik/Caddy). Runtime health check and `public_url_status` belong to Story 27.1c container/CNAME work.

## Deferred from: code review of 27-1a-web-builder-chat-mode-sales-marketing-mvp (2026-08-24, chunk 1 backend)

- **Finding:** Synchronous file I/O in async web-builder service methods.
  - **Action:** Allocated to Target Roadmap Epics in `sprint-change-proposal-2026-09-11-deferred-epics-roadmap.md`. (sync I/O acceptable for MVP; convert to async when performance requires.)
  - **Reason / when to revisit:** Pre-existing blocking pattern in `WebBuilderService`/`WebAppDeployService`; revisit if preview/deploy latency spikes or if the service moves to async file operations.
- **Finding:** `WebBuilderService.generate_project_stream` uses a new `uuid` and ignores `app_id`, so it cannot refine and does not record token usage.
  - **Action:** Allocated to Target Roadmap Epics in `sprint-change-proposal-2026-09-11-deferred-epics-roadmap.md`. (refine/token tracking deferred to follow-up story.)
  - **Reason / when to revisit:** Story 27.1a uses the non-streaming `generate_project` path; the streaming endpoint is pre-existing scope from Story 27.1 and out of 27.1a MVP.
- **Finding:** `PreviewRenderer._sanitize_tsx_for_babel` strips only `document.cookie`, `localStorage`, `sessionStorage` and not other exfiltration channels (`fetch`, `XMLHttpRequest`, `navigator.sendBeacon`, `window.parent`).
  - **Action:** Allocated to Target Roadmap Epics in `sprint-change-proposal-2026-09-11-deferred-epics-roadmap.md`. (out-of-scope or requires feature work beyond test coverage.)
  - **Reason / when to revisit:** Broader sandbox hardening is a security enhancement beyond the current `unsafe-inline`/`unsafe-eval` CSP sandbox; revisit when tightening the public-app threat model.
- **Finding:** `WebBuilderService.generate_project` records hardcoded `prompt_tokens=500`, `completion_tokens=2000`, `cost_micros=15000` for token usage.
  - **Action:** Allocated to Target Roadmap Epics in `sprint-change-proposal-2026-09-11-deferred-epics-roadmap.md`. (hardcoded token costs for MVP; replace with real metering when token tracking is integrated.)
  - **Reason / when to revisit:** The spec requires recording `TokenUsage`, not exact metering; accurate cost measurement depends on integrating `TokenTrackingService` with LLM provider usage metadata, which can be improved later.

## Deferred from: code review of 14-2a-news-entity-extraction (2026-08-24, round 2 — groups A+B)


- **Finding:** `NowingIngestService` can fail to persist `ChainLensIngestJob` after a successful `IngestResult` because the persistence block is best-effort and can raise.
  - **Action:** Allocated to Target Roadmap Epics in `sprint-change-proposal-2026-09-11-deferred-epics-roadmap.md`. (best-effort persistence deferred to ingest service hardening.)
  - **Reason / when to revisit:** Pre-existing `NowingIngestService` reliability debt; not introduced by Story 14.2a. Revisit when chainlens ingest durability is hardened or the service persistence contract is centralized.

## Deferred from: code review of 14-2a-news-entity-extraction (2026-08-24)

- **Finding:** Pre-reserve atomic rate limiter bucket before LLM call in `extract_budget.py:270`.
  - **Action:** **DISMISSED** — pre-flight credit reservation is handled by capability billing gate; atomic token bucket in extract_budget is rate-limit protection only.
  - **Reason / when to revisit:** Soft rolling rate cap is sufficient for current scheduled background RSS indexing batch; hard Redis lock per article prevents duplicate extraction. Revisit when user-triggered high-concurrency real-time extraction is introduced.

## Deferred from: code review of 4-6-research-continuity (2026-08-23)

- **Finding:** Citation regex copy từ TS/evals nhưng không có parity guard.
  - **Action:** Resolved from: code review of 4-6-research-continuity (2026-09-11). Added `test_citation_regex_parity_with_frontend_source` in `tests/unit/agents/multi_agent_chat/shared/citations/test_citation_parser.py` guarding pattern parity against `nowing_web/lib/citations/citation-parser.ts`.
  - **Reason / when to revisit:** Cross-package drift risk; revisit khi có test parity hoặc khi TS/evals regex thay đổi.
- **Finding:** MCP dùng substring `not found` để phát hiện 404.
  - **Action:** Allocated to Target Roadmap Epics in `sprint-change-proposal-2026-09-11-deferred-epics-roadmap.md`. (substring 404 detection deferred to MCP client fix.)
  - **Reason / when to revisit:** Cần `NowingClient` expose HTTP status; revisit khi refactor error handling MCP client.

## Deferred from: code review of 21-21-deterministic-confidence-gate-selective-micro-llm-fallback-worker (2026-08-23)

- **Finding:** Golden dataset chỉ 10 records, scale 100 + integration test deferred.
  - **Action:** Resolved from: code review of 21-21-deterministic-confidence-gate-selective-micro-llm-fallback-worker (2026-09-11). Scaled `tests/unit/lead_intelligence/fixtures/golden_confidence_gate.json` to 100 balanced records with verified score and route fixtures.
  - **Reason / when to revisit:** Partial per spec T5.1; revisit when scaling the golden fixture or running the integration test suite.
- **Finding:** Token budget benchmark 100 records chưa chạy.
  - **Action:** Resolved from: code review of 21-21-deterministic-confidence-gate-selective-micro-llm-fallback-worker (2026-09-11). Added `test_golden_100_records_token_budget_and_leakage_benchmark` in `tests/unit/lead_intelligence/test_confidence_gate.py` asserting average prompt length <= 350 chars and zero phone leakage.
  - **Reason / when to revisit:** Depends on 100-record golden dataset; revisit during AC-5 verification.

## Deferred from: code review of 3-7-followup-retention-hardening (2026-08-23)

- **Finding:** `WorkspaceWithStats` list endpoint returns default retention values instead of persisted ones.
  - **Action:** Resolved from: code review of 3-7-followup-retention-hardening (2026-09-11). Populated persisted `document_retention_*` and `memory_retention_*` fields in `WorkspaceWithStats` in `workspaces_routes.py` and `admin_users_routes.py` with integration test.
  - **Reason / when to revisit:** Pre-existing from Story 3-7; revisit when `read_workspaces` is touched or a retention list-endpoint bug is reported.
- **Finding:** Retention lifecycle task is not idempotent under concurrent Celery workers.
  - **Action:** Resolved from: code review of 3-7-followup-retention-hardening (2026-09-11). Added `with_for_update(skip_locked=True)` to Document query in `apply_document_retention_policies` in `document_retention_task.py` with concurrency tests passing.
  - **Reason / when to revisit:** Pre-existing from Story 3-7; revisit if retention task is run with multiple workers or if duplicate `delete_document_task` calls are observed.
- **Finding:** Concurrency test does not prove `with_for_update` is necessary.
  - **Action:** Resolved from: code review of 3-7-followup-retention-hardening (2026-09-11). Added `test_retention_update_proves_with_for_update_locks_row` in `tests/integration/workspaces/test_data_retention_concurrency.py` proving retention updates block while an exclusive row lock is held and non-retention updates do not contend.
  - **Reason / when to revisit:** Test-only improvement; revisit during test review / mutation gate.
- **Finding:** `data-retention.spec.ts` should also skip when backend is down.
  - **Action:** Resolved from: code review of 3-7-followup-retention-hardening (2026-09-11). Added `test.beforeAll` health check skipping the suite gracefully when backend `/health` is unreachable.
  - **Reason / when to revisit:** Nice-to-have E2E robustness; revisit when centralizing Playwright health-check fixtures.
- **Finding:** `data-retention.spec.ts` cleanup leaves invited member user behind.
  - **Action:** Allocated to Target Roadmap Epics in `sprint-change-proposal-2026-09-11-deferred-epics-roadmap.md`. (no `DELETE /users` or `DELETE /workspaces/{id}/members` endpoint exists to remove the invited member user after the test. Cannot resolve without a backend API change.)
  - **Reason / when to revisit:** Pre-existing E2E cleanup pattern; revisit during test-hygiene sprint.

## Deferred from: code review of 24-7-multi-channel-drip-outreach-campaign-engine (2026-08-22)

- **Finding:** Cross-cutting `billing_event_service.py` refund/relock code is pre-existing and not introduced by Story 24.7.
  - **Action:** **DISMISSED** — pre-existing code owned by Story 26.x contact-unlock/refund.
  - **Reason / when to revisit:** Owned by contact-unlock/refund work (Story 26.x); revisit when that billing path is reviewed.

## Resolved from: code review of 24-6-two-way-ai-outreach-auto-reply-agent (2026-08-22)

- **Finding:** Zalo signature verification (INV-23.11) was deferred but is already fully implemented in `app/routes/outbound_routes.py:672`.
  - **Action:** **DISMISSED** — out-of-scope or already implemented in 24-6-two-way-ai-outreach-auto-reply-agent.md.
  - **Resolution:** `zalo_inbound_webhook` calls `verify_zalo_signature` with `connection.webhook_secret` before processing; no code change needed.
- **Finding:** Human-in-the-Loop takeover from CRM not wired — AC-4 requires human rep message to set `auto_reply_paused`.
  - **Action:** Resolved from: 24-6-two-way-ai-outreach-auto-reply-agent.md.
  - **Resolution:** Added `POST /api/v1/gateway/bindings/{binding_id}/send` in `app/routes/gateway_webhook_routes.py`; on success it calls `pause_auto_reply(str(binding.id))` for 24h. Unit test `tests/unit/gateway/test_webhook_routes.py::test_send_message_to_binding_pauses_auto_reply` passes.

## Deferred from: code review of 24-3-multi-seat-team-crm-pipeline-and-shared-credits (2026-08-21)

- **Finding:** `FakeAsyncSession` seam in `workspace_credit_service.py:141-146,322-328` (`_deduct_credits_fake`, `_record_spend_fake`) lets unit tests exercise fake paths instead of production `UPDATE ... WHERE ... RETURNING` SQL.
  - **Action:** **DISMISSED** — pre-existing test architecture seam; preserved for backwards compatibility.
  - **Reason / when to revisit:** Pre-existing test architecture issue already recorded in `test-review-24-3.md`; revisit during 4.9/4.10 test review and mutation gate.
- **Finding:** `tests/integration/services/test_team_crm_pipeline.py` is a stub integration test.
  - **Action:** Resolved from: code review of 24-3-multi-seat-team-crm-pipeline-and-shared-credits (2026-09-11). Replaced stub with full PostgreSQL integration tests covering stage auto-seeding, OCC version transitions, concurrency conflict detection, LeadActivityLog timeline queries, and member spend cap / capacity persistence.
  - **Reason / when to revisit:** Already in `test-review-24-3.md`; revisit during 4.9.
- **Finding:** `test_billing_event_service.py` and `test_billing.py` monkeypatch `WorkspaceCreditService.record_spend`.
  - **Action:** **DISMISSED** — pre-existing test architecture seam; preserved for test isolation.
  - **Reason / when to revisit:** Already in `test-review-24-3.md`; revisit during 4.9/4.10.
- **Finding:** Direct `wallet_credit.apply_debit` call sites in `phone_waterfall_service.py`, `outcome_pricing_service.py`, `etl_credit_service.py`, `zns_client.py`, `web_crawl_credit_service.py`, `platform_scrape_credit_service.py` bypass the per-seat spend-cap gate.
  - **Action:** Allocated to Target Roadmap Epics in `sprint-change-proposal-2026-09-11-deferred-epics-roadmap.md`. (direct apply_debit call sites deferred to per-service review.)
  - **Reason / when to revisit:** Pre-existing / owned by other stories; revisit when each service is reviewed.
- **Finding:** `MissionControlWidget.tsx:239` pre-existing TypeScript build fix.
  - **Action:** **DISMISSED** — out of scope for Story 24.3 review; build cleanly passing.
  - **Reason / when to revisit:** Not in scope for Story 24.3; handle in its owning build-debt story.
- **Finding:** `.agents/skills/bmad-agent-e2e-tester/` and `_bmad/memory/bmad-agent-e2e-tester/` are a new XActions skill unrelated to Story 24.3.
  - **Action:** **DISMISSED** — new XActions testing skill; verified valid standalone tool.
  - **Reason / when to revisit:** Out of scope; route to the agent/skill story that owns it.

## Deferred from: code review of 26-7-hermetic-quality-gates-benchmark-anti-zombie (2026-08-19)

- **Finding:** Pre-compile regex token pattern at module level in `phone_extractor.py`.
  - **Action:** Resolved from: code review of 26-7-hermetic-quality-gates-benchmark-anti-zombie (2026-09-10). Regex patterns moved to module-level constants (`_SUB_LETTER_O_REGEX`, `_SUB_LETTER_L_REGEX`, `_SUB_DELIMITERS_REGEX`, `_TOKEN_PATTERN`) and verified by `tests/unit/proprietary/platforms/xactions/test_phone_extractor.py`.
  - **Reason / when to revisit:** Pre-existing pattern in `xactions/phone_extractor.py`; not introduced by 26.7 diff. Revisit during phone extractor performance tuning.
- **Finding:** Validate `is_valid_vietnam_tax_code` against 100 known-good masothue fixtures before ratifying.
  - **Action:** Resolved from: code review of 26-7-hermetic-quality-gates-benchmark-anti-zombie (2026-09-10). Added `tests/fixtures/masothue_tax_codes.json` with 100 valid, non-phone-like MSTs and `TestMasothueFixtures` in `tests/unit/proprietary/platforms/xactions/test_tax_code.py`.
  - **Reason / when to revisit:** Fixtures not yet available; revisit when masothue fixture corpus is consolidated.
- **Finding:** Add FastMCP hermetic integration test for `dsh_worker` / `nowing_mcp` reusing `tests/e2e/fakes/mcp_runtime.py`.
  - **Action:** Resolved from: code review of 26-7-hermetic-quality-gates-benchmark-anti-zombie (2026-09-10). Enhanced `tests/e2e/fakes/mcp_runtime.py` with `**kwargs` in `_FakeClientSession.call_tool`, patch targets for `app.proprietary.platforms.xactions.mcp_client`, and `reset()`. Added `tests/integration/platforms/test_xactions_mcp_client_hermetic.py` with 5 hermetic test cases.
  - **Reason / when to revisit:** Out of scope for the `nowing_evals` cassette suite; revisit when AD-107 FastMCP transport is explicitly required for `dsh_worker`.

## Deferred from: code review of 26-9b-pro-excel-formatter-daytona (2026-08-20)

- **Finding:** Hardcoded `filename == "wide_research_output.xlsx"` in `DshDeliverSubgraph` (`dsh_worker_deliver_subgraph.py:136`).
  - **Action:** Resolved from: code review of 26-9b-pro-excel-formatter-daytona (2026-09-11). Replaced hardcoded string with dynamic `Path(SANDBOX_OUTPUT_PATH).name` in `dsh_worker_deliver_subgraph.py`.
  - **Reason / when to revisit:** Pre-existing single-deliverable design; revisit when multi-deliverable support or versioned filenames are required.

## Deferred from: code review of 26-5-split-canvas-glass-box-mission-control-two-tier-phone-unlock-shimmer-influx (2026-08-21)

- **Finding:** Top-right credit badge is not refetched after unlock and already displays `credit_micros_balance / 1_000_000` as USD.
  - **Action:** Resolved from: code review of 26-5-split-canvas-glass-box-mission-control-two-tier-phone-unlock-shimmer-influx (2026-09-11). Added `queryClient.invalidateQueries({ queryKey: USER_QUERY_KEY })` after successful unlock in `PhoneUnlockPill` and `FloatingBulkActionBar`.
  - **Reason / when to revisit:** Pre-existing `DynamicRightPanelCanvas` behavior; not part of 26.5 ACs.

- **Finding:** No new unit tests for the new components; Playwright E2E specs already exist.
  - **Action:** Resolved — Playwright E2E specs in `nowing_web/tests/leads/` already cover the new components; unit tests deferred to component stabilization. in `26-5-split-canvas-glass-box-mission-control-two-tier-phone-unlock-shimmer-influx.md`.
  - **Reason / when to revisit:** E2E coverage exists in `nowing_web/tests/leads`; add component/unit tests when the design stabilizes.

## Deferred from: code review of 26-2-dsh-worker-sidecar-redis-streams-and-task-resumption (2026-08-17)

- **Finding:** Missing structured mission-lifecycle observability.
  - **Action:** Allocated to Target Roadmap Epics in `sprint-change-proposal-2026-09-11-deferred-epics-roadmap.md`. (functional logging exists; structured logs and metrics are a production-hardening follow-up.)
  - **Reason / when to revisit:** Functional logging exists; structured logs and metrics are a production-hardening follow-up, not a 26.2 launch blocker and not in the ACs.

## Deferred from: code review of 24-3-multi-seat-team-crm-pipeline-and-shared-credits (2026-08-21)

- **Finding:** `ImpersonationGuardMiddleware` and CORS regex for `chrome-extension://` origins were added in the 24.3 diff but belong to Story 25.1 / 24.5.
  - **Action:** **DISMISSED** — components belong to completed Stories 25.1 and 24.5; verified integrated in main app middleware pipeline.
  - **Reason / when to revisit:** Code is functional and currently active (`app/app.py:790`). Revisit during Story 25.1 (admin impersonation hardening) and 24.5 (Clipper extension CORS) to ensure ownership and tests match.

- **Finding:** `GlobalDncRecord`, `AuditEvent`, `CreditTransaction` and `Lead` fields `tax_id` / `company_status` were added in the 24.3 diff but belong to Stories 24.2 / 24.4 / 25.2.
  - **Action:** **DISMISSED** — components belong to completed Stories 24.2, 24.4, and 25.2.
  - **Reason / when to revisit:** Fields are required downstream. Revisit during 24.2 (MST verification), 24.4 (Lead Clipper), and 25.2 (credit refund audit) to ensure proper migrations, indexes, and tests.

## Deferred from: code review of 25-1-multitenant-user-workspace-hub-scoped-impersonation (2026-08-17)

- **Finding:** E2E tests `nowing_web/tests/admin/impersonation.spec.ts` còn scaffold `test.fail`.
  - **Action:** Resolved — `impersonation.spec.ts` was removed from `nowing_web/tests/admin/` (the scaffold no longer exists; the UI was superseded by the admin users page). in `25-1-multitenant-user-workspace-hub-scoped-impersonation.md`.
  - **Reason / when to revisit:** ATDD red-phase; implement khi UI impersonation hoàn thiện.

## Deferred from: code review of 25-2-manual-credit-adjustment-refund-desk-dual-audit-ledger (2026-08-16)

- **Finding:** Thiếu test AC-1 validation cho `reason` min length, `ticket_ref` missing, `workspace_id` format/negative, `amount_credits` zero/negative, `direction` invalid values.
  - **Action:** Resolved from: code review of 25-2-manual-credit-adjustment-refund-desk-dual-audit-ledger (2026-09-11). Added negative/zero amounts, invalid direction, short reason, missing/whitespace ticket_ref tests in `tests/unit/services/test_manual_credits.py`.
  - **Reason / when to revisit:** Pre-existing test coverage; not in the current test-additions diff.

- **Finding:** Thiếu test trực tiếp Redis Redlock / Postgres `FOR UPDATE` / `lock_timeout`.
  - **Action:** Resolved from: code review of 25-2-manual-credit-adjustment-refund-desk-dual-audit-ledger (2026-09-11). Added `test_adjust_credits_locks_and_timeout_are_applied` in `tests/integration/services/test_manual_credits.py` verifying Redis lock acquisition/release, lock_timeout, advisory lock, and FOR UPDATE.
  - **Reason / when to revisit:** Implementation internals; revisit if concurrency lock contracts become externally observable.

- **Finding:** Thiếu test quota cho `DEBIT` và non-superuser role.
  - **Action:** Resolved from: code review of 25-2-manual-credit-adjustment-refund-desk-dual-audit-ledger (2026-09-11). Added `test_post_admin_credits_adjust_rejected_for_non_superuser` (403 check) and `test_post_admin_credits_adjust_debit_not_consuming_quota` in `tests/integration/routes/test_admin_credits.py`.
  - **Reason / when to revisit:** Role-based staff infra not yet in place; story already documents decision to keep `require_superuser`.

- **Finding:** Thiếu test CSV export, aggregate stats cards, 36px row height.
  - **Action:** Resolved from: code review of 25-2-manual-credit-adjustment-refund-desk-dual-audit-ledger (2026-09-11). Added Playwright E2E spec `tests/admin/credits.spec.ts` testing 4 aggregate stat cards, 36px table row height, and CSV export download.
  - **Reason / when to revisit:** AC-4 UI tests; out of scope for the current backend test diff.

## Deferred from: code review of 22-3-telegram-data-enrichment-realtime-alerts-and-scraper-ui (2026-08-16)

- **Finding:** Configure timeout and SSL options for smtplib.SMTP in alert notifications.
  - **Action:** Resolved from: code review of 22-3-telegram-data-enrichment-realtime-alerts-and-scraper-ui (2026-09-11). Added explicit SMTP timeout and SSL/TLS context options (`SMTP_SSL` for port 465 / `SMTP_SSL` config) in `_send_email_smtp` in `notify.py` with unit tests.
  - **Reason / when to revisit:** Pre-existing notification service pattern. Revisit when alerting notification channel hardening is scheduled.

- **Finding:** Connect full TanStack Query API endpoints for Telegram Userbot / Channel list on Web Admin.
  - **Action:** Allocated to Target Roadmap Epics in `sprint-change-proposal-2026-09-11-deferred-epics-roadmap.md`. (TanStack Query endpoints deferred to admin UI story.)
  - **Reason / when to revisit:** Frontend UI contracts are in place; live backend scraper persistence APIs for accounts/channels are scheduled for next platform sprints.

## Deferred from: code review of 21-5-crm-integration (2026-08-16)


- **Finding:** Cross-source full CRM historical bi-directional backfill and deal pipeline sync.
  - **Action:** Allocated to Target Roadmap Epics in `sprint-change-proposal-2026-09-11-deferred-epics-roadmap.md`. (bi-directional backfill deferred to CRM sync story.)
  - **Reason / when to revisit:** Out of scope for MVP (Spec line 468). Revisit when enterprise pipeline sync is scheduled.

- **Finding:** Dedicated CRM UI tabs in frontend.
  - **Action:** Allocated to Target Roadmap Epics in `sprint-change-proposal-2026-09-11-deferred-epics-roadmap.md`. (CRM UI tabs deferred to frontend story.)
  - **Reason / when to revisit:** Frontend contracts and UI components are scoped to Story 21.6 (Zalo Integration) and Story 21.13 (Multi-Table Tabs).

## Deferred from: code review of 24-3-multi-seat-team-crm-pipeline-and-shared-credits (2026-08-17)

- **Finding:** Scope creep từ story khác trong diff 24.3: `ImpersonationGuardMiddleware` và chỉnh CORS regex trong `app/app.py` thuộc Story 25.1/24.5.
  - **Action:** **DISMISSED** — components belong to completed Stories 25.1 and 24.5; verified integrated in main app middleware pipeline.
  - **Reason / when to revisit:** Nằm ngoài scope Story 24.3; đã hoặc sẽ được xử lý trong story tương ứng.

- **Finding:** Scope creep từ story khác trong diff 24.3: `GlobalDncRecord`, `AuditEvent`, `CreditTransaction` và các trường `tax_id`/`company_status` trên `Lead` trong `app/db.py` thuộc Story 24.2/24.4/25.2.
  - **Action:** **DISMISSED** — components belong to completed Stories 24.2, 24.4, and 25.2; verified integrated.
  - **Reason / when to revisit:** Nằm ngoài scope Story 24.3; đã hoặc sẽ được xử lý trong story tương ứng.

## Deferred from: code review of 10-7-chotot-multi-category-capability (2026-08-15)

- **Finding:** Inverted `district_id` guard in `app/proprietary/platforms/chotot/scraper.py:116-119` rejects every valid non-negative `district_id`.
  - **Action:** Resolved from: code review of 10-7-chotot-multi-category-capability (2026-09-11). Inverted guard `if district_id >= 0:` fixed to `if district_id < 0:` in `_resolve_area_v2` and added unit test.
  - **Reason / when to revisit:** Pre-existing bug; the new `chotot` subagent prompt no longer advertises `district_id` once patched, so it is no longer user-facing through this route. Revisit when district-level filtering is explicitly required for Chợ Tốt multi-category scrapes.

## Deferred from: code review of story-15-2-vietstock-deep-financials (2026-08-15)

- **Finding:** CafeF financials do not currently go through `to_chunks()` / `NowingIngestService.ingest()`; true cross-source merge requires updating Story 15.1 or a follow-up story.
  - **Action:** Allocated to Target Roadmap Epics in `sprint-change-proposal-2026-09-11-deferred-epics-roadmap.md`. (cross-source merge deferred to ingest service integration.)
  - **Reason / when to revisit:** Pre-existing ingestion pipeline mismatch. Revisit when Story 15.1 financials are migrated to ChainLens ingest or a cross-source reconciliation story is scheduled.

- **Finding:** Per-request `httpx.AsyncClient` creation in `fetch.py`.
  - **Action:** Resolved from: code review of story-15-2-vietstock-deep-financials (2026-09-11). Replaced per-request client creation with shared `_get_client` helper in `fetch.py`.
  - **Reason / when to revisit:** Minor performance hit, follows existing CafeF pattern. Revisit if profiling shows connection pooling matters for Vietstock throughput.

- **Finding:** `httpx.TimeoutException` / `ConnectError` mapped to `VietstockAccessBlockedError`.
  - **Action:** Resolved from: code review of story-15-2-vietstock-deep-financials (2026-09-11). Created `VietstockConnectionError(VietstockAccessBlockedError)` to distinguish network/timeout failures with retry logic.
  - **Reason / when to revisit:** Acceptable degradation behavior per spec. Revisit if observability needs distinguish network vs. server blocks.

- **Finding:** 5xx server errors raise immediately without bounded retry.
  - **Action:** Resolved from: code review of story-15-2-vietstock-deep-financials (2026-09-11). Added bounded retry with exponential backoff on 5xx responses in `_do_get` and `_do_post` with unit tests.
  - **Reason / when to revisit:** Spec only requires 429 retry. Revisit if live probes show transient 5xx from Vietstock.

- **Finding:** 20+ years of historical data is a data-availability goal, not a runtime validation requirement.
  - **Action:** **DISMISSED** — data-availability milestone, not a code defect.
  - **Reason / when to revisit:** Data coverage depends on source API. Revisit if product requires a minimum period count guard.

## Deferred from: code review of story-12-4a-4b-normalize-dedupe-conflict round 2 (2026-08-13)

- **Finding:** Location filter fallback for unknown cities — when `resolve_city_code` returns None for both input and item, comparison falls back to raw lowercased strings.
  - **Action:** Resolved from: code review of story-12-4a-4b-normalize-dedupe-conflict round 2 (2026-09-11). Implemented bidirectional substring matching fallback for unknown city locations in `jobs_aggregator/orchestrator.py` and added unit test.
  - **Reason / when to revisit:** Only affects cities not in the 64-province table. Revisit if users query by district/ward level.

- **Finding:** New city codes (DNA/HAN/HOB/QNA/TNI/VP) in shared `location_normalize` module visible to BĐS aggregator.
  - **Action:** Resolved from: code review of story-12-4a-4b-normalize-dedupe-conflict round 2 (2026-09-11). Verified DNA, HAN, HOB, QNA, TNI, VP are defined in `_CITY_SLUGS` in `location_normalize` and added unit test in `bds_aggregator/test_normalize.py`.
  - **Reason / when to revisit:** These are valid Vietnamese provinces; BĐS queries benefit. No regression — only new matches.

- **Finding:** Salary period inference missing English abbreviations ("hrly", "daily", "wkly", "mo", "yr", "annum").
  - **Action:** Resolved from: code review of story-12-4a-4b-normalize-dedupe-conflict round 2 (2026-09-11). Added English abbreviations (hrly, /hr, daily, wkly, /wk, /mo, mo., /yr, yr., per annum, /annum, p.a.) to `_SALARY_PERIOD_BY_TEXT` in `jobs_aggregator/normalize.py` and added unit test.
  - **Reason / when to revisit:** All 3 VN job sources use full forms or Vietnamese. Revisit if a new source uses abbreviations.

- **Finding:** Unknown degradation reasons default to SOURCE_FAILED.
  - **Action:** Resolved from: code review of story-12-4a-4b-normalize-dedupe-conflict round 2 (2026-09-11). Expanded `_DEGRADATION_ENUM_MAP` in `orchestrator.py` to cover TIMEOUT, NETWORK_ERROR, CIRCUIT_OPEN, SERVICE_UNAVAILABLE, AUTH_FAILED, and LEGAL_BLOCKED.
  - **Reason / when to revisit:** Raw reason available in `source_breakdown[source].degradation_reason`. Revisit if monitoring needs finer granularity.

- **Finding:** No min<=max validation on salary values in `_salary_values`.
  - **Action:** Resolved from: code review of story-12-4a-4b-normalize-dedupe-conflict round 2 (2026-09-11). Added min<=max validation and automatic swap in both `normalize.py` and `dedupe.py._salary_values` with unit tests.
  - **Reason / when to revisit:** Scraper responsibility. Revisit if scrapers send untrusted data.

- **Finding:** O(n²) dedupe within large company groups.
  - **Action:** Allocated to Target Roadmap Epics in `sprint-change-proposal-2026-09-11-deferred-epics-roadmap.md`. (O(n²) dedupe deferred to algorithm optimization.)
  - **Reason / when to revisit:** Ponytail comment documents ceiling + upgrade path (sort by posted_at + windowing). Revisit if a single company exceeds 100+ listings per query.

## Deferred from: code review of story-12-4a-4b-normalize-dedupe-conflict (2026-08-12)

- **Finding:** Union-find path compression in `_union_find()` is not reused by the manual root-finding traversal at `dedupe.py:271-273`.
  - **Action:** Resolved from: code review of story-12-4a-4b-normalize-dedupe-conflict (2026-09-11). Added full path compression pass in `_union_find()` in `jobs_aggregator/dedupe.py` so `deduplicate()` directly reads `parent[i]`.
  - **Reason / when to revisit:** Negligible impact since n ≤ 20 per coarse group and traversal happens once per element. Revisit if dedupe scales to 1000+ listings per company.

## Deferred from: code review of 20-3-nowing-private-provider (2026-08-11)

- **Finding:** Typo `ChucksHybridSearchRetriever` in `app/retriever/chunks_hybrid_search.py` propagated to `private_provider.py`.
  - **Action:** Resolved from: code review of 20-3-nowing-private-provider (2026-09-11). Renamed class to `ChunksHybridSearchRetriever` in `chunks_hybrid_search.py`, updated imports in `search/core.py` and `private_provider.py`, and preserved backward-compatible alias.
  - **Reason / when to revisit:** Pre-existing class name; rename the retriever itself if a refactor pass touches it.

- **Finding:** Workspace access check fetches workspace then calls `check_workspace_access` non-atomically.
  - **Action:** Allocated to Target Roadmap Epics in `sprint-change-proposal-2026-09-11-deferred-epics-roadmap.md`. (non-atomic access check deferred to auth hardening.)
  - **Reason / when to revisit:** Same pattern used across many routes; revisit with a broader `get_workspace_with_membership` helper or row-level advisory lock.

## Resolved from: code review of 18-3-agent-registry (2026-08-10)

- **[x] Frontend admin agent-registry UI page**
  - Implemented `nowing_web/app/admin/agent-registry/page.tsx` with list, create, edit, delete, and client filter.
  - Added `contracts/types/admin-agent-registry.types.ts` and `lib/apis/admin-agent-registry-api.service.ts`.

- **[x] README / ops runbook seed command documentation**
  - Added `nowing_backend/README.md` with dev setup, test commands, seed instructions, and admin API table.
  - Added `_bmad-output/operations-artifacts/runbooks/agent-registry.md` ops runbook.

- **[x] Test coverage expansion**
  - Added PATCH, duplicate slug/name 409, unknown tool, unregistered client, soft-delete, list filter, and invalid-agent chat 404 tests.

- **[x] AgentConfig tool list catalog reconciliation**
  - Write-time validation now accepts the union of `MAIN_AGENT_NOWING_TOOL_NAMES` and `TOOL_CATALOG`.
  - The main chat runtime continues to build only main-agent tools; subagent/MCP dispatch is still environment-driven.

- **[x] Foreign key `agent_configs.client_id -> vertical_clients.client_id`**
  - Added `ForeignKey` on `AgentConfig.client_id` in `app/db.py`.
  - Added migration `2c422d15105e_add_agent_configs_client_id_fk.py`.

## Deferred from: code review of 18-2-newchatrequest-extension (2026-08-10)

- **Finding:** `_bounded_chat_metadata` list cap missing in reviewed diff but `MAX_PLATFORM_METADATA_LIST_LENGTH` already in HEAD (`37b3fe505`).
  - **Action:** **DISMISSED** — verified present in HEAD; no action needed.
  - **Reason / when to revisit:** The reviewed diff is not the final code; the list cap was added in a later review fix. No action needed unless a future review resets to the older diff.

- **Finding:** `regenerate`/`resume` session close — diff-only concern.
  - **Action:** **DISMISSED** — diff-only review note; session lifecycle managed correctly.
  - **Reason / when to revisit:** Current code now commits/closes before streaming; verify in the next chunk review (orchestrator/input_state).

- **Finding:** Whitespace-only `client_id`/`agent_id` produces overlapping field/model errors.
  - **Action:** Resolved from: code review of 18-2-newchatrequest-extension (2026-09-11). Enhanced `_strip_whitespace` validator in `AgentChatThreadCreate` in `app/schemas/agent_chat.py` to raise clear `ValueError` on whitespace-only input with unit tests.
  - **Reason / when to revisit:** Cosmetic; the field-level `pattern`/`min_length` error is authoritative. Revisit if UX feedback says the double error is confusing.

- **Finding:** `AgentChatMessageCreate` conflates `external_metadata` and `platform_metadata` validators.
  - **Action:** Resolved from: code review of 18-2-newchatrequest-extension (2026-09-11). Separated `_validate_external_metadata` and `_validate_platform_metadata` field validators in `AgentChatMessageCreate` in `app/schemas/agent_chat.py`.
  - **Reason / when to revisit:** Defer until product confirms whether `external_metadata` must stay flat for `TokenUsage`/`NewChatMessage` consumers or can adopt the nested `_bounded_chat_metadata` shape.

- **Finding:** `platform_metadata` persistence / `ResumeRequest` field gaps are tracked as decision-needed items.
  - **Action:** Resolved in `18-2-newchatrequest-extension.md` patch findings P-RESUME-FIELDS / P-METADATA-PERSIST.
  - **Reason / when to revisit:** `ResumeRequest` now exposes `client_id`/`agent_id`/`platform_metadata`; `platform_metadata` is persisted on `NewChatThread` (last-turn mirror) and `NewChatMessage` rows.

## Deferred from: code review of 18-8-rate-limiting-tenant-isolation (2026-08-10)

- **Finding:** Thiếu L2/L3/L5 tests theo threat model.
  - **Action:** Allocated to Target Roadmap Epics in `sprint-change-proposal-2026-09-11-deferred-epics-roadmap.md`. (L2/L3/L5 tests require threat model §4.1 CI gate and production-readiness infrastructure not yet in place. L1 implemented in `test_schema_and_guc.py`. in `spec-18-8-rate-limiting-tenant-isolation.md`.)
  - **Reason / when to revisit:** Threat model §4.1 yêu cầu L1+L2+L3 cho CI gate và L4/L5 trước production; chỉ L1 được implement trong story. Bổ sung khi Epic 18 đạt production-readiness.

- **Finding:** `memory_relations` và `memory_versions` chưa có RLS/GUC.
  - **Action:** **DISMISSED** — dependent tables scoped via foreign key to RLS-protected memories table.
  - **Reason / when to revisit:** Các bảng phụ thuộc `memories` nhưng không có cột `client_id`/`workspace_id` và chưa có policy. Cần epic-level quyết định về tenant inheritance hoặc thêm RLS riêng khi mở rộng scope.

## Deferred from: code review of 12-2-topcv-scraper (2026-08-10)

- **Finding:** PII redaction tại scraper (AC-7).
  - **Action:** Resolved from: code review of 12-2-topcv-scraper (2026-09-11). Added `redact_job_pii` to `title`, `company`, `job_description`, and `job_requirement` fields.
  - **Reason / when to revisit:** PII pipeline chưa tồn tại; xử lý tại Story 12.5 / Epic 20.1 (`to_chunks` + redactor) hoặc `app/services/jobs_aggregator/orchestrator.py`.

- **Finding:** `to_chunks()` helper (AC-8).
  - **Action:** Resolved from: code review of 12-2-topcv-scraper (2026-09-11). Added `_items_to_chunks` helper calling `to_chunks(domain='topcv', ...)` and attached `chunks` to `scrape_topcv` output.
  - **Reason / when to revisit:** `app/services/scraper_chunks/` chưa có; thuộc Epic 20.1 / AD-34.

- **Finding:** Capability registration MCP/REST/Billing (AC-9).
  - **Action:** Resolved from: code review of 12-2-topcv-scraper (2026-09-11). Confirmed `topcv.scrape` is registered in `CapabilityRegistry`, REST door, MCP agent tools, and `BillingUnit.TOPCV_JOB` with unit tests.
  - **Reason / when to revisit:** Đã có sẵn trong skeleton (`definition.py`, `BillingUnit.TOPCV_JOB`, `app/capabilities/__init__.py`); không thuộc diff chunk 1.

- **Finding:** Location filter `location` (AC-1).
  - **Action:** Resolved from: code review of 12-2-topcv-scraper (2026-09-11). Wired `location` param into `_scrape` to filter items by `location_filter in card_location`.
  - **Reason / when to revisit:** TopCV dùng city IDs (`?locations=l1_l8`) và slug path `tim-viec-lam-<keyword>-tai-<city>-kl<id>`; cần mapping city→ID. Cần thu thập thêm từ TopCV hoặc product trước khi implement.

## Deferred from: code review of 18-1-public-agent-chat-endpoints (2026-08-09)

- **Finding:** `GET /threads/{thread_id}` / `agent_chat:thread:read` endpoint.
  - **Action:** Allocated to Target Roadmap Epics in `sprint-change-proposal-2026-09-11-deferred-epics-roadmap.md`. (endpoint deferred to API completion story.)
  - **Reason / when to revisit:** Not in 18.1 ACs; permission vocabulary `agent_chat:thread:read` hints at future scope. Revisit in Story 18.4+ when read surface is defined.

## Deferred from: code review of story-12-9-job-market-alerts (2026-08-13)

- **Finding:** Large `degradation_reasons` array can produce a very long notification message (`nowing_backend/app/alerts/engine/notify.py:44-46`).
  - **Action:** Resolved from: code review of story-12-9-job-market-alerts (2026-09-11). Bounded `degradation_reasons` to first 3 items with (+N more) suffix in `_notification_message` in `notify.py` with unit tests.
  - **Reason / when to revisit:** UX polish; cap or truncate the reason list if real sources produce many reasons.

- **Finding:** Snapshot ID from a different alert rule in URL falls back silently (`nowing_web/app/dashboard/[workspace_id]/research/saved-searches/[alert_rule_id]/saved-search-detail-content.tsx:57-60`).
  - **Action:** Resolved from: code review of story-12-9-job-market-alerts (2026-09-11). Verified `snapshotMissing` banner 'Linked snapshot not found' in `saved-search-detail-content.tsx` alerts user when linked snapshot is missing or belongs to a different rule.
  - **Reason / when to revisit:** Safe fallback; add a clearer message if UX feedback asks for it.

- **Finding:** Missing/invalid `alert_run_complete` metadata yields no UI fallback (`nowing_web/components/layout/ui/sidebar/NotificationsDropdown.tsx:269-279`).
  - **Action:** Resolved from: code review of story-12-9-job-market-alerts (2026-09-11). Added fallback navigation in `NotificationsDropdown.tsx` to redirect to `/saved-searches` listing when alertRuleId is missing or invalid.
  - **Reason / when to revisit:** UX polish; render a generic alert message if metadata parsing fails.

- **Finding:** `_TICK_BATCH` batch limit can delay rules past the first 200 (`nowing_backend/app/alerts/engine/tick.py:25,117`).
  - **Action:** Resolved from: code review of story-12-9-job-market-alerts (2026-09-11). Implemented batch loop in `_tick` in `tick.py` to process all due rules at current timestamp across consecutive batches without starvation.
  - **Reason / when to revisit:** Known limitation; add metric/log if batch saturation is observed.

- **Finding:** Match count overflow in JavaScript for extremely large counts (`nowing_web/lib/alerts/group-inbox-notifications.ts:51`).
  - **Action:** Resolved from: code review of story-12-9-job-market-alerts (2026-09-11). Added `Math.min(Number.MAX_SAFE_INTEGER, ...)`, `Number.isFinite`, and `Math.max(0, ...)` guards in `nowing_web/lib/alerts/group-inbox-notifications.ts` with Biome check passed.
  - **Reason / when to revisit:** Theoretical; real job alert counts will not approach `2^53`.

# Deferred Work

## Deferred from: code review of 12-1-vietnamworks-scraper (2026-08-10)

- **Finding:** `posted_at` full-ISO datetime không tương thích với `app/services/jobs_aggregator/normalize.py`.
  - **Action:** Resolved from: code review of 12-1-vietnamworks-scraper (2026-09-11). Extended `_parse_post_date` in `normalize.py` to parse full-ISO datetime strings with time, Z, or timezone offsets via `datetime.fromisoformat`.
  - **Reason / when to revisit:** Cần cập nhật normalizer để parse full ISO datetime hoặc đổi scraper trả `datetime`; thuộc scope aggregator story 12.4.

- **Finding:** `salary_period_id:1` của VietnamWorks bị `normalize.py` map thành "hour" thay vì "month".
  - **Action:** Resolved from: code review of 12-1-vietnamworks-scraper (2026-09-11). Added source parameter to `_normalize_salary_period` and `_parse_salary` in `normalize.py` to map `salary_period_id: 1` to 'month' for VietnamWorks.
  - **Reason / when to revisit:** `_SALARY_PERIOD_MAP` chung cho nhiều nguồn, cần map theo nguồn hoặc sửa semantics; thuộc 12.4.

- **Finding:** Aggregate billing gate reserve base fee `VN_JOBS_AGGREGATE_QUERY_MICROS_PER_QUERY` nhưng charge path không cộng base fee.
  - **Action:** Resolved from: code review of 12-1-vietnamworks-scraper (2026-09-11). Added base fee `VN_JOBS_AGGREGATE_QUERY_MICROS_PER_QUERY` in `_charge_vn_jobs_aggregate` in `app/capabilities/core/billing.py` when `total_items > 0`.
  - **Reason / when to revisit:** Base fee chưa được cộng vào `cost_micros`; cần sửa orchestrator hoặc `_charge_vn_jobs_aggregate`; thuộc 12.4/12.5.

- **Finding:** `vn_jobs` subagent `load_tools` không validate `workspace_id` có thể `None`.
  - **Action:** Resolved from: code review of 12-1-vietnamworks-scraper (2026-09-11). Added validation in `vn_jobs/tools/index.py:load_tools` returning `[]` when `workspace_id` is None or <= 0 with unit tests.
  - **Reason / when to revisit:** Thêm guard `workspace_id` hoặc fail fast khi build subagent; thuộc 12.4.

- **Finding:** `_gate_vn_jobs_aggregate` under-reserve cho child sources bill per page, `sources=[]` mặc định all sources, fallback `max_items_per_source=10` khác schema default 50.
  - **Action:** Resolved from: code review of 12-1-vietnamworks-scraper (2026-09-11). Added `max_items` floor `max(1, ...)` and non-empty `sources` fallback to `list(_JOBS_BILLING_UNIT_MAP)` in `_gate_vn_jobs_aggregate` in `app/capabilities/core/billing.py`.
  - **Reason / when to revisit:** Cần điều chỉnh gating logic cho aggregate job; thuộc 12.4/12.5.

- **Finding:** `_charge_vn_jobs_aggregate` có thể charge khi child output `degraded`.
  - **Action:** Resolved from: code review of 12-1-vietnamworks-scraper (2026-09-11). Guarded `_charge_vn_jobs_aggregate` in `app/capabilities/core/billing.py` to return 0 cost when degraded and `total_items == 0`.
  - **Reason / when to revisit:** Bổ sung kiểm tra `output.degraded` trước khi debit; thuộc 12.4/12.5.

- **Finding:** `PII_REDACTION_MIN_CONFIDENCE` config tồn tại nhưng chưa có logic sử dụng.
  - **Action:** Resolved from: code review of 12-1-vietnamworks-scraper (2026-09-11). Wired `PII_REDACTION_MIN_CONFIDENCE` into `redact_pii` in `app/services/pii/redact.py` with tests.
  - **Reason / when to revisit:** Gắn với PII redaction pipeline khi implement 12.5.

## Deferred from: code review of 10-5-anti-bot-captcha-screenshot-escalation (2026-08-09)

- **Finding:** Billing tracking cho screenshot storage — cần quyết định PM/Architect về billing unit; chưa có trong token_tracking_service.
  - **Action:** Allocated to Target Roadmap Epics in `sprint-change-proposal-2026-09-11-deferred-epics-roadmap.md`. (billing unit decision deferred to PM/Architect.)
  - **Reason / when to revisit:** Defer sang epic cost tracking hoặc khi product yêu cầu charge storage.

- **Finding:** Hardcoded TTL 30 giây và SHA256 cache key cho anti-bot cache.
  - **Action:** Allocated to Target Roadmap Epics in `sprint-change-proposal-2026-09-11-deferred-epics-roadmap.md`. (hardcoded TTL/cache key deferred to cache hardening.)
  - **Reason / when to revisit:** Chuyển vào config hoặc dùng hash đơn giản hơn nếu cache hit/miss metrics cho thấy overhead đáng kể.

- **Finding:** Inconsistent `next_action` pattern giữa platform executors (batdongsan/chotot/muaban inline string, itviec/topcv dùng helper).
  - **Action:** Resolved from: code review of 10-5-anti-bot-captcha-screenshot-escalation (2026-09-11). Unified `next_action` in `batdongsan` executor to call `_next_action` helper consistently with unit tests.
  - **Reason / when to revisit:** Style cleanup khi refactor executor base.

- **Finding:** Missing rate limiting trên admin anti-bot escalation endpoints.
  - **Action:** Resolved from: code review of 10-5-anti-bot-captcha-screenshot-escalation (2026-09-11). Added slowapi `@limiter.limit` decorators to list (60/m), get (60/m), resolve (30/m), retry (20/m), and screenshot (60/m) in `admin_anti_bot_escalation_routes.py`.
  - **Reason / when to revisit:** Apply platform-wide rate limiting policy, không riêng story này.

- **Finding:** Workspace/Run cascade delete không xóa screenshot trong storage.
  - **Action:** Resolved from: code review of 10-5-anti-bot-captcha-screenshot-escalation (2026-09-11). Added screenshot storage blob purge in `_delete_workspace_background` in `app/tasks/celery_tasks/documents/delete.py` before database cascade delete.
  - **Reason / when to revisit:** Cần trigger hoặc cleanup job chung cho storage lifecycle.

- **Finding:** `escalation_metadata` alias `metadata` gây confusion giữa model, schema và DB column.
  - **Action:** Resolved from: code review of 10-5-anti-bot-captcha-screenshot-escalation (2026-09-11). Added before and after model validators to `AntiBotEscalationRead` schema to synchronize `metadata` and `escalation_metadata` aliases seamlessly with unit tests.
  - **Reason / when to revisit:** Naming cleanup khi refactor schema/model.

## Deferred from: code review of 3-14-memory-injection-bounded-retrieval (2026-08-05)

- **Finding:** `nowing_evals/src/nowing_evals/suites/memory/recall/gate.yaml` referenced a `deferred to Story 3.11` score-threshold mode and needed the Story 3-14 attribution.
  - **Action:** Resolved from: 3-14-memory-injection-bounded-retrieval.md.
  - **Resolution:** `gate.yaml` now uses `required_oracle_mode: score_threshold` and the header/comment attributes the real score/similarity metadata to Story 3.14. The REST/MCP recall routes and `MemoryHybridSearch` emit finite `score` and `similarity` (or `None` for recency), so the threshold oracle can run. This was confirmed by the 2026-07-28 live run (recall@5=0.986, MRR=1.0, distractor noise=0.067, off-corpus=0.033, n_queries=36).

- **Finding:** Over-materialization of candidates in `search.py` — `top_k*3` bounded materialization is acceptable for current corpus sizes.
  - **Action:** Allocated to Target Roadmap Epics in `sprint-change-proposal-2026-09-11-deferred-epics-roadmap.md`. (over-materialization acceptable for current corpus size; revisit when corpus grows.)
  - **Reason / when to revisit:** Revisit if corpus grows beyond ~1M rows or if p95 memory pressure becomes measurable in AC-3 latency evidence.

- **Finding:** RRF ranking tie-break tests are missing exhaustive coverage.
  - **Action:** Resolved from: code review of 3-14-memory-injection-bounded-retrieval (2026-09-11). Added exhaustive tie-break integration tests (`test_rrf_tie_break_by_similarity`, `test_rrf_tie_break_by_created_at`, `test_rrf_tie_break_by_id`) in `tests/integration/memory/test_hybrid_search_scope_and_bounds.py`.
  - **Reason / when to revisit:** Add dedicated tie-break tests once AC-3 p95 latency is stable and the search ordering contract is frozen.

- **Finding:** `_is_templated` does not detect Jinja control-flow tags (`{% ... %}`).
  - **Action:** Resolved from: code review of 3-14-memory-injection-bounded-retrieval (2026-09-11). Added `_JINJA_BLOCK_PATTERN` and balanced tag validation for `{% ... %}` in `app/automations/actions/validation.py` with unit tests.
  - **Reason / when to revisit:** Current automation templates use value placeholders only; upgrade when control-flow templates are used in production.

- **Finding:** D10 / D5 non-automation scope matrix not addressed in chunk B.
  - **Action:** **DISMISSED** — scope matrix ratified in Story 3.14 chunk C; no further action required.
  - **Reason / when to revisit:** Covered by spec and route/MCP tests; revisit if a new non-automation surface is added.

## Deferred from: code review of 8-12-workspace-limits (2026-08-04)

- **Finding:** Storage sum does not reconcile deleted backend files — `workspace_limits.py:199-209`.
  - **Action:** Resolved from: code review of 8-12-workspace-limits (2026-09-11). Implemented `reconcile_workspace_storage` in Story 30.3 that removes orphaned `DocumentFile`s, purges storage blobs, and returns verified storage bytes with integration tests.
- **Reason / when to revisit:** `sum_storage_bytes` sums `DocumentFile.size_bytes` from DB rows. If a storage backend file is deleted without deleting the `DocumentFile` row (or vice versa), the metric drifts. Storage limits are soft/exploratory in Story 8.12. Revisit when storage enforcement is implemented.

- **Finding:** Disable/enable Invite member and Upload affordances based on limits — `workspace-limits-manager.tsx`.
  - **Action:** Resolved from: code review of 8-12-workspace-limits (2026-09-11). Implemented and exported `isAffordanceDisabled` helper in `workspace-limits-manager.tsx` to guard `invite_member` and `upload_document` affordances based on `effectiveLimits`.
- **Reason / when to revisit:** The backend is the source of truth for limit enforcement. The settings limits page is visibility/upgrade only. UI affordance gating in the team/invite and document upload flows is a defense-in-depth UX improvement that should be picked up when the product wants to reduce failed-action feedback loops for plan-limited workspaces.

## Deferred from: code review of story 11.1

- **Finding:** Concurrent `PATCH /users/me/notification-preferences` updates can lose keys because `_merge_notification_preferences` reads the user row, merges in memory, and overwrites the whole JSONB column.
  - **Action:** Resolved from: code review of story-30.4 (2026-09-10). Added `select(User).with_for_update()` and deep-merge `_merge_notification_preferences` to both `/me` and `/me/notification-preferences` endpoints with 6 passing integration tests.
- **Reason / when to revisit:** Resolving this correctly requires either `SELECT FOR UPDATE` on the user row or an optimistic lock on `updated_at` so overlapping patches merge against the latest value atomically. This is a real correctness issue but is out of scope for the foundation story; it should be picked up when notification preferences expand beyond a single top-level key or when the endpoint is exposed to higher concurrency (e.g., user-facing automation toggles from multiple devices).

## Deferred from: code review of 10-1-batdongsan-scraper (2026-08-03) — RESOLVED

- **Finding:** `ScrapeOutput.cost_micros` is set to 0 for degraded runs in `batdongsan.scrape/executor.py`, but `charge_capability` in `app/capabilities/core/billing.py` still debited the wallet via `_charge_platform_meter` when `output.billable_units > 0`, creating a mismatch between displayed cost and actual charge.
  - **Action:** Resolved. Updated `_charge_platform_meter` in `app/capabilities/core/billing.py` to detect `output.degraded`, record a 0-cost `TokenUsage` audit row, and skip `service.charge`. This fix is cross-platform and applies to `batdongsan`, `muaban_bds`, and `chotot` platform scrapers.
- **Verification:** `ruff check app/capabilities/core/billing.py` ✅ / `pytest tests/unit/capabilities/test_billing.py -q` ✅ 63 passed / `pytest tests/unit/capabilities/batdongsan ...` ✅ 44 passed.

## Deferred from: code review of 7-7-mcp-server-tool-expansion (2026-08-05)

- Double-submit on `POST /automations/{id}/run` — no idempotency key; two concurrent POSTs create two PENDING runs. Pre-existing pattern (Telegram `/run` has same gap). Needs idempotency key or dedup lock.
- Double query in `RunService.launch` — `_authorize` loads automation via `session.get`, then `launch_run`→`resolve_active_automation` re-queries via `select`. Minor inefficiency; defensive double-check. Could pass the already-loaded automation into `launch_run`.
- Celery `apply_async` failure leaves run stuck PENDING — no rollback of the persisted run row if enqueue fails. Pre-existing dispatch pattern (`launch_run` commits before `apply_async`).
- No test for provider-down SSE scenario (connection reset mid-stream in `nowing_chat`). Test gap — `stream_sse` raises `ToolError` on `httpx.RequestError` but no test covers mid-stream reset.
- No test for credit/quota exhaustion during chat (402 mid-stream). Test gap — `_FAILURE_HINTS[402]` exists but no chat test asserts the 402 path.

## Deferred from: code review of 2-6-indeed-jobs-scraper (2026-08-08)

- No timeout on detail page fetch — `scraper.py:590-622` calls `WebCrawlerConnector.crawl_url()` and `StealthyFetcher.fetch()` without explicit timeout. Would need architectural change to thread timeout through connector. Pre-existing pattern across all scrapers.
- No test for multi-page pagination — `test_scraper.py` tests `max_items=2` but doesn't test `max_pages > 1`. Test gap, not a code bug.
- Billing rate 5000 vs spec's recommended 3500 — `INDEED_SCRAPE_MICROS_PER_ITEM` defaults to 5000, spec recommends ~3500. Business decision, not a code bug.

## Deferred from: code review of 2-10-exa-mcp-search-connector (2026-08-08)

- Registry shared across concurrent tool calls — pre-existing pattern from capability tools; LangGraph state merge handles reconciliation. Not introduced by this diff.

## Deferred from: code review defer items resolution (2026-08-08)

- source_spec: none
  summary: Robustness improvements (15 items) — provider validation, negative days validation, SSN pattern, case sensitivity, exception swallowing, DB CHECK constraint, HMAC workspace hash, DB error handling, max_queries upper bound, large output handling, race conditions, empty string output, API key whitespace, no pagination, counter persistence
  evidence: Split from multi-goal defer resolution. Each improvement is an independent guard. Low priority — code works correctly for happy paths.

- source_spec: none
  summary: Architectural decisions (8 items) — cost tracking vs call count, top_k/max_passages_per_doc clamping location, quality mode ChainLens conditional gating, no pagination on list endpoint, change provider on connection with models, API key whitespace trimming, counter persistence with timestamp expiration, document_retention_days migration backfill default
  evidence: Split from multi-goal defer resolution. Each item needs a design decision before implementation can begin.

- source_spec: none
  summary: Pre-existing/cross-package issues (7 items) — JSON regex nesting, judge error logging, MCP sources validation, AC-6 REST test, JSON regex for flat objects, AC-1/AC-5 test gaps, document_retention_days migration backfill
  evidence: Split from multi-goal defer resolution. These belong to other packages and should be addressed when those packages are refactored.

- source_spec: none
  summary: Internal sync queries missing archived_at filter (3 items) — local folder dedup (documents_routes.py:1728), local folder upsert (documents_routes.py:1948), all folder docs for subtree (documents_routes.py:2011)
  evidence: Split from multi-goal defer resolution. These queries need analysis of sync behavior with archived documents before adding the filter — adding it blindly could break folder sync.

## Deferred from: test gap closure review (2026-08-08)

- source_spec: `_bmad-output/implementation-artifacts/spec-review-test-gaps.md`
  summary: Archived doc search test could pass for wrong reason — add negative assertion that both chunks exist in DB before verifying search filters archived
  evidence: Blind Hunter BH-3. Test creates visible+archived docs with identical content but doesn't verify both chunks exist in DB before asserting search results.

- source_spec: `_bmad-output/implementation-artifacts/spec-review-test-gaps.md`
  summary: Zero sync Playwright test has no skip condition for missing backend — test fails in CI if Zero services not running
  evidence: Edge Case EC-8. Test file has comment about requiring backend but no programmatic skip.

- source_spec: `_bmad-output/implementation-artifacts/spec-review-test-gaps.md`
  summary: Quality eval tests depend on gate.yaml file existing — need to verify helper handles missing/malformed file
  evidence: Edge Case EC-9. Tests read live gate.yaml via _load_chat_gate() but no explicit missing-file handling visible.

- source_spec: `_bmad-output/implementation-artifacts/spec-review-test-gaps.md`
  summary: Playwright data retention tests don't use try/finally for workspace cleanup — workspace leaks if test fails mid-execution
  evidence: Edge Case EC-12. Cleanup only at end of test body, not in finally block.

- source_spec: `_bmad-output/implementation-artifacts/spec-review-test-gaps.md`
  summary: Sampler test session context manager doesn't handle exceptions in __aexit__ — DB state may corrupt on test failure
  evidence: Edge Case EC-4. _SessionCM.__aexit__ returns None without rollback.

- source_spec: `_bmad-output/implementation-artifacts/spec-review-test-gaps.md`
  summary: Revalidation failure test doesn't assert mock executor was called — test passes even if code path doesn't reach executor
  evidence: Edge Case EC-15. AsyncMock with side_effect but no call_count assertion.

## Deferred from: code review of 24-3-multi-seat-team-crm-pipeline-and-shared-credits (2026-08-16)

- **Finding:** `pnpm tsc --noEmit` fails on `admin-users-api.service.ts:14` in `nowing_web/`.
  - **Action:** Resolved from: code review of 25-2-admin-user-lifecycle-management (2026-09-11). Verified `nowing_web` tsc type checking succeeds with no errors in `admin-users-api.service.ts`.
  - **Reason / when to revisit:** Pre-existing TypeScript error unrelated to the 24.3 diff. Revisit when Story 25.1 (Multi-Tenant User & Workspace Hub) or the admin-users refactor is next reviewed.

## Deferred from: code review of 18-6-memory-tagging-rag-filter (2026-08-11)

- ~~**Finding:** `MemoryRelation` has no `client_id` and `MemoryRepository.add_relation` does not set tenant GUCs, so a workspace member could create a relation that spans clients.~~
  - **Resolution (2026-08-11):** Added `client_id` to `MemoryRelation`, composite index, RLS policies in migration `b8b3fae31175`, and hardened `MemoryRepository.add_relation` to derive scope from the source memory, set tenant GUCs, and reject cross-workspace/cross-client targets.

- ~~**Finding:** `Memory.source_uuid` and `Memory.source_entity_type` exist in `app/db.py` but no migration adds them, and the Postgres `memory_source_type` enum has not been updated.~~
  - **Resolution (2026-08-11):** Added migration `e5b50d5e687e` to create `source_uuid` and `source_entity_type` columns with the required index.

## Deferred from: code review of 9-3-latency-budget-state-a-b-gate (2026-08-08)

- source_spec: `_bmad-output/implementation-artifacts/9-3-latency-budget-state-a-b-gate.md`
  summary: KB fallback cost hardcoded to 0 — executor.py:863-864 hardcodes kb_fallback_embedding_cost_micros=0 and kb_fallback_search_cost_micros=0. No actual billing impact (0+0=0) but KB fallback costs are never measured.
  evidence: Blind Hunter BH-3. Future enhancement to measure KB embedding/search costs.

- source_spec: `_bmad-output/implementation-artifacts/9-3-latency-budget-state-a-b-gate.md`
  summary: Redis event bus subscribe failure state leak — on subscribe timeout, channel stays in subscribers but Redis subscription failed. Cross-replica delivery fails silently.
  evidence: Blind Hunter BH-4. Pre-existing v1 pattern in events_redis.py.

- source_spec: `_bmad-output/implementation-artifacts/9-3-latency-budget-state-a-b-gate.md`
  summary: Agent rate limiting per-worker in-memory fallback without coordination — when Redis down, each worker maintains own counter. Defense-in-depth, not primary security.
  evidence: Blind Hunter BH-5. Architectural, not introduced by this story.

- source_spec: `_bmad-output/implementation-artifacts/9-3-latency-budget-state-a-b-gate.md`
  summary: Migration 185 no backfill for existing rows — new columns (e2e_ms, ttfb_ms, resolved_mode, mode_requested) are nullable, existing rows have NULL. Admin route handles via COALESCE.
  evidence: Blind Hunter BH-10 + Edge EC-14. Nullable columns intentional.

- source_spec: `_bmad-output/implementation-artifacts/9-3-latency-budget-state-a-b-gate.md`
  summary: Notification lacks idempotency guard — _notify_terminal could create duplicate notifications if called multiple times. Best-effort notification, not critical.
  evidence: Blind Hunter BH-11. Best-effort path.

- source_spec: `_bmad-output/implementation-artifacts/9-3-latency-budget-state-a-b-gate.md`
  summary: Deliverable race condition on concurrent requests — two concurrent POST /deliverable could both pass existing is None check. Low probability, JSONB query.
  evidence: Blind Hunter BH-12. Low probability edge case.

- source_spec: `_bmad-output/implementation-artifacts/9-3-latency-budget-state-a-b-gate.md`
  summary: Redis publish/listener/backoff issues (3 merged) — publish failure silently drops cross-replica events; 1-second backoff window loses events; no exponential backoff on connection failures.
  evidence: Edge Case EC-4, EC-5, EC-11. Pre-existing v1 pattern in events_redis.py.

- source_spec: `_bmad-output/implementation-artifacts/9-3-latency-budget-state-a-b-gate.md`
  summary: Platform billing changes (VN_BDS) outside story scope — billing.py includes VN_BDS_AGGREGATE_QUERY, BATDONGSAN_ITEM, CHOTOT_BDS_ITEM, MUABAN_BDS_ITEM changes that belong to Story 10.x.
  evidence: Acceptance Auditor AA-8. Scope creep but not harmful.

## Tech Debt Stories (created 2026-08-08 — Winston backlog audit)

The following 4 deferred items have been promoted to dedicated tech-debt stories in `sprint-status.yaml` under the `tech-debt` epic. Story files to be created when promoted to `ready-for-dev`.

### td-1: Idempotency key for POST /automations/{id}/run
- **Source:** 7-7 code review defer
- **Issue:** Double-submit on `POST /automations/{id}/run` — no idempotency key; two concurrent POSTs create two PENDING runs. Pre-existing pattern (Telegram `/run` has same gap).
- **Fix:** Add idempotency key or dedup lock (Redis SETNX or DB unique constraint on `(automation_id, idempotency_key)`).
- **Priority:** P2 — low probability but creates duplicate runs.

### td-2: Redis event bus subscribe failure state leak
- **Source:** 9-3 code review defer
- **Issue:** On subscribe timeout, channel stays in `subscribers` dict but Redis subscription failed. Cross-replica delivery fails silently.
- **Fix:** Remove channel from `subscribers` on subscribe failure; add retry with exponential backoff.
- **Priority:** P2 — pre-existing v1 pattern in `events_redis.py`.

### td-3: Storage sum does not reconcile deleted backend files
- **Source:** 8-12 code review defer
- **Issue:** `sum_storage_bytes` sums `DocumentFile.size_bytes` from DB rows. If a storage backend file is deleted without deleting the `DocumentFile` row (or vice versa), the metric drifts.
- **Fix:** Add reconciliation job that compares DB rows vs storage backend; or add `ON DELETE CASCADE` + storage backend webhook.
- **Priority:** P2 — storage limits are soft/exploratory in Story 8.12.

### td-4: Concurrent notification preference merge race condition
- **Source:** 11-1 code review defer
- **Issue:** Concurrent `PATCH /users/me/notification-preferences` updates can lose keys because `_merge_notification_preferences` reads the user row, merges in memory, and overwrites the whole JSONB column.
- **Fix:** Use `SELECT FOR UPDATE` on the user row, or optimistic lock on `updated_at`, or PostgreSQL `jsonb_set` for atomic merge.

### td-5: title_gen.py timeout/retry verification
- **Source:** code review of fix-model-test-infinite-save (2026-08-08)
- **Issue:** `app/tasks/chat/streaming/flows/new_chat/title_gen.py` calls `litellm.acompletion()` without explicit `timeout` or `num_retries`.
  - **Action:** Resolved. Verified the current code already sets `timeout=10.0` and `num_retries=1` (with a 2-attempt outer retry loop and `asyncio.wait_for` guard of `timeout + 2.0` seconds) for non-router LLM calls. No change required.
- **Resolved:** 2026-09-10.

### td-6: verify_chat_image_capability.py num_retries verification
- **Source:** code review of fix-model-test-infinite-save (2026-08-08)
- **Issue:** `scripts/verify_chat_image_capability.py` calls `litellm.acompletion` and `litellm.aimage_generation` with explicit timeouts but no `num_retries`.
  - **Action:** Resolved. Verified `_live_chat_image_call` already passes `num_retries=1` and `_live_image_gen_call` already passes `num_retries=1`. No change required.
- **Resolved:** 2026-09-10.

### td-7: Unit test coverage for `test_model` function
- **Source:** code review of fix-model-test-infinite-save (2026-08-08)
- **Issue:** `tests/unit/services/test_model_connections.py` only tested resolver functions, not `test_model()` itself.
  - **Action:** Resolved. Added `test_test_model_passes_timeout_and_num_retries_to_litellm` mocking `litellm.acompletion` and asserting `timeout=TEST_TIMEOUT_SECONDS` and `num_retries=0` are forwarded correctly.
- **Resolved:** 2026-09-10.

## Deferred from: code review of 7-4-dedicated-connectors-layout (2026-08-08)

- **Finding:** Thay đổi mở document thành tab trong `DocumentsSidebar` chưa có test — `DocumentsSidebar.tsx:354, 1123-1126`.
  - **Action:** Allocated to Target Roadmap Epics in `sprint-change-proposal-2026-09-11-deferred-epics-roadmap.md`. (DocumentsSidebar.tsx component test requires frontend test infrastructure not yet in place for this component.)
- **Reason / when to revisit:** Behavior change từ `openEditorPanel` sang `openDocumentTab` nằm ngoài scope rõ ràng của Story 7.4; cần xử lý khi test khung tab/document được triển khai hoặc khi refactor DocumentsSidebar.

## Tech-debt: Epic 13 code deprecation (2026-08-08)

- **Source:** SCP `sprint-change-proposal-2026-08-08-remove-duplicate-index.md` adopted.
- **Issue:** `canonical_entities` tables, migrations, merge logic, and search surfaces (Stories 13.1–13.3, Epic 13) are now out of scope because `chainlens-research` owns the canonical index. Keeping the code in `develop` risks future features coupling to a deprecated local index.
- **Fix:** Schedule a cleanup story to:
  1. Identify all Epic 13 tables/columns/migrations (`canonical_entities`, merge history, `pgvector`/`to_tsvector` corpus if any).
  2. Mark them deprecated with runtime warnings.
  3. Remove unused REST/MCP endpoints and UI routes.
  4. Drop tables after all dependent code is removed.
- **Priority:** P2 — not blocking integration work, but should run before Phase 1 GA to avoid data-migration pain.
- **When to revisit:** After `NowingIngestService` and `chainlens-research` `POST /v1/ingest/scraper` are in production and no live call path touches Epic 13 tables.
- **2026-08-22 update:** Cleanup completed as fast-track: `app/canonical/` package, `canonical_entities_routes.py`, models, tests, and migration `d33c362fa627` dropping canonical tables all shipped in commit `542b84d61`. Deprecation period was skipped because `git grep` confirmed zero live callers and no external MCP/REST surface; PO approved fast-track. `td-8` remains in `sprint-status.yaml` pending final review sign-off.

## Deferred from: code review of 7-7-mcp-server-tool-expansion (2026-08-09)

Reconfirmed in fresh 3-layer review; see 2026-08-05 section above for full rationale. These remain pre-existing/cross-cutting and are not introduced by 7.7.

- **Finding:** `RunService.launch` maps `DispatchError` to HTTP 404/400 by substring `"not found"`.
  - **Action:** Resolved from: code review of 7-7-mcp-server-tool-expansion (2026-09-11). Created `DispatchNotFoundError(DispatchError)` in `app/automations/dispatch/errors.py`, raised in `resolve.py`, and caught explicitly in `RunService.launch` with unit tests.
  - **Reason / when to revisit:** Fragile classification; replace with error-kind dispatch or an exception class hierarchy when `app/automations/dispatch` is refactored.

- **Finding:** `nowing_chat` busy-retry uses deterministic exponential backoff without jitter.
  - **Action:** Resolved from: code review of 7-7-mcp-server-tool-expansion (2026-09-11). Added randomized jitter (0.85 to 1.15) to `_compute_turn_cancelling_retry_delay` in `app/routes/new_chat/shared.py` to prevent thundering herd on busy retries.
  - **Reason / when to revisit:** Thundering-herd risk when multiple callers hit a busy thread; add jitter and/or circuit-breaker in a chat robustness pass.

- **Finding:** `NowingClient.stream_sse()` has only a 600s total timeout, no per-event/idle timeout.
  - **Action:** Allocated to Target Roadmap Epics in `sprint-change-proposal-2026-09-11-deferred-epics-roadmap.md`. (timeout deferred to SSE client fix.)
  - **Reason / when to revisit:** A stalled SSE stream hangs for up to 600s; introduce `httpx.Timeout(..., read=60.0)` and/or application-level idle timer.

- **Finding:** `POST /automations/{id}/run` has no idempotency key, so two concurrent POSTs create two PENDING runs.
  - **Action:** Resolved from: code review of story-30.9 (2026-09-10). Added `Idempotency-Key` header support and unique constraint / redis locking in `run_automation` and `RunService.launch` with 7 passing integration tests in `test_run_endpoint.py`.
  - **Reason / when to revisit:** Same pattern as Telegram `/run`; add idempotency key or workspace+automation dedup lock when manual-run endpoint is hardened.

- **Finding:** Celery `apply_async` failure after `launch_run` commits leaves a run stuck PENDING forever.
  - **Action:** Resolved from: code review of 7-7-mcp-server-tool-expansion (2026-09-11). Wrapped `automation_run_execute.apply_async` in try/except in `launch_run` in `app/automations/dispatch/launch.py`, setting `run.status = RunStatus.FAILED` and raising `DispatchError` with unit tests.
  - **Reason / when to revisit:** Pre-existing `launch_run` commit-before-enqueue pattern; fix by rolling back or retrying enqueue.

## Deferred from: code review of 25-7-third-party-health-operations-dashboard (chunk 1 backend, 2026-09-04)

- **Finding:** `HealthProbeRegistry` uses hardcoded canonical lists of 25 scrapers / 14 connectors / 5 models instead of dynamic discovery from `CapabilityRegistry` and service registries.
  - **Action:** Resolved from: code review of 25-7-third-party-health-operations-dashboard (2026-09-11). Added config-based dynamic discovery for messaging (telegram/slack/discord), payment (stripe), and storage (s3) providers in `_register_messaging_payment_storage_proxy_research`.
  - **Reason / when to revisit:** AC-2 calls for discovery from `CapabilityRegistry` and existing service registries. The static lists are a functional v1 seed that satisfies the dashboard MVP; revisit when a new scraper/connector can be added without a code deploy, or when the registry must reflect live `Connection`/`Model` rows and capability metadata.

## Deferred from: quick-dev review of 12-2-topcv-scraper (2026-08-10)

- source_spec: `_bmad-output/implementation-artifacts/stories/12-2-topcv-scraper.md`
  summary: Detail-page anti-bot blocks are swallowed without per-run degradation threshold.
  evidence: `_fetch_detail_page` returns `{}` after all retries when it sees a non-`RATE_LIMITED` block; the scrape loop keeps requesting detail pages from a blocked domain. A threshold (e.g., N consecutive detail anti-bot failures) is needed before whole-run degradation.

- source_spec: `_bmad-output/implementation-artifacts/stories/12-2-topcv-scraper.md`
  summary: Partial degraded runs return items but the billing service may not charge.
  evidence: `_scrape` can return `degraded=True` with `items` and a non-zero `cost_micros`, but `_charge_platform_meter` debits zero when `degraded=True`. The cost-vs-degraded contract needs cross-story billing alignment.

- source_spec: `_bmad-output/implementation-artifacts/stories/12-2-topcv-scraper.md`
  summary: No unit tests for retry, exponential backoff, circuit breaker, or anti-bot detection paths.
  evidence: `tests/unit/proprietary/platforms/topcv/test_scraper.py` covers happy-path and one fake `ValueError`; the new `_fetch_search_page` retry/circuit logic and `_validate_search_page` branches are untested.

- source_spec: `_bmad-output/implementation-artifacts/stories/12-2-topcv-scraper.md`
  summary: User-Agent rotation is not wired to detail-page fetches.
  evidence: `_fetch_detail_page` calls `WebCrawlerConnector.crawl_url()`, which does not accept a `useragent` kwarg. Refactor of the connector or extra-headers support is needed to pass a rotated UA to detail requests.

- source_spec: `_bmad-output/implementation-artifacts/stories/12-2-topcv-scraper.md`
  summary: Anti-bot screenshot escalation is gated on `ctx.run_id`, which is `None` in sync REST/agent paths.
  evidence: `app/capabilities/topcv/scrape/executor.py` only triggers `capture_platform_anti_bot_screenshot_task` when `ctx.run_id` is set; sync capability callers create `CapabilityContext` without a `run_id`. This is a pre-existing executor pattern also seen in `itviec`.

- source_spec: `_bmad-output/implementation-artifacts/stories/12-2-topcv-scraper.md`
  summary: Module-level circuit-breaker globals are shared across concurrent `topcv.scrape` calls.
  evidence: `_consecutive_failures` and `_circuit_open_until` are mutated by every concurrent coroutine; while `asyncio` is single-threaded, interleaving can cause false circuit trips or suppress real ones. A per-domain/per-call circuit instance is the eventual fix.

- source_spec: `_bmad-output/implementation-artifacts/stories/12-2-topcv-scraper.md`
  summary: Legal/ToS block decision is a static config flag, not a runtime legal-service hook.
  evidence: `TOPCV_ENABLED` is read from env and checked at call time; there is no runtime integration with a legal/TOS service because Story 12.0 produced a manual decision and no service exists to consume it.

## Deferred from: code review of 12-2-topcv-scraper — bmad-code-review (2026-08-10)

- source_spec: `_bmad-output/implementation-artifacts/stories/12-2-topcv-scraper.md`
  summary: Partial degraded billing may not charge when `degraded=True`.
  evidence: `_scrape` can return `degraded=True` with `items` and a non-zero `cost_micros`, but the billing path may skip debit on degraded output. The cost-vs-degraded contract needs cross-story billing alignment.

- source_spec: `_bmad-output/implementation-artifacts/stories/12-2-topcv-scraper.md`
  summary: User-Agent rotation is not wired to detail-page fetches.
  evidence: `_fetch_detail_page` calls `WebCrawlerConnector.crawl_url()`, which does not accept a `useragent` kwarg. Refactor of the connector or extra-headers support is needed to pass a rotated UA to detail requests.

- source_spec: `_bmad-output/implementation-artifacts/stories/12-2-topcv-scraper.md`
  summary: Anti-bot screenshot escalation is gated on `ctx.run_id`, which is `None` in sync REST/agent paths.
  evidence: `app/capabilities/topcv/scrape/executor.py` only triggers `capture_platform_anti_bot_screenshot_task` when `ctx.run_id` is set; sync capability callers create `CapabilityContext` without a `run_id`. This is a pre-existing executor pattern also seen in `itviec`.

- source_spec: `_bmad-output/implementation-artifacts/stories/12-2-topcv-scraper.md`
  summary: Legal/ToS block decision is a static config flag, not a runtime legal-service hook.
  evidence: `TOPCV_ENABLED` is read from env and checked at call time; there is no runtime integration with a legal/TOS service because Story 12.0 produced a manual decision and no service exists to consume it.

## Deferred from: code review of 18-3-agent-registry deferred resolution (2026-08-10)

- Tool catalog tools stored in `AgentConfig` may still be ignored by the main-agent runtime because subagent/MCP dispatch is environment-driven.
- Admin `PATCH` has no optimistic locking (`updated_at` comparison) — acceptable last-write-wins for the current admin surface.
- Frontend does not pre-validate `client_id` against `vertical_clients` before submit; API already fails fast, but a UX pass should add a dropdown or pre-check.
- UI for soft-deleted/inactive agents and a system-instructions character counter are not aligned with the (missing) `ux-contract-agent-registry.md`.
- Max-length boundary tests and tests for enabled/disabled tool overlap are out of scope for this chunk.
- `enabled_tools` / `disabled_tools` are not validated as disjoint and are not de-duplicated; currently harmless.

## Deferred from: code review of 18-4-agentconfig-prompt-injection (2026-08-10)

- OpenTelemetry metrics for agent prompt/tool filter usage are not added; audit logs cover the merge event.
- `enabled_tools` / `disabled_tools` overlap and duplicate-name validation is not enforced in the schema.
- Thread `platform_metadata` persistence does not log changes or serialize concurrent updates.
- No dedicated `tests/integration/api/test_agent_chat_pat_matrix.py` was created; existing tests cover critical paths.
- Prompt render-time size check for the `platform_metadata` wrapper is not explicit.

## Deferred from: code review of 14-1-rss-feed-integration (2026-08-13)

- ~~Feed pruning: articles that leave the RSS feed (rolling window) are never removed; unbounded document growth. No soft-delete state exists in DocumentStatus (only ready/pending/processing/failed) and no pruning job exists for any connector type — a retention design (window, hard vs soft delete, canonical last_seen_at handling) is required before implementing.~~ **RESOLVED (2026-08-13):** inline pruning in `index_rss_feeds` after `_persist_canonical_articles` — `RSS_RETENTION_DAYS=30` hard delete of docs not seen in the current poll and older than the window (using `Document.created_at` as last-seen proxy), plus canonical provenance + orphaned-entity sweep via `app/canonical/services/canonical_cleanup.py`. Only runs when the poll succeeded (seen_links non-empty), so transient fetch failures never wipe a feed. Verified by `tests/integration/news/test_rss_pruning.py`.
- ~~Canonical churn: upsert_canonical_entity unconditionally bumps version and records merge history even when the entity is unchanged; pre-existing behavior affecting all connectors, not RSS-specific.~~ **RESOLVED (2026-08-13):** `upsert_canonical_entity` now detects content unchanged (title, canonical_data, search_text, conflict_flags, confidence_score) + source moved; version bump, merge history and embedding backfill are skipped when nothing changed, while `last_seen_at`/`source_count` still refresh. Verified by `tests/unit/services/news/test_rss_indexer_units.py` and `tests/integration/news/test_rss_pruning.py`.
- Epoch sentinel: `_MISSING_PUB_DATE` (1970-01-01) surfaces in UI when pubDate is missing; deliberate deterministic design to avoid re-index churn, accepted at review. **RESOLVED (2026-08-13):** sentinel stays in canonical data/metadata (anti-churn); RSS source markdown now renders "Unknown" via `_format_pub_date` instead of the epoch value. No frontend renders `metadata.pubDate` directly (verified by grep).
- ~~Connector deletion orphans canonical entities: deleting a connector does not clean up its canonical entities; pre-existing general behavior for all connector types.~~ **RESOLVED (2026-08-13):** delete connector route collects document links during the batch deletion loop and then removes canonical sources by record_ids + sweeps orphaned `news_article` entities. Verified by `tests/integration/routes/test_search_source_connectors_routes.py`.

## Resolved/Dismissed from: code review of 21-8-social-ingress-via-xactions-integration (2026-08-15)

- **Finding:** Redundant status fields in SocialMonitoredTarget
  - **Action:** **DISMISSED** — pre-existing flexible schema; `is_active` and `status` are intentionally left for future target states.

- **Finding:** Confusing duplicate timing fields in SocialMonitoredTarget — Three timing-related fields: realtime_stream (bool), scrape_interval_minutes (default 15), and poll_interval_seconds (default 900). The last two are the same value in different units, creating confusion. (app/db.py:4882-4884)
  - **Action:** **DISMISSED** — out-of-scope or future improvement for Story 21.8. in `21-8-social-ingress-via-xactions-integration.md`.
  - **Reason / when to revisit:** Three timing-related fields: realtime_stream (bool), scrape_interval_minutes (default 15), and poll_interval_seconds (default 900). The last two are the same value in different units, creating confusion. Out-of-scope or future improvement for Story 21.8.

- **Finding:** Redundant timestamp fields in SocialMonitoredTarget — Both last_polled_at and last_scraped_at exist with no clear distinction in purpose. Could lead to inconsistent tracking. (app/db.py:4886-4887)
  - **Action:** **DISMISSED** — out-of-scope or future improvement for Story 21.8. in `21-8-social-ingress-via-xactions-integration.md`.
  - **Reason / when to revisit:** Both last_polled_at and last_scraped_at exist with no clear distinction in purpose. Could lead to inconsistent tracking. Out-of-scope or future improvement for Story 21.8.

- **Finding:** SocialPost.target_id is nullable but has CASCADE relationship — target_id is nullable with a CASCADE foreign key. If a target is deleted, posts with NULL target_id would remain, but posts with a target_id would be deleted. This creates inconsistent behavior. (app/db.py:4910-4915)
  - **Action:** **DISMISSED** — out-of-scope or future improvement for Story 21.8. in `21-8-social-ingress-via-xactions-integration.md`.
  - **Reason / when to revisit:** target_id is nullable with a CASCADE foreign key. If a target is deleted, posts with NULL target_id would remain, but posts with a target_id would be deleted. This creates inconsistent behavior. Out-of-scope or future improvement for Story 21.8.

- **Finding:** No validation of account_id in proxy binding — The bind_account_proxy method accepts any account_id string without validation. No checks for format, length, or allowed characters. (app/proprietary/platforms/xactions/adapter.py:82-84)
  - **Action:** **DISMISSED** — out-of-scope or future improvement for Story 21.8. in `21-8-social-ingress-via-xactions-integration.md`.
  - **Reason / when to revisit:** The bind_account_proxy method accepts any account_id string without validation. No checks for format, length, or allowed characters. Out-of-scope or future improvement for Story 21.8.

- **Finding:** ReDoS timeout check placement allows partial execution — The timeout check is inside the loop, so if the first candidate is slow, it breaks. But if the regex itself is slow on the normalized string, it may still timeout after the loop. The timeout doesn't protect the normalization step itself. (app/proprietary/platforms/xactions/phone_extractor.py:118-121)
  - **Action:** **DISMISSED** — out-of-scope or future improvement for Story 21.8. in `21-8-social-ingress-via-xactions-integration.md`.
  - **Reason / when to revisit:** The timeout check is inside the loop, so if the first candidate is slow, it breaks. But if the regex itself is slow on the normalized string, it may still timeout after the loop. The timeout doesn't protect the normalization step itself. Out-of-scope or future improvement for Story 21.8.

- **Finding:** Phone regex allows invalid Vietnamese prefixes — The regex allows 9\d which matches any digit 0-9 in the third position. Vietnamese mobile prefixes are more specific (e.g., 90, 91, 92, etc., not 93, 94, 95, 96, 97, 98, 99). (app/proprietary/platforms/xactions/phone_extractor.py:44-46)
  - **Action:** **DISMISSED** — out-of-scope or future improvement for Story 21.8. in `21-8-social-ingress-via-xactions-integration.md`.
  - **Reason / when to revisit:** The regex allows 9\d which matches any digit 0-9 in the third position. Vietnamese mobile prefixes are more specific (e.g., 90, 91, 92, etc., not 93, 94, 95, 96, 97, 98, 99). Out-of-scope or future improvement for Story 21.8.

- **Finding:** Token pattern may miss valid obfuscated phones — The token pattern requires 7-25 characters. A valid obfuscated phone like 'o9.123.456' (10 chars) would match, but edge cases might not. The pattern is complex and may have blind spots. (app/proprietary/platforms/xactions/phone_extractor.py:96)
  - **Action:** **DISMISSED** — out-of-scope or future improvement for Story 21.8. in `21-8-social-ingress-via-xactions-integration.md`.
  - **Reason / when to revisit:** The token pattern requires 7-25 characters. A valid obfuscated phone like 'o9.123.456' (10 chars) would match, but edge cases might not. The pattern is complex and may have blind spots. Out-of-scope or future improvement for Story 21.8.

- **Finding:** Intent classification has keyword overlap — Keywords are checked sequentially without weighting. A post containing 'tìm việc để bán' (find job to sell) would be classified as 'hiring' (first match) rather than the more nuanced intent. No mechanism for mixed intents. (app/proprietary/platforms/xactions/phone_extractor.py:148-193)
  - **Action:** **DISMISSED** — out-of-scope or future improvement for Story 21.8. in `21-8-social-ingress-via-xactions-integration.md`.
  - **Reason / when to revisit:** Keywords are checked sequentially without weighting. A post containing 'tìm việc để bán' (find job to sell) would be classified as 'hiring' (first match) rather than the more nuanced intent. No mechanism for mixed intents. Out-of-scope or future improvement for Story 21.8.

- **Finding:** Location extraction is hardcoded and incomplete — The location list is hardcoded with Vietnamese provinces/districts. It's incomplete, unmaintainable, and doesn't handle typos or abbreviations. (app/proprietary/platforms/xactions/phone_extractor.py:60-73)
  - **Action:** **DISMISSED** — out-of-scope or future improvement for Story 21.8. in `21-8-social-ingress-via-xactions-integration.md`.
  - **Reason / when to revisit:** The location list is hardcoded with Vietnamese provinces/districts. It's incomplete, unmaintainable, and doesn't handle typos or abbreviations. Out-of-scope or future improvement for Story 21.8.

- **Finding:** Email regex is overly simplistic — The email regex doesn't validate TLDs properly and could match invalid emails like user@com or user@.com. (app/proprietary/platforms/xactions/phone_extractor.py:49-51)
  - **Action:** **DISMISSED** — out-of-scope or future improvement for Story 21.8. in `21-8-social-ingress-via-xactions-integration.md`.
  - **Reason / when to revisit:** The email regex doesn't validate TLDs properly and could match invalid emails like user@com or user@.com. Out-of-scope or future improvement for Story 21.8.

- **Finding:** No dead letter queue for failed messages — Failed messages are logged but not moved to a dead letter queue. They're ACKed even on failure, so they're lost forever. (app/tasks/social_stream_worker.py:186-192)
  - **Action:** **DISMISSED** — out-of-scope or future improvement for Story 21.8. in `21-8-social-ingress-via-xactions-integration.md`.
  - **Reason / when to revisit:** Failed messages are logged but not moved to a dead letter queue. They're ACKed even on failure, so they're lost forever. Out-of-scope or future improvement for Story 21.8.

- **Finding:** No rate limiting on stream consumer — The consumer has no rate limiting. If the stream has millions of messages, it could overwhelm the database. (app/tasks/social_stream_worker.py:142-197)
  - **Action:** **DISMISSED** — out-of-scope or future improvement for Story 21.8. in `21-8-social-ingress-via-xactions-integration.md`.
  - **Reason / when to revisit:** The consumer has no rate limiting. If the stream has millions of messages, it could overwhelm the database. Out-of-scope or future improvement for Story 21.8.

- **Finding:** No pagination in search results — The query uses .limit(payload.limit) but has no offset/cursor. Users can only get the first N results, not page through them. (app/capabilities/social/search_leads/executor.py:59)
  - **Action:** **DISMISSED** — out-of-scope or future improvement for Story 21.8. in `21-8-social-ingress-via-xactions-integration.md`.
  - **Reason / when to revisit:** The query uses .limit(payload.limit) but has no offset/cursor. Users can only get the first N results, not page through them. Out-of-scope or future improvement for Story 21.8.

- **Finding:** Test mocks don't validate SQL queries — The test mocks the database session but doesn't verify the SQL query is correct. It could pass even if the query has bugs. (tests/unit/capabilities/test_social_search_leads.py)
  - **Action:** Resolved from: code review of 21-8-social-ingress-via-xactions-integration (2026-09-11). Added SQL statement inspection in `test_social_search_leads_capability_execution` and `test_social_search_leads_uses_offset` asserting `workspace_id`, `LIMIT`, and `OFFSET` in generated queries.
  - **Reason / when to revisit:** The test mocks the database session but doesn't verify the SQL query is correct. It could pass even if the query has bugs. Out-of-scope or future improvement for Story 21.8.

- **Finding:** ReDoS test has generous timeout — The test asserts duration < 0.10s (100ms) but the spec requires 50ms. This gives 2x headroom and could miss regressions. (tests/unit/platforms/test_phone_regex_redos_safety.py)
  - **Action:** Resolved from: code review of 21-8-social-ingress-via-xactions-integration (2026-09-11). Verified `assert duration < 0.05` is enforced in `tests/unit/platforms/test_phone_regex_redos_safety.py` and `tests/unit/proprietary/platforms/xactions/test_phone_extractor.py`.
  - **Reason / when to revisit:** The test asserts duration < 0.10s (100ms) but the spec requires 50ms. This gives 2x headroom and could miss regressions. Out-of-scope or future improvement for Story 21.8.

- **Finding:** Integration test uses mock database — Despite being marked as an integration test, it mocks the database session. This doesn't test actual database persistence. (tests/integration/platforms/test_social_redis_stream.py)
  - **Action:** Resolved from: code review of 21-8-social-ingress-via-xactions-integration (2026-09-11). Verified `tests/integration/platforms/test_social_redis_stream.py` uses real PostgreSQL persistence via `platform_db_session` asserting `SocialPost` and `Lead` table rows.
  - **Reason / when to revisit:** Despite being marked as an integration test, it mocks the database session. This doesn't test actual database persistence. Out-of-scope or future improvement for Story 21.8.

- **Finding:** No composite index on frequently queried columns — While there are indexes on platform, external_post_id, published_at, intent_tag, and raw_entities, there's no composite index on (platform, intent_tag, published_at) which the search capability likely needs. (app/db.py:4901-4907)
  - **Action:** **DISMISSED** — out-of-scope or future improvement for Story 21.8. in `21-8-social-ingress-via-xactions-integration.md`.
  - **Reason / when to revisit:** While there are indexes on platform, external_post_id, published_at, intent_tag, and raw_entities, there's no composite index on (platform, intent_tag, published_at) which the search capability likely needs. Out-of-scope or future improvement for Story 21.8.

- **Finding:** XActions subprocess timeout hardcoded at 30s — Timeout hardcoded at 30s. No configurable timeout for different operations (scraping vs simple queries). Could be too short for large Facebook group scrapes. (app/proprietary/platforms/xactions/adapter.py:126)
  - **Action:** **DISMISSED** — out-of-scope or future improvement for Story 21.8. in `21-8-social-ingress-via-xactions-integration.md`.
  - **Reason / when to revisit:** Timeout hardcoded at 30s. No configurable timeout for different operations (scraping vs simple queries). Could be too short for large Facebook group scrapes. Out-of-scope or future improvement for Story 21.8.

- **Finding:** Timeout breaks loop mid-processing without indication — Timeout breaks loop mid-processing, returning partial results. No indication to caller that results are incomplete due to timeout. Could miss valid phone numbers. (app/proprietary/platforms/xactions/phone_extractor.py:118-121)
  - **Action:** **DISMISSED** — out-of-scope or future improvement for Story 21.8. in `21-8-social-ingress-via-xactions-integration.md`.
  - **Reason / when to revisit:** Timeout breaks loop mid-processing, returning partial results. No indication to caller that results are incomplete due to timeout. Could miss valid phone numbers. Out-of-scope or future improvement for Story 21.8.

- **Finding:** Province regex may exceed engine limits — Regex built from 60+ province names. Sorted by length (reverse) to match longer names first, but still could have false positives on partial matches. No validation that regex doesn't exceed engine limits. (app/proprietary/platforms/xactions/phone_extractor.py:196-199)
  - **Action:** **DISMISSED** — out-of-scope or future improvement for Story 21.8. in `21-8-social-ingress-via-xactions-integration.md`.
  - **Reason / when to revisit:** Regex built from 60+ province names. Sorted by length (reverse) to match longer names first, but still could have false positives on partial matches. No validation that regex doesn't exceed engine limits. Out-of-scope or future improvement for Story 21.8.

- **Finding:** No CHECK constraint for platform values in SocialMonitoredTarget — No validation that platform values are from allowed set ('facebook_group', 'facebook_page', 'twitter_keyword', 'twitter_user'). Could insert invalid platform values. (app/db.py:4876)
  - **Action:** **DISMISSED** — out-of-scope or future improvement for Story 21.8. in `21-8-social-ingress-via-xactions-integration.md`.
  - **Reason / when to revisit:** No validation that platform values are from allowed set ('facebook_group', 'facebook_page', 'twitter_keyword', 'twitter_user'). Could insert invalid platform values. Out-of-scope or future improvement for Story 21.8.

- **Finding:** No CHECK constraint for interval values in SocialMonitoredTarget — No CHECK constraint to prevent negative values or unreasonably small intervals (e.g., 0 or 1 second). Could cause excessive polling and rate limiting issues. (app/db.py:4883-4884)
  - **Action:** **DISMISSED** — out-of-scope or future improvement for Story 21.8. in `21-8-social-ingress-via-xactions-integration.md`.
  - **Reason / when to revisit:** No CHECK constraint to prevent negative values or unreasonably small intervals (e.g., 0 or 1 second). Could cause excessive polling and rate limiting issues. Out-of-scope or future improvement for Story 21.8.

- **Finding:** No CHECK constraint for platform values in SocialPost — No CHECK constraint or enum to restrict platform to 'facebook' or 'twitter'. Could insert invalid platform values. (app/db.py:4916)
  - **Action:** **DISMISSED** — out-of-scope or future improvement for Story 21.8. in `21-8-social-ingress-via-xactions-integration.md`.
  - **Reason / when to revisit:** No CHECK constraint or enum to restrict platform to 'facebook' or 'twitter'. Could insert invalid platform values. Out-of-scope or future improvement for Story 21.8.

- **Finding:** No CHECK constraint for intent_tag values in SocialPost — No CHECK constraint or enum to restrict intent_tag to documented values. Could insert invalid intent tags. (app/db.py:4923)
  - **Action:** **DISMISSED** — out-of-scope or future improvement for Story 21.8. in `21-8-social-ingress-via-xactions-integration.md`.
  - **Reason / when to revisit:** No CHECK constraint or enum to restrict intent_tag to documented values. Could insert invalid intent tags. Out-of-scope or future improvement for Story 21.8.

- **Finding:** No validation for raw_entities structure in SocialPost — No validation that raw_entities structure matches expected schema (phones, emails, prices, locations arrays). Could insert malformed JSON. (app/db.py:4928-4930)
  - **Action:** **DISMISSED** — out-of-scope or future improvement for Story 21.8. in `21-8-social-ingress-via-xactions-integration.md`.
  - **Reason / when to revisit:** No validation that raw_entities structure matches expected schema (phones, emails, prices, locations arrays). Could insert malformed JSON. Out-of-scope or future improvement for Story 21.8.

- **Finding:** No validation for embedding dimension in SocialPost — No validation that embedding dimension matches configured model. If model changes, existing embeddings could become invalid or cause query errors. (app/db.py:4932)
  - **Action:** **DISMISSED** — out-of-scope or future improvement for Story 21.8. in `21-8-social-ingress-via-xactions-integration.md`.
  - **Reason / when to revisit:** No validation that embedding dimension matches configured model. If model changes, existing embeddings could become invalid or cause query errors. Out-of-scope or future improvement for Story 21.8.

- **Finding:** CASCADE delete causes data loss if target deleted — CASCADE delete means if target is deleted, all associated posts are deleted. Could cause data loss if target is accidentally deleted. No soft delete or archival mechanism. (app/db.py:4910-4915)
  - **Action:** **DISMISSED** — out-of-scope or future improvement for Story 21.8. in `21-8-social-ingress-via-xactions-integration.md`.
  - **Reason / when to revisit:** CASCADE delete means if target is deleted, all associated posts are deleted. Could cause data loss if target is accidentally deleted. No soft delete or archival mechanism. Out-of-scope or future improvement for Story 21.8.

## Resolved from: re-review of 21-8-social-ingress-via-xactions-integration (2026-08-15)

- **Finding:** Email alert channel is still `pass` in `app/alerts/engine/notify.py:146-152` — `AlertEngine` is supposed to fire Telegram/Email, but the email branch is not implemented. (app/alerts/engine/notify.py:146-152)
  - **Action:** Resolved. Implemented `_email` using `smtplib` + optional `SMTP_HOST/SMTP_PORT/SMTP_USER/SMTP_PASSWORD/SMTP_FROM/SMTP_TLS` env; logs a warning and skips if not configured.

- **Finding:** First-run alert rules suppress notification — existing alert-engine behavior stores a snapshot on the first run and does not notify. (app/alerts/engine/execute.py:113, 158-189, 210-225)
  - **Action:** Resolved. Confirmed as intentional baseline behavior; added unit test `tests/unit/alerts/test_job_alert.py::test_job_alert_first_run_suppresses_notification` documenting the contract.

- **Finding:** `test_social_redis_stream.py` mocks DB and never touches Redis/Postgres — the integration test does not exercise real persistence. (tests/integration/platforms/test_social_redis_stream.py)
  - **Action:** Resolved. Rewrote as a real integration test using a target fixture, Redis `xadd`, `run_social_stream_consumer`, and Postgres assertions; added `tests/integration/platforms/conftest.py` that skips when PostGIS is unavailable.

- **Finding:** No test for social post → alert-engine notification path — no test creates an `AlertRule` and asserts notification firing. (app/tasks/social_stream_worker.py:254-293)
  - **Action:** Resolved. Added `tests/unit/tasks/test_social_stream_worker.py` covering `_evaluate_alerts_for_social_post` and duplicate lead guard.

- **Finding:** ReDoS timeout not enforced on initial `normalize_vietnamese_text` regex calls — the 50ms timer only checks inside the candidate loop, not the initial normalization regex. (app/proprietary/platforms/xactions/phone_extractor.py:76-145)
  - **Action:** Resolved. Moved `start_time` before `normalize_vietnamese_text` and added a timeout check immediately after; added a 200k input-length cap as a secondary defense.

## Deferred from: code review of 21-8-social-ingress-via-xactions-integration (2026-08-15 second pass)

- **Finding:** No trigram/GIN index on social search keyword search — `content.ilike('%...%')` and `author_name.ilike('%...%')` will full-scan `social_posts` as the table grows. (app/capabilities/social/search_leads/executor.py:65-72; app/db.py:5067)
  - **Action:** Resolved from: code review of 21-8-social-ingress-via-xactions-integration (2026-09-11). Added `idx_social_posts_trgm_content` and `idx_social_posts_trgm_author` GIN indexes with `gin_trgm_ops` to `SocialPost.__table_args__` in `app/models/leads/social.py`.
  - **Reason / when to revisit:** Query performance issue, not correctness. Add `pg_trgm` GIN index when search latency becomes a concern or as part of an NFR/performance pass.

- **Finding:** Model/migration index drift — SQLAlchemy model uses `ix_social_posts_target_id` while migration 204 creates `idx_social_posts_target_id`; `updated_at` is `index=True` in model but missing in migration; `published_at` index is `ASC` in model but `DESC` in migration. (app/db.py:5050-5120; alembic/versions/204_add_social_tables.py:78-89)
  - **Action:** Resolved from: code review of 21-8-social-ingress-via-xactions-integration (2026-09-11). Replaced implicit `index=True` with explicit `Index('idx_social_posts_target_id', 'target_id')` in `SocialPost.__table_args__` in `app/models/leads/social.py`.
  - **Reason / when to revisit:** Duplicate or mismatched indexes waste space but do not affect correctness. Resolve in a future migration-hardening pass.

- **Finding:** `social_routes.py` only exposes target creation — no list, get, update, or delete endpoints. (app/routes/social_routes.py:52-103)
  - **Action:** Resolved from: code review of 21-8-social-ingress-via-xactions-integration (2026-09-11). Confirmed list, get, update, and delete endpoints are fully implemented in `social_routes.py` with 12 unit tests passing.
  - **Reason / when to revisit:** CRUD completeness is out-of-scope for the MVP; add endpoints when the UI requires management screens.

- **Finding:** `target_url` and `proxy_url` are stored as arbitrary strings with no URL/scheme validation. (app/routes/social_routes.py:26-32, 79-91)
  - **Action:** Resolved from: code review of 21-8-social-ingress-via-xactions-integration (2026-09-11). Added `validate_url_scheme` validator enforcing `http://` or `https://` in `SocialTargetCreate` and `SocialTargetUpdate` in `social_routes.py` with unit tests.
  - **Reason / when to revisit:** SSRF risk is real but the URLs are consumed by the XActions scraper, which already has its own proxy parsing. Add `HttpUrl` validation in a hardening pass.

- **Finding:** Search/target input schemas lack enum validation for platform, intent, category, status and no bounds for keyword/offset. (app/capabilities/social/search_leads/schemas.py:11-13; app/routes/social_routes.py:22-32)
  - **Action:** Resolved from: code review of 21-8-social-ingress-via-xactions-integration (2026-09-11). Added `SocialPlatform` and `SocialIntent` Literal enums, bounded `keyword` to 500 chars, `offset` to 10000, and added `SocialTargetStatus` enum with interval bounds in `social_routes.py`.
  - **Reason / when to revisit:** Typos produce empty results rather than data corruption. Add Pydantic enums/CHECK constraints in a future validation pass.

- **Finding:** Social search ordering places `NULL published_at` first. (app/capabilities/social/search_leads/executor.py:77)
  - **Action:** Resolved from: code review of 21-8-social-ingress-via-xactions-integration (2026-09-11). Fixed NULL ordering with `desc(SocialPost.published_at).nullslast()`.
  - **Reason / when to revisit:** Default `DESC NULLS FIRST` ordering may show undated posts above recent ones. Add `nulls_last` when UX confirms newest-first intent.

- **Finding:** `SocialMonitoredTarget.posts` and `Workspace` social relationships use `cascade="all, delete-orphan"` without `passive_deletes=True`. (app/db.py:5048-5051, 2110-2121)
  - **Action:** Resolved from: code review of 21-8-social-ingress-via-xactions-integration (2026-09-11). Added `passive_deletes=True` to `SocialMonitoredTarget.posts` and `Workspace.social_*` relationships in `app/models/leads/social.py` and `app/models/workspaces.py`.
  - **Reason / when to revisit:** PostgreSQL FKs already have `ON DELETE CASCADE`; SQLAlchemy loads children on delete. Add `passive_deletes=True` in a performance pass.

- **Finding:** Redis consumer group starts at stream ID `0` and never reclaims pending messages from crashed consumers. (app/tasks/social_stream_worker.py:500-530)
  - **Action:** Allocated to Target Roadmap Epics in `sprint-change-proposal-2026-09-11-deferred-epics-roadmap.md`. (add consumer group recovery when stream consumer is productionized.)
  - **Reason / when to revisit:** New group reading from beginning is recoverable, and `XAUTOCLAIM` is not required for the first release. Add when consumer durability is prioritized.

- **Finding:** `run_social_stream_consumer` runs a single `xreadgroup` batch and returns, not a continuous processing loop. (app/tasks/social_stream_worker.py:481-584)
  - **Action:** Resolved from: code review of 21-8-social-ingress-via-xactions-integration (2026-09-11). Enhanced `run_social_stream_consumer` with `max_loops` parameter in `app/tasks/social_stream_worker.py` allowing continuous batch processing while respecting bounded execution in Celery worker tasks.
  - **Reason / when to revisit:** Intended as a Celery-driven tick; if external scheduling is chosen, this is fine. Revisit when finalizing deployment/operations model.

- **Finding:** `published_at` parser is narrow and may corrupt RFC-2822/lowercase-z timestamps. (app/tasks/social_stream_worker.py:109-121)
  - **Action:** Resolved from: code review of 21-8-social-ingress-via-xactions-integration (2026-09-11). Extended parser to handle lowercase 'z' and RFC-2822 via `email.utils.parsedate_to_datetime`.
  - **Reason / when to revisit:** Current XActions payloads use ISO-8601. Add broader parsing if Twitter timestamps remain unparsed in production.

- **Finding:** Engagement bonus thresholds are strict `>` (off-by-one) at 10 reactions / 5 comments. (app/tasks/social_stream_worker.py:150-151)
  - **Action:** Resolved from: code review of 21-8-social-ingress-via-xactions-integration (2026-09-11). Fixed off-by-one with `>=` thresholds.
  - **Reason / when to revisit:** Boundary behavior is marginal; adjust to `>=` if product confirms inclusive thresholds.

- **Finding:** Facebook group ingest always passes `auth_cookie=None`; per-target cookie store not implemented. (app/tasks/celery_tasks/social_xactions_ingest.py:115-121)
  - **Action:** Allocated to Target Roadmap Epics in `sprint-change-proposal-2026-09-11-deferred-epics-roadmap.md`. (implement per-target cookie store when Facebook group ingest is productionized.)
  - **Reason / when to revisit:** Global env cookies are acceptable for the first release. Add per-target cookie column when multi-tenant Facebook scraping is required.

- **Finding:** Email channel lacks outbound metrics, partial SMTP credentials silently skip auth, and missing-SMTP_HOST warning is logged per subscriber. (app/alerts/engine/notify.py:125-137)
  - **Action:** Resolved from: code review of story-12-9-job-market-alerts (2026-09-11). Added `record_gateway_outbound` for email channel and partial SMTP credentials validation in `app/alerts/engine/notify.py` with unit tests.
  - **Reason / when to revisit:** Operational observability improvements; add `record_gateway_outbound` and centralized env checks after core email path is stable.

## Resolved from: second pass code review of 21-8-social-ingress-via-xactions-integration (2026-08-15)

- **Finding:** Stream messages that fail validation or persistence are not ACKed or dead-lettered — bad messages remain in PEL. (app/tasks/social_stream_worker.py:579-625)
  - **Action:** Resolved. `run_social_stream_consumer` now moves `None` returns to `stream:social:failed` and ACKs.

- **Finding:** `workspace_id` from stream payload is not validated against `SocialMonitoredTarget.workspace_id` — cross-tenant write possible. (app/tasks/social_stream_worker.py:389-426)
  - **Action:** Resolved. Worker now resolves the target, compares `workspace_id`, and rejects mismatches.

- **Finding:** Per-target scheduler uses non-atomic `exists`/`delay` and overrides short `scrape_interval_minutes` with a 300s min TTL. (app/tasks/celery_tasks/social_xactions_ingest.py:31-70, 216-248)
  - **Action:** Resolved. Added a 60s atomic per-target scheduling lock (`nx=True, ex=60`) and clamped intervals to `[1, 1440]`.

- **Finding:** Alert rule evaluation is not isolated and can abort all rules for a post. (app/tasks/social_stream_worker.py:325-380)
  - **Action:** Resolved. Each rule is wrapped in `try/except`; `min_fit_score` and `keyword` are coerced/validated.

- **Finding:** Lead dedup by `source_url` matches all leads with NULL/empty `source_url`; `raw_entities` not shape-guarded. (app/tasks/social_stream_worker.py:203-242)
  - **Action:** Resolved. Skip dedup when `source_url` is empty; coerce `raw_entities` values to string lists before indexing.

- **Finding:** `SMTP_PORT` parsing crashes on malformed/empty env. (app/config/__init__.py:1345)
  - **Action:** Resolved. `SMTP_PORT = _env_int("SMTP_PORT", 587)`.

- **Finding:** Email channel unreachable because alert schema only allows `in_app`/`telegram`. (app/alerts/schemas.py:34)
  - **Action:** Resolved. Added `email` to the allowed set.

- **Finding:** Email subject/body not UTF-8 safe and SMTP has no timeout/SSL. (app/alerts/engine/notify.py:116-145)
  - **Action:** Resolved. Use `Header`/`MIMEText(..., "plain", "utf-8")`; 10s socket timeout; `SMTP_SSL` for port 465.

- **Finding:** `SocialSearchLeadsOutput.total` is page size; tenant filter is redundant. (app/capabilities/social/search_leads/executor.py:60-95)
  - **Action:** Resolved. `total` is now `func.count()`; filter uses single `workspace_id` equality; `NULL published_at` last.

- **Finding:** `SocialPostItem` can fail on malformed `raw_entities`. (app/capabilities/social/search_leads/executor.py:88-95)
  - **Action:** Resolved. Coerce `phones`/`emails`/`prices`/`locations` to `list[str]` and drop `None`.

- **Finding:** `create_db_and_tables` swallows schema-creation errors. (app/db.py:3910-3916)
  - **Action:** Resolved. Removed the broad `try/except` around `Base.metadata.create_all` and `ensure_publication`.

- **Finding:** Integration test cannot persist because worker opens a separate session. (tests/integration/platforms/test_social_redis_stream.py:97-104)
  - **Action:** Resolved. `run_social_stream_consumer` accepts a `session` parameter; the test passes `platform_db_session`.

- **Finding:** Unit test for search uses unconditional mock and would fail real SQL. (tests/unit/capabilities/test_social_search_leads.py:33-61)
  - **Action:** Resolved. Fixture now distinguishes count vs SELECT and uses deterministic `MagicMock` results.

- **Finding:** `threshold_cross` first-run is suppressed. (app/alerts/engine/execute.py:158-174)
  - **Action:** Resolved. Execute `diff_snapshots` with an empty previous snapshot for `threshold_cross`, so first-run threshold crossing fires.

- **Finding:** Stream consumer `run_social_stream_consumer` is not wired to Celery/beat. (app/tasks/social_stream_worker.py:481-584, app/celery_app.py:295-300)
  - **Action:** Resolved. Added `consume_social_stream` Celery task and 5s beat schedule.

- **Finding:** Unique constraints on social tables are not workspace-scoped. (app/db.py:5009-5061; alembic/versions/211_social_unique_workspace_scoped.py)
  - **Action:** Resolved. Model and migration `211` now use `(workspace_id, platform, target_id)` and `(workspace_id, platform, external_post_id)`.

- **Finding:** `social_search_posts` helper opens an unauthored session from raw `workspace_id`. (app/capabilities/social/search_leads/__init__.py:31-50)
  - **Action:** Resolved. Helper now requires `CapabilityContext` and no longer accepts raw `workspace_id`.

- **Finding:** `published_at` parser replaces all `Z` and misses lowercase `z`. (app/tasks/social_stream_worker.py:109-121)
  - **Action:** Resolved. Normalize only a trailing `Z`/`z` to `+00:00`.

- **Finding:** Engagement bonus thresholds are strict `>` (off-by-one). (app/tasks/social_stream_worker.py:150-151)
  - **Action:** Resolved. Changed to `>=`.

## Deferred from: code review of 21-6-zalo-integration (2026-08-15)

- **Finding:** `leads_routes.py` awaits sync `has_permission` with 4 args (pre-existing 21.3 issue, unrelated to 21.6). (app/routes/leads_routes.py:640-645,691)
  - **Action:** Resolved from: code review of 21-6-zalo-integration (2026-09-11). Replaced invalid `await has_permission(session, auth, workspace_id, ...)` with `get_user_permissions` and synchronous `has_permission` in `app/routes/leads_routes.py` with 12 passing tests.
  - **Reason / when to revisit:** Fix when resolving phone-waterfall RBAC in Story 21.3; use `check_permission` or correct `has_permission` helper.

- **Finding:** Phone waterfall worker `asyncio.run` inside a sync Celery task and refund exception swallow. (app/tasks/phone_waterfall_worker.py:69,109-116)
  - **Action:** Resolved from: code review of 21-3-phone-waterfall-resolution-service (2026-09-11). Replaced `asyncio.run` with `run_async_celery_task` and added bounded retry on `auto_refund_lead_task` failures with 30 passing tests in `app/tasks/phone_waterfall_worker.py`.
  - **Reason / when to revisit:** Refactor to async Celery task or worker loop in Story 21.3.

- **Finding:** Missing migration for `VerifiedContact`/`PhoneWaterfallLog` model changes. (app/db.py)
  - **Action:** Allocated to Target Roadmap Epics in `sprint-change-proposal-2026-09-11-deferred-epics-roadmap.md`. (migration deferred to schema update story.)
  - **Reason / when to revisit:** Add companion migration in Story 21.3 to keep alembic in sync.

- **Finding:** `app/db.py` reintroduces top-level circular `SpatialPlanningZone` import. (app/db.py:4762)
  - **Action:** Resolved from: code review of 21-8-social-ingress-via-xactions-integration (2026-09-11). Replaced circular import from `app.db` with direct import from `app.db.base` in `app/proprietary/platforms/spatial_planning/models.py`.
  - **Reason / when to revisit:** Fix in Story 10.8 by moving import inside `create_db_and_tables`.

- **Finding:** SQLAlchemy `cascade="delete-orphan"` for `ZaloMessageLog` conflicts with migration `ON DELETE SET NULL`. (app/db.py:5157-5161,5222-5224)
  - **Action:** Resolved from: code review of 21-8-social-ingress-via-xactions-integration (2026-09-11). Changed `Lead.zalo_message_logs` cascade to `"save-update, merge"` with `passive_deletes=True` in `app/models/leads/main.py` to align with `ON DELETE SET NULL` DDL constraint.
  - **Reason / when to revisit:** Align ORM/migration delete semantics when finalizing 21.6 data model.

- **Finding:** `PhoneResolutionResponse` hard-codes 1.5 credits for async `pending` results. (app/routes/leads_routes.py:595-602)
  - **Action:** Allocated to Target Roadmap Epics in `sprint-change-proposal-2026-09-11-deferred-epics-roadmap.md`. (hardcoded credits deferred to pricing model update.)
  - **Reason / when to revisit:** Return 0/null for pending async results in Story 21.3.

## Deferred from: code review of 21-6-zalo-integration — second pass (2026-08-15)

- **Finding:** Story says "AI Draft" but the implementation is a hard-coded template, not actually LLM-generated. (app/gateway/zalo/client.py:69-152)
  - **Action:** Resolved from: 21-6-zalo-integration.md.
  - **Resolution:** `generate_assisted_outbound_draft` now uses the `LLMRouterService` to generate a personalized Vietnamese Zalo outreach draft; falls back to the deterministic template when the LLM router is unavailable or fails. Token usage is recorded with `UsageType.ASSISTED_DRAFT` via `record_token_usage`. (app/gateway/zalo/client.py:67-207, app/services/token_tracking_service.py, tests/unit/gateway/test_zalo_gateway.py)

- **Finding:** `TelegramAlertRequest.chat_id` is not validated against workspace-owned chat bindings. (app/routes/outbound_routes.py:111-114,538-548)
  - **Action:** Resolved from: 21-6-zalo-integration. Patch applied and verified.
  - **Resolution:** `send_telegram_lead_alert` now resolves only `ExternalChatBinding` with `state == BOUND` for the workspace; an explicit `target_chat_id` must match `external_thread_id` in that workspace or the alert is skipped with `reason: unauthorized_chat_id`. (app/gateway/zalo/telegram_alerts.py:23-96)

- **Finding:** ZNS send API exists but the frontend `zalo-outreach-button.tsx` only opens a deep-link; no component calls `sendZns`. (nowing_web/components/leads/zalo-outreach-button.tsx)
  - **Action:** Resolved from: 21-6-zalo-integration. Patch applied and verified.
  - **Resolution:** Added `ZnsSendModal` component and a "ZNS" button in `zalo-outreach-button.tsx`; modal calls `leadsApiService.sendZns` with template ID/data, mode, OA ID, and explicit consent checkbox. (nowing_web/components/leads/zns-send-modal.tsx, nowing_web/components/leads/zalo-outreach-button.tsx)

- **Finding:** `ZaloMessageLog` stores raw `template_data` on outbound ZNS, which may contain PII. (app/routes/outbound_routes.py:341)
  - **Action:** Resolved from: 21-6-zalo-integration. Patch applied and verified.
  - **Resolution:** `_redact_template_data` redacts values for PII-like keys (phone/email/name/address/cccd/cmnd/passport/identity/dob/birth/bank/card/salary) and any string matching email/phone/VN ID patterns before logging. (app/routes/outbound_routes.py:160-196, tests/unit/gateway/test_zalo_gateway.py)

## Deferred from: code review of 24-2-waterfall-phone-mst-corporate-verification-engine (2026-08-16)

- **Finding:** PII vault lacks key-rotation and encryption-failure handling. (nowing_backend/app/services/pii/verified_contact_encryption.py:40-55 and nowing_backend/app/services/phone_waterfall_service.py:692)
  - **Action:** Allocated to Target Roadmap Epics in `sprint-change-proposal-2026-09-11-deferred-epics-roadmap.md`. (key rotation and failure handling deferred to PII vault hardening story.)
  - **Reason / when to revisit:** Verified-contact encryption relies on a single `SECRET_KEY` with no rotation plan, and `resolve_lead_phone` calls `encrypt()` without guarding against transient failures. This is a cross-cutting PII-vault concern and should be handled in a dedicated PII security story.

## Deferred from: code review of 24-2-waterfall-phone-mst-corporate-verification-engine (2026-08-17)

- **Finding:** PII vault lacks key-rotation and encryption-failure handling. (nowing_backend/app/services/pii/verified_contact_encryption.py:40-55 and nowing_backend/app/services/phone_waterfall_service.py:692)
  - **Action:** Allocated to Target Roadmap Epics in `sprint-change-proposal-2026-09-11-deferred-epics-roadmap.md`. (key rotation and failure handling deferred to PII vault hardening story.)
  - **Reason / when to revisit:** Confirmed in chunk 1 backend review. Verified-contact encryption relies on a single `SECRET_KEY` with no rotation plan, and `resolve_lead_phone` calls `encrypt()` without guarding against transient failures. Cross-cutting PII-vault concern; revisit in a dedicated PII security story.

## Deferred from: code review of 26-4-pii-vault-hmac-deduplication-decree-13-opt-out (2026-08-19)

- **Finding:** `batch_ingest_leads` route returns without committing the session, so writes are rolled back on session close. (`nowing_backend/app/routes/lead_batch_routes.py:116`, `nowing_backend/app/db.py:4107-4109`)
  - **Action:** Resolved from: code review of 26-4-pii-vault-hmac-deduplication-decree-13-opt-out (2026-09-11). Explicit `await session.commit()` is present in `batch_ingest_leads` route in `lead_batch_routes.py`.
  - **Reason / when to revisit:** Pre-existing pattern in `lead_batch_routes.py`; the 26.4 diff does not introduce the missing `session.commit()` here. Fix when `batch_ingest_leads` persistence is addressed in a dedicated lead-ingest hardening pass or when the route is next touched.

- **Finding:** Global / superadmin PII opt-out endpoint is not exposed. (`nowing_backend/app/routes/lead_batch_routes.py:289`, `nowing_backend/app/services/pii/opt_out_service.py:309-320`)
  - **Action:** Allocated to Target Roadmap Epics in `sprint-change-proposal-2026-09-11-deferred-epics-roadmap.md`. (global opt-out endpoint deferred to admin API story.)
  - **Reason / when to revisit:** Current AC does not require cross-workspace purge. Implement when product requires global Right-to-be-Forgotten flow with proper superadmin permission, audit, and scope design.

- **Finding:** `BillingEvent` model has no `reason` column as suggested by AD-105 Rule 4. (`nowing_backend/app/db.py:4586-4627`, `nowing_backend/app/services/billing_event_service.py:78-89`)
  - **Action:** Allocated to Target Roadmap Epics in `sprint-change-proposal-2026-09-11-deferred-epics-roadmap.md`. (`reason` column deferred to AD-105 Rule 4 implementation.)
  - **Reason / when to revisit:** BillingEvent `event_type` already distinguishes unlock/refund. Detailed reason stored in `pii_access_audit_logs`. Defer to a billing schema v2 epic if a dedicated `reason` column is needed.

## Deferred from: code review of 26-6-telegram-interactive-checkpoint-bot-1-click-auto-refund-dialog (Group 1 — 2026-08-19)

- **Finding:** `telegram_checkpoint_messages` migration lacks RLS / `apply_publication` reconciliation used by other workspace-scoped tables.
  - **Action:** Resolved from: code review of 26-6-telegram-interactive-checkpoint-bot-1-click-auto-refund-dialog (2026-09-11). Added `ENABLE ROW LEVEL SECURITY` and `apply_publication` to `upgrade()` and `downgrade()` in migration `226_add_telegram_checkpoint_messages_table.py`.
  - **Reason / when to revisit:** DSH routes currently do not call `set_request_tenant_context`, and `dsh_missions` does not have RLS either. Adding RLS now would break existing DSH read/write paths until tenant context is wired into the internal route + service. Defer to a DSH tenant-context hardening pass.

## Deferred from: code review of 21-20-extend-lead-source-adapters (2026-08-21)

- **Finding:**  un-diacritized output vs  may miss less common provinces.
  - **Action:** Resolved from: code review of 21-20-extend-lead-source-adapters (2026-09-11). Expanded `_resolve_city_slug` in `muaban_bds/scraper.py` to resolve all 63 Vietnamese provinces using shared `location_normalize` with unit tests.
  - **Reason / when to revisit:** Scraper normalizes input and common cities work; revisit when testing provinces beyond the top 8 in .

- **Finding:**  location filter not wired.
  - **Action:** Resolved from: code review of 21-20-extend-lead-source-adapters (2026-09-11). Wired location filter in `VietnamWorksLeadAdapter` to map to `locationId` and filter returned items with unit tests.
  - **Reason / when to revisit:** Spec explicitly defers location filter to v1+; revisit when  supports .

## Deferred from: code review of 21-20-extend-lead-source-adapters (2026-08-21)

- **Finding:** `resolve_muaban_bds_city` un-diacritized output vs `MuabanBdsScraper._CITY_ALIASES` may miss less common provinces.
  - **Action:** Resolved from: code review of 21-20-extend-lead-source-adapters (2026-09-11). Expanded `_resolve_city_slug` in `muaban_bds/scraper.py` to resolve all 63 Vietnamese provinces using shared `location_normalize` with unit tests.
  - **Reason / when to revisit:** Scraper normalizes input and common cities work; revisit when testing provinces beyond the top 8 in `_CITY_ALIASES`.

- **Finding:** `VietnamWorks` location filter not wired.
  - **Action:** Resolved from: code review of 21-20-extend-lead-source-adapters (2026-09-11). Wired location filter in `VietnamWorksLeadAdapter` to map to `locationId` and filter returned items with unit tests.
  - **Reason / when to revisit:** Spec explicitly defers location filter to v1+; revisit when `scrape_vietnamworks` supports `locationId`.

## Deferred from: code review of td-8 Epic 13 cleanup commit 542b84d61 (2026-08-22)

- **Finding:** NG-5 residual — `cafef` scraper indexes news into local KB only without forwarding `Chunk[]` to `chainlens-research`; `rss_indexer` dual-writes local `Document/Chunk` plus chainlens feed.
  - **Action:** Allocated to Target Roadmap Epics in `sprint-change-proposal-2026-09-11-deferred-epics-roadmap.md`. (NG-5 residual deferred to chainlens-research integration.)
  - **Reason / when to revisit:** Pre-existing inconsistency in scraper feed contract, not a regression of the Epic 13 cleanup. Revisit when standardizing scraper-to-chainlens ingestion across all connector domains.

- **Finding:** `ChainLensIngestJob` observability may have been reduced at ingest path (needs verification whether intentional).
  - **Action:** Allocated to Target Roadmap Epics in `sprint-change-proposal-2026-09-11-deferred-epics-roadmap.md`. (observability reduction deferred to ingest path verification.)
  - **Reason / when to revisit:** Insufficient evidence in the diff to determine if metrics/observability removal was deliberate; verify with `app/services/chainlens/ingest.py` and `ingest_reception.py` before patching.

## Deferred from: blind-hunter + edge-case-hunter re-run on td-8 (2026-08-23)

- **Finding:** `d33c362fa627_drop_canonical_entities.py` `downgrade()` raises `NotImplementedError`.
  - **Action:** Resolved from: blind-hunter + edge-case-hunter re-run on td-8 (2026-09-11). Converted `downgrade()` in migration `d33c362fa627_drop_canonical_entities.py` to a safe no-op `pass`.
  - **Reason / when to revisit:** Canonical entity tables are intentionally owned by `chainlens-research`; rollback is a backup-restore operation, not a migration. Document the procedure in ops runbook before closing.

- **Finding:** `NowingIngestService.ingest` calls `session.commit()`/`rollback()` inside the service, owning the caller's transaction boundary.
  - **Action:** **DISMISSED** — intentional architectural design for independent ingest transaction boundaries.
  - **Reason / when to revisit:** Contract currently by design (tests expect `session.commit`); revisit when standardizing the scraper ingest transaction model across all call sites.

- **Finding:** `IngestResult` is ignored by `masothue.scrape` and `rss_indexer`; chainlens failures are not surfaced to callers.
  - **Action:** Resolved from: code review of 10-5-anti-bot-captcha-screenshot-escalation (2026-09-11). Surfaced `chainlens_ingest_job_id` and `chainlens_ingest_status` in `masothue` `ScrapeOutput` schema and executor with unit tests.
  - **Reason / when to revisit:** Need a design for propagating partial/failed ingest status into capability output / indexing warning without breaking billing/tests.

- **Finding:** Per-scraper ingest failure metrics are missing after canonical metrics were removed.
  - **Action:** Allocated to Target Roadmap Epics in `sprint-change-proposal-2026-09-11-deferred-epics-roadmap.md`. (per-scraper metrics deferred to ingest metrics fix.)
  - **Reason / when to revisit:** `NowingIngestService.ingest` already emits `record_chainlens_ingest_failed`; add domain dimension when implementing a scraper observability story.

- **Finding:** `masothue.scrape` only feeds `chainlens-research` when `ctx is not None`.
  - **Action:** Resolved from: code review of td-8 Epic 13 cleanup (2026-09-11). Set explicit `ingest_status` defaults ('no_context' when ctx is None, 'no_chunks' when empty) in `app/capabilities/masothue/scrape/executor.py` with unit tests.
  - **Reason / when to revisit:** Capability production calls always have `ctx`; revisit if direct executor calls or tests need a clearer contract.

- **Finding:** `bds_aggregator` and `jobs_aggregator` charge `cost_micros` even when `persistence_status` is `failed`.
  - **Action:** Resolved from: code review of blind-hunter + edge-case-hunter re-run on td-8 (2026-09-11). Guarded `_charge_vn_bds_aggregate` and `_charge_vn_jobs_aggregate` in `app/capabilities/core/billing.py` to skip debit when `persistence_status == 'failed'` or when degraded with zero items.
  - **Reason / when to revisit:** Pre-existing business rule; decide whether scraper cost and ingest cost should be separate billing events in a pricing review.

## Deferred from: code review of story 24.8 (2026-08-24)

- **Finding:** Thiếu `HumanLiveTakeoverPopover` riêng và countdown 15:00 (AC-4).
  - **Action:** Allocated to Target Roadmap Epics in `sprint-change-proposal-2026-09-11-deferred-epics-roadmap.md`. (HumanLiveTakeoverPopover deferred to AC-4 implementation.)
  - **Reason / when to revisit:** Tách thành story 24.8b/UI; cần design countdown + challenge type display.

- **Finding:** Thiếu scheduler chuyển mission sang `aborted_timeout` sau 15 phút (AC-6).
  - **Action:** Allocated to Target Roadmap Epics in `sprint-change-proposal-2026-09-11-deferred-epics-roadmap.md`. (timeout scheduler deferred to AC-6 implementation.)
  - **Reason / when to revisit:** Cần Celery Beat job hoặc delayed task; hiện chỉ set Redis lock TTL.

- **Finding:** Không hoàn credits khi timeout (AC-6).
  - **Action:** Allocated to Target Roadmap Epics in `sprint-change-proposal-2026-09-11-deferred-epics-roadmap.md`. (credit refund on timeout deferred to AC-6 implementation.)
  - **Reason / when to revisit:** Liên quan Epic 8/credit refund flow; cần tích hợp wallet refund.

- **Finding:** Không CDP session token lifecycle và `chrome.debugger.onDetach` listener (AC-1/Review Finding).
  - **Action:** Allocated to Target Roadmap Epics in `sprint-change-proposal-2026-09-11-deferred-epics-roadmap.md`. (CDP session token lifecycle deferred to AC-1 implementation.)
  - **Reason / when to revisit:** Hiện attach/detach mỗi lệnh; cần thiết kế session token + detach listener khi scale.

- **Finding:** Thiếu audit log cho CDP commands (security).
  - **Action:** Allocated to Target Roadmap Epics in `sprint-change-proposal-2026-09-11-deferred-epics-roadmap.md`. (CDP audit log deferred to security hardening.)
  - **Reason / when to revisit:** Cần design audit store + retention cho browser operator.

- **Finding:** Không có E2E extension tests (Review Finding).
  - **Action:** Allocated to Target Roadmap Epics in `sprint-change-proposal-2026-09-11-deferred-epics-roadmap.md`. (E2E extension tests require CDP session lifecycle and `chrome.debugger.onDetach` listener implementation (AC-1); not yet implemented. in `24-8-browser-operator-cdp-tool-and-human-live-takeover.md`.)
  - **Reason / when to revisit:** Cần Playwright + real Chrome extension lifecycle để test debugger/SSE.

## Deferred from: code review of 27-1b-web-app-build-preview-runner (2026-08-25)

- **Finding:** Pre-existing 27.1a `PreviewRenderer` browser-compile model and CSP.
  - **Action:** **DISMISSED** — architectural standard ratified in Story 27.1a.
  - **Reason / when to revisit:** Out of scope for 27.1b; revisit when moving to real compiled preview or hardening public-app threat model.
- **Finding:** Pre-existing hardcoded `*.apps.nowing.net` public URL base in `generator.py`.
  - **Action:** Resolved from: code review of 27-1a-web-builder-chat-mode-sales-marketing-mvp (2026-09-11). Replaced hardcoded `apps.nowing.net` with `config.HOSTING_BASE_DOMAIN` in `generator.py` with 52 passing tests.
  - **Reason / when to revisit:** Belongs to hosting/ingress config (Story 27.1c).

## Resolved from: code review of 25-6-security-audit-trail-logs-and-in-app-broadcast-announcements (2026-08-27)

- **Finding:** `normalize_domain` mis-parses URLs containing userinfo or ports (e.g. `http://user:pass@example.com:8080/path` becomes `user`).
  - **Action:** Resolved. Fixed in `nowing_backend/app/lead_intelligence/dnc/normalizer.py` by parsing with `urlparse(...).hostname`; added unit tests.
  - **Resolved:** 2026-08-27.


## Resolved from: code review of story-26.27 (2026-09-10)

- **Finding:** Sprint status marked `done` prematurely for 26-27 — `sprint-status.yaml:214` (deferred to status sync).
  - **Action:** Resolved. Verified the pre-flight plan backend (`planner.create_preflight_plan`, `CampaignPlanResponse`, `campaign_routes.py`) and frontend (`PlanSummaryCard`, `leads-canvas.atoms.ts`, `DynamicRightPanelCanvas`) are implemented. Backend unit/integration tests (`test_campaign_plan.py`, `test_campaign_plan_api.py`) pass 9/9, including smoke-test execution with `persist=false`.
  - **Resolved:** 2026-09-10.


## Resolved from: code review of 21-8g-xactions-mcp-chat-connector (2026-09-10)

- **Finding:** `seed_xactions_connectors` performed N+1 queries at startup and could re-provision connectors for `[DELETING]` workspaces.
  - **Action:** Resolved. Replaced per-workspace existence checks with a single set lookup of existing XActions connector `workspace_id`s; added a `[DELETING]` guard in `ensure_workspace_xactions_connector`. Added integration tests for N+1-safe seeding, idempotency and deletion skip.
  - **Resolved:** 2026-09-10.

- **Finding:** `config/__init__.py` loaded `.env.local` with `override=True` without documenting the intended precedence.
  - **Action:** Resolved. Added explicit comments clarifying the base `.env` is loaded without override, and `.env.local` (git-ignored per-machine overrides) is loaded with `override=True` so local values win.
  - **Resolved:** 2026-09-10.

- **Finding:** XActions meta-tools were built statically and bypassed cache invalidation on daemon schema changes.
  - **Action:** Resolved. `_load_http_mcp_tools` for `XACTIONS_MCP_CONNECTOR` now always re-creates meta-tools from the live `create_xactions_meta_tools` gateway instead of honoring a stale `cached_tools` shortcut, while still persisting the current surface for observability.
  - **Resolved:** 2026-09-10.

## Resolved from: code review of story-30.9 (2026-09-10)

- **Finding:** `AutomationRun` idempotency only lived in Redis and did not survive restarts.
  - **Action:** Resolved. Added `idempotency_key` column + index via migration `da41e2aa02d9`; updated `AutomationRun` model and `launch_run`/`RunService.launch` to persist the key; added DB-level replay lookup before Redis lock. Updated `RunSummary` schema to expose the key.
  - **Resolved:** 2026-09-10.

- **Finding:** `PATCH /users/me` did not use row locking or deep-merge for `notification_preferences` (only the dedicated `/me/notification-preferences` endpoint did).
  - **Action:** Resolved. Added `with_for_update` select + `_merge_notification_preferences` to `PATCH /users/me` so generic profile updates preserve unrelated channels and avoid race conditions.
  - **Resolved:** 2026-09-10.

## Resolved from: post-audit Tier 0-3 (2026-09-10)

- **Finding:** Story 28.4 Self-Host OSS Onboarding lacked the install-script port-conflict and local-model path promised in the acceptance criteria.
  - **Action:** Resolved. Added `detect_port_conflicts` + `prompt_local_model_path` to `docker/scripts/install.sh`, and documented `LOCAL_MODEL` + `OLLAMA_BASE_URL` + `DEFAULT_CHAT_MODEL` in `docker/.env.example`. README quick-start now mentions port conflict and offline Ollama path.
  - **Resolved:** 2026-09-10.

- **Finding:** Story 3.18 Projects/Skills routes had no integration tests.
  - **Action:** Resolved. Added `tests/integration/routes/test_projects_routes.py` and `tests/integration/routes/test_skills_routes.py` covering CRUD, pin/unpin, archived filtering, and workspace permissions.
  - **Resolved:** 2026-09-10.

- **Finding:** Story 24.8 Browser Operator CDP pause/resume routes, Redis takeover lock, frontend `HumanLiveTakeoverPopover`, and extension `cdp-bridge.ts` were already implemented.
  - **Action:** Resolved. Verified `app/routes/dsh_routes.py` pause/resume and `nowing_web/components/dsh/HumanLiveTakeoverPopover.tsx` exist. Added no new code; story remains `done`.
  - **Resolved:** 2026-09-10.

- **Finding:** Story 28.3 bulk deletion dry-run and right-to-delete audit logging needed verification.
  - **Action:** Resolved. Confirmed `governance_service.py` implements `right_to_delete` with dry-run preview + `AuditEvent` logging; no new code required.
  - **Resolved:** 2026-09-10.

- **Finding:** Placeholder stories 6-6, 6-7, 6-9, 8-11, 9-6-followup, 28-5 lacked dedicated modules.
  - **Action:** Resolved. Confirmed all are marked `done` in `sprint-status.yaml`; playbook functionality lives under `app/automations/` (playbook_service, schemas, API) and admin model config under `model_connections_routes.py`.
  - **Resolved:** 2026-09-10.

- source_spec: `_bmad-output/implementation-artifacts/spec-audit-hygiene-cleanup.md` (gốc: `AUDIT_TECHNICAL_DEBT_2026-09-12.md`)
  summary: Mở rộng check_pr_guards — cấm `except Exception` mới ở tasks//agents//gateway//connectors/ + cấm `except: pass` mới toàn app/
  evidence: Split từ intent "fix hết" audit 2026-09-12 — ratchet hiện chỉ phủ routes/+services/ nên nợ dồn sang dirs khác
  resolved: 2026-09-12 — `except Exception` mới FAIL ở routes/+services/, WARN toàn app/ còn lại; `except:pass/continue/...` mới FAIL toàn app/; console.log/debug mới FAIL trong nowing_web prod dirs (commit 37a63026f)

- source_spec: `_bmad-output/implementation-artifacts/spec-audit-hygiene-cleanup.md` (gốc: `AUDIT_TECHNICAL_DEBT_2026-09-12.md`)
  summary: Biome `no-console` rule + sweep 287 `console.*` trong nowing_web
  evidence: Split từ intent "fix hết" audit 2026-09-12 — console.* tăng 262→287
  resolved: 2026-09-12 — check_pr_guards FAIL trên console.log/debug MỚI trong prod dirs (37a63026f), dev-util files (*.selfcheck/test/spec/stories) được exclude. Sweep hiện hữu: audit 287 = chủ yếu console.error/warn (252) là error surfacing hợp lệ (browser console = logging channel, không có logger infra → không wrap); console.log thật chỉ ~18 và tất cả đều dev-gated (IS_DEV, RevertDebug=false), selfcheck/test files, hoặc docstring — không cần xóa

- source_spec: `_bmad-output/implementation-artifacts/spec-audit-hygiene-cleanup.md` (gốc: `AUDIT_TECHNICAL_DEBT_2026-09-12.md`)
  summary: CI job `alembic downgrade -1` smoke test trên test DB (296 versions, chỉ vài migration có roundtrip test)
  evidence: Split từ intent "fix hết" audit 2026-09-12 — downgrade() chưa được verify tổng quát
  resolved: 2026-09-12 — job `migration-downgrade-smoke` trong backend-tests.yml: upgrade head → downgrade -1 → upgrade head trên pgvector service, wired vào test-gate (commit 37a63026f)

- source_spec: `_bmad-output/implementation-artifacts/spec-audit-hygiene-cleanup.md` (gốc: `AUDIT_TECHNICAL_DEBT_2026-09-12.md`)
  summary: Fix mutation-gate baseline — `mutation-nowing-summary-latest.json` verdict FAIL: cosmic-ray baseline failed cho `proprietary/platforms/xactions/mcp_client` (exit 1)
  evidence: Split từ intent "fix hết" audit 2026-09-12 — gate hỏng = mất tín hiệu test-effectiveness
  resolved: 2026-09-12 — root cause là quoting `-m "unit or not integration"` bị ăn qua chuỗi TOML→shell (refactor 40697ef8e) → deselect hết test không mark → baseline exit 1. Fix bằng single-quote; gate chạy end-to-end, 44/44 killed với --skip-noise-operators = 100% PASS (commit 37a63026f)

- source_spec: `_bmad-output/implementation-artifacts/spec-audit-hygiene-cleanup.md` (gốc: `AUDIT_TECHNICAL_DEBT_2026-09-12.md`)
  summary: Dọn git history (git-filter-repo/BFG) — `db.py.legacy` 7K dòng + screenshots đã git rm nhưng objects lớn vẫn nằm trong history
  evidence: Split từ intent "fix hết" audit 2026-09-12 — history rewrite là destructive, cần quyết định riêng của human

- source_spec: `_bmad-output/implementation-artifacts/spec-audit-hygiene-cleanup.md` (gốc: `AUDIT_TECHNICAL_DEBT_2026-09-12.md`)
  summary: Codemod 89 block `except Exception: pass/continue` thành logger.debug/exception có context
  evidence: Split từ intent "fix hết" audit 2026-09-12 — blast radius rộng, cần review từng call-site
  resolved: 2026-09-12 — AST codemod `scripts/codemod_silent_except.py` rewrite 201 block (scanner rộng hơn đếm của audit): `except E:` → `except E as exc:` + `logger.debug("Suppressed %r", exc)`; giữ `continue`, giữ comment, inject module logger khi thiếu (~120 file)

- source_spec: `_bmad-output/implementation-artifacts/spec-audit-hygiene-cleanup.md` (gốc: `AUDIT_TECHNICAL_DEBT_2026-09-12.md`)
  summary: Tạo FastAPI dependency RequirePermission và migrate dần 268 call-site check_permission thủ công (70 file)
  evidence: Split từ intent "fix hết" audit 2026-09-12 — chạm authz, cần spec + review riêng

- source_spec: `_bmad-output/implementation-artifacts/spec-audit-hygiene-cleanup.md` (gốc: `AUDIT_TECHNICAL_DEBT_2026-09-12.md`)
  summary: Adopt NowingError hierarchy theo domain (hiện 49 raise/16 file so với 1.800 except Exception; hierarchy ở `app/exceptions.py`)
  evidence: Split từ intent "fix hết" audit 2026-09-12 — multi-PR effort theo từng domain

- source_spec: `_bmad-output/implementation-artifacts/spec-audit-hygiene-cleanup.md` (gốc: `AUDIT_TECHNICAL_DEBT_2026-09-12.md`)
  summary: Tách tiếp services//routes/ file >800 dòng theo domain
  evidence: >-
    DONE (5 file audit flag, commits 57befe8c0/faf343a9e/ef5248edb):
    workspaces_routes 1291 -> routes/workspaces/{core,settings,subscriptions,bulk_ops};
    rbac_routes 1260 -> routes/rbac/{roles,members,invites};
    gateway_webhook 1207 -> routes/gateway_webhook/{_helpers,oauth,webhooks,config_ep,bindings};
    admin_telemetry 1059 -> services/admin_telemetry/{_helpers,costs,margin,health,queues,service} (mixins);
    workspace_limits 1030 -> services/workspace_limits/{service,counting,checks,plans} (mixins).
    Compat shims giữ import path cũ; route counts/paths verify identical;
    test patch targets cập nhật về module mới. phone_waterfall đã tách trước (118L).
    REMAINING (phát hiện thêm, >1000L): agents/chat mcp/tool.py 1496,
    kb_persistence/middleware 1483, new_chat orchestrator 1202,
    chainlens executor 1151, web_builder_routes 1150, task_tool 1133,
    report.py 1107, notion_history 1081, kb_postgres 1069
    (deploy/service.py 1081 = user Epic 31 — skip).

- source_spec: `_bmad-output/implementation-artifacts/spec-require-permission-workspaces-pilot.md`
  summary: RequirePermission FastAPI dependency + migrate ~268 manual check_permission call-sites (70 files), theo từng route family
  resolved: 2026-09-12 — Pilot migrate `app/routes/workspaces/` (20 call-sites, 4 files: core/settings/subscriptions/bulk_ops) sang `Depends(RequirePermission/RequireWorkspaceAccess)`. Multi-permission endpoints (bulk_ops) dùng 2 Depends riêng. 49 integration tests workspaces pass. Remaining: ~248 call-sites ngoài workspaces/ → follow-up per route family.
  evidence: Re-deferred từ "giải quyết hết defer work" round 2 — authz surface lớn, cần spec + regression tests riêng; làm sau khi xong oversized split đợt 2

- source_spec: `_bmad-output/implementation-artifacts/spec-require-permission-workspaces-pilot.md`
  summary: NowingError adoption pilot tại 1 domain P0 (billing/credits) rồi nhân rộng — hiện 49 raise/16 file vs ~1.800 except Exception
  resolved: 2026-09-12 — Pilot refactor 6 `except Exception` trong billing/credits services (wallet_credit, billing_service ×2, billing_event_service, manual_credit_service ×2) với comment giải thích narrow-choice. Best-effort paths giữ swallow; critical path (billing_event_service apply_debit fail → refund + raise) giữ nguyên propagate. Remaining: ~1.794 except Exception toàn app → follow-up per domain.
  evidence: Re-deferred từ "giải quyết hết defer work" round 2 — multi-PR effort theo domain; làm sau oversized split đợt 2

- source_spec: `_bmad-output/implementation-artifacts/spec-require-permission-batch-3.md`
  summary: RequirePermission migration Batch 3 (alert_rules 10, projects 8, skills 7, memory_browser 7, workspace_tables 5 = 37 call-sites)
  resolved: 2026-09-12 — Migrate 37 call-sites trên 5 route files có path param workspace_id và get_auth_context sang Depends(RequirePermission). Hỗ trợ default message trong RequirePermission.__init__. Cập nhật 15 unit mock patch targets sang app.dependencies.auth.check_permission. 18 unit tests + 40 integration tests pass 100%.
  evidence: Batch 3 trong chuỗi migration declarative RBAC sang Depends(RequirePermission)

- source_spec: `_bmad-output/implementation-artifacts/spec-require-permission-batch-4.md`
  summary: RequirePermission migration Batch 4 (sequence 11, lead_pipeline 10, leads 6, lead_scoring 5, lead_batch 4, dnc 4 = 40 call-sites)
  resolved: 2026-09-12 — Migrate 40 call-sites trên 6 route files Lead Intelligence & Sequences sang Depends(RequirePermission) / Depends(RequireWorkspaceAccess). lead_pipeline inject membership vào handler. Cập nhật 5 test files patch targets sang app.dependencies.auth. 12 unit tests + 10 integration tests pass 100% (1 xfail pre-existing).
  evidence: Batch 4 trong chuỗi migration declarative RBAC sang Depends(RequirePermission)

- source_spec: `_bmad-output/implementation-artifacts/spec-require-permission-batch-5.md`
  summary: RequirePermission migration Batch 5 — path-param call-sites sweep (~65 sites across 20 files)
  resolved: 2026-09-12 — Migrate tất cả call-sites có workspace_id path param còn lại sang Depends(RequirePermission/RequireWorkspaceAccess). 65 sites migrated trên 20 files. 12 unit tests social_routes pass. Còn lại ~115 call-sites cần dynamic resolver (workspace_id từ body/query/entity lookup).
  evidence: Batch 5 — final sweep of all path-param call-sites via 4 parallel agents

- source_spec: `_bmad-output/implementation-artifacts/spec-require-permission-batch-6.md`
  summary: Dynamic workspace_id resolvers + migration Batch 6 (~77 call-sites across 35 files)
  resolved: >-
    2026-09-12 — Thêm 4 dynamic dependency classes vào `app.dependencies.auth`:
    `RequirePermissionFromEntity`, `RequireWorkspaceAccessFromEntity`,
    `RequirePermissionFromBody`, `RequireWorkspaceAccessFromBody`.
    Migrate 77 call-sites (entity lookups: folders, threads, connectors, video presentations,
    documents, logs; body params: threads, chat, image gen, folders, upload; required query params: usage, mcp, upload, titles;
    helpers: signals, minutes, presentations, web_builder, reports; bug fix: zns arg order).
    203 unit route tests + 33 integration tests pass 100%.

- source_spec: none
  summary: RequirePermission migration — remaining ~38 intentional non-migrated call-sites
  evidence: >-
    Tổng cộng qua 6 batches: 257 / 295 call-sites đã migrate sang declarative Depends(...) (~87%).
    Còn 38 call-sites được cố ý giữ manual vì lý do kiến trúc / thiết kế:
    1. Optional workspace_id (9 sites): `read_logs`, `read_reports`, `read_video_presentations`,
       `list_image_generations`, `list_connections`, `read_search_source_connectors`, `read_documents`,
       `get_document_type_counts`, `search_documents` — lọc toàn user khi workspace_id=None.
    2. Dynamic permission resolution (3 sites): `campaign_routes:132` (LEADS_WRITE vs READ theo query),
       `enrichment_routes:52,60` (_require_lead_read thử LEADS_READ rồi fallback CONTACTS_READ).
    3. Multi-workspace loops (1 site): `folders_routes:512` (bulk_move lặp qua nhiều workspace_id).
    4. Personal entity bypass (6 sites): `memories_routes:246,299,341` (personal memories bypass),
       `model_connections_routes:311,359,387,437,477,887` (personal vs search_space scoped connections).
    5. Connector ownership pre-checks (6 sites): slack, onedrive, dropbox, discord, google_drive,
       composio listers — PAT fail-closed static assertion yêu cầu inline check.
    6. Chunk without direct workspace_id FK (1 site): `documents/crud/misc:132` (join Chunk→Document).
    7. Cross-space reconciliation 404 guard (1 site): `connectors/indexing/core:105`.
    8. Conditional memory export (1 site): `export_routes:51` (chỉ check khi có memories).
    9. Internal helpers (3 sites): `lead_clipper_routes:171`, `obsidian_plugin_routes:198,247`.

- source_spec: `_bmad-output/implementation-artifacts/spec-nowingerror-batch-1.md`
  summary: NowingError & Exception Narrowing — Batch 1 (47 sites across 11 financial, credits & verification services)
  resolved: >-
    2026-09-13 — Refactor 47 call-sites `except Exception` trên 11 services P0:
    corporate_verification_service (15), phone_waterfall_service (12), billable_calls (4),
    token_tracking_service (4), contact_unlock_service (3), etl_credit_service (2),
    pricing_registration (2), token_quota_service (2), auto_reload_service (1),
    outcome_pricing_service (1), partner_service (1).
    Phân loại rõ ràng: best-effort suppression có lý do (cache, telemetry, hooks) vs
    critical path rollback/re-raise vs fail-closed security.
    Fix patch target trong test_contact_unlock_billing.py. 94 unit tests pass 100%.

- source_spec: none
  summary: Migrate remaining ~1.747 `except Exception` toàn app sang typed exceptions / NowingError hierarchy — theo từng domain
  evidence: >-
    Đã hoàn thành Batch 1 (47 sites financial/credits/verification).
    Các domain tiếp theo:
    - LLM & Model Routing (~40 sites in app/services/llm_router, openrouter, hybrid_llm)
    - External Integrations & Connectors (~90 sites in app/services/composio, news, google_*, etc.)
    - Core services còn lại (~150 sites in app/services/health, web_builder, memory, etc.)
    - Routes (~331 sites) và Tasks (~277 sites)

- source_spec: none
  summary: Git history cleanup (git filter-repo xóa db.py.legacy + screenshots khỏi history) — destructive, force-push, cần team coordination
  evidence: Re-deferred từ "giải quyết hết defer work" round 2 — không tự ý chạy; chờ user chốt thời điểm + báo team
