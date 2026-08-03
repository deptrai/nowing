---
baseline_commit: 25ba542c2a3dec95b0a4020da8c129242ba748e2
baseline_branch: develop
story_key: 8-13-posthog-analytics
status: ready-for-dev
---

# Story 8.13: PostHog Product Analytics

**Status:** ready-for-dev
**Epic:** 8 — Platform Operations
**Priority:** MEDIUM
**Requirements:** NFR-3
**Architecture:** AD-9
**Dependencies:** `nowing_web` build system; existing `@posthog/react` / `posthog-js` dependencies.

## Story

As a product team,
I want PostHog analytics integrated into the web app,
So that I can understand user flows, feature adoption, and retention.

## Context

### Upstream reference

SurfSense PR #1622 (`MODSetter/SurfSense#1622`, commit `dbedf0cfa53e604e4b9bc3f26f29691b691ddeb4`) already implemented the pattern we need to harden:

- Added `NEXT_PUBLIC_POSTHOG_KEY` / `NEXT_PUBLIC_POSTHOG_HOST` to `surfsense_web/.env.example`.
- Added `posthog-js` and `@posthog/react` dependencies.
- Initialized `posthog-js` in `surfsense_web/instrumentation-client.ts`:
  - `capture_pageview: "history_change"` and `capture_pageleave: true`.
  - `api_host` pointing at the custom PostHog asset proxy (`https://assets.surfsense.com`).
  - `before_send` injects `platform` (`web`/`desktop`), ref-code `first_ref_code` / `latest_ref_code`, and `$set` person properties.
  - Lazy `requestIdleCallback` init so analytics never blocks first paint.
- Wrapped the app in `PostHogProvider` from `app/layout.tsx`.
- `PostHogIdentify.tsx` identifies users with `user.id`, `email`, `name`, `is_superuser`, `is_verified`, and resets on public routes.
- `PostHogReferral.tsx` captures `?ref=` landing attribution.
- `lib/posthog/events.ts` holds **intent/UX-only** frontend events. Outcome events (`workspace_created`, `auth_login_success`, `document_upload_success`, `connector_connected`, etc.) are removed from the frontend and emitted server-side in `surfsense_backend/app/observability/analytics.py`.
- `lib/posthog/events.ts` explicitly drops `connector_title` from `trackConnectorEvent`; only `connector_type`, `connector_group`, `is_oauth`, `connector_id`, and `workspace_id` are sent.
- `lib/apis/base-api.service.ts` extracted a `captureApiException` helper and restricts PostHog error tracking to **network failures and 5xx server faults**; 4xx client errors are expected behavior and are not captured.
- `app/error.tsx` and `app/global-error.tsx` lazy-load `posthog-js` and call `posthog.captureException`.

The same PR also introduced the authoritative **backend** PostHog module (`surfsense_backend/app/observability/analytics.py`). That server-side product-analytics module is out of scope for this web-only story; the Dev Notes below explain how to keep the server-side observability boundary clean.

### Nowing current state

- `nowing_web/package.json` already depends on `posthog-js` (`^1.336.1`) and `@posthog/react` (`^1.7.0`) and `posthog-node` (`^5.24.4`).
- `nowing_web/app/layout.tsx` already wraps the app in `PostHogProvider` (lines 130–155).
- `nowing_web/instrumentation-client.ts` already initializes `posthog-js` with `capture_pageview: "history_change"`, `capture_pageleave: true`, platform/ref `before_send` enrichment, and `requestIdleCallback`/`setTimeout` boot (lines 36–103).
- `nowing_web/components/providers/PostHogProvider.tsx` re-exports the `PHProvider` and mounts `PostHogIdentify` + `PostHogReferral`.
- `nowing_web/components/providers/PostHogIdentify.tsx` identifies users with `email`, `name`, `is_superuser`, and `is_verified` (lines 40–45). It resets on public routes.
- `nowing_web/lib/posthog/events.ts` exists and has many track helpers, but several still carry workspace content or display labels:
  - `trackWorkspaceCreated` sends the workspace `name` (lines 81–86).
  - `trackWorkspaceInviteAccepted`, `trackWorkspaceUserAdded`, and `trackWorkspaceInviteDeclined` send `workspace_name` and/or `role_name` (lines 435–491).
  - `trackConnectorEvent` sends `connector_title` via `getConnectorTelemetryMeta` (lines 316–334).
  - `trackYouTubeImport` sends the raw `url` (lines 275–280).
  - Dead helpers: `trackWorkspaceViewed`, `trackWorkspaceDeleted`, `trackDocumentDeleted`, `trackDocumentBulkDeleted`, `trackConnectorSynced` have no callers.
- `nowing_web/lib/apis/base-api.service.ts` currently sends **every** non-`AuthenticationError` exception to PostHog (lines 287–306), including 403, 404, and 422 client errors.
- `nowing_web/lib/posthog/server.ts` throws if `NEXT_PUBLIC_POSTHOG_KEY` is unset (lines 5–8), which breaks `instrumentation.ts` when analytics is disabled.
- `nowing_web/instrumentation.ts` uses `lib/posthog/server.ts` to capture server-side request errors (lines 9–37).
- `nowing_web/contracts/types/user.types.ts` includes `is_superuser: boolean` (line 7), and `PostHogIdentify.tsx` already passes it to `identifyUser`.
- Key user actions are already instrumented:
  - Create workspace: `CreateWorkspaceDialog.tsx` line 70.
  - Run scraper: `hooks/use-run-stream.ts` line 113 calls `trackWeeklyUser("api_run", workspaceId)`.
  - Open chat / send message: `lib/chat/stream-engine/engine.ts` lines 387, 459, 779.
  - Invite member: `app/dashboard/[workspace_id]/team/team-content.tsx` line 657 and `app/invite/[invite_code]/page.tsx` lines 100–101.
- `.env.example` already exposes `NEXT_PUBLIC_POSTHOG_KEY` and `NEXT_PUBLIC_POSTHOG_HOST` (lines 34–38).

The remaining work is to make the existing integration **privacy-safe, production-hardened, and aligned with upstream's intent/UX + server-outcome split**.

## Acceptance Criteria

1. **Initialization & pageview**
   - **Given** `NEXT_PUBLIC_POSTHOG_KEY` and `NEXT_PUBLIC_POSTHOG_HOST` are configured at build time, **When** the web app loads, **Then** `posthog-js` initializes, pageviews are captured on history change, page-leave events are captured, and platform/ref person properties are set.
   - **And** initialization is deferred with `requestIdleCallback` / `setTimeout` and never blocks first paint or throws when ad-blockers block the PostHog script.

2. **User identification & superuser anonymization**
   - **Given** a non-superuser is logged in and `currentUserAtom` succeeds, **When** `PostHogIdentify` runs, **Then** `posthog.identify` is called once with the user id, `email`, `name`, `is_superuser`, `is_verified`, and `platform`.
   - **Given** a superuser (`user.is_superuser === true`), **When** `PostHogIdentify` runs, **Then** `email` and `name` are omitted from the identify call, the distinct id is still the stable user id, and a trait `is_internal_user: true` is set instead of PII.
   - **And** when the user navigates to a public route or logs out, `posthog.reset()` is called.

3. **Key action event capture**
   - **Given** a user creates a workspace, runs a scraper, opens/sends a chat, or invites a member, **When** the action happens, **Then** a PostHog event is captured with only low-cardinality identifiers (`workspace_id`, `chat_id`, `connector_type`, `role_name`, etc.) and no workspace content.

4. **Privacy / secrets**
   - **Given** any PostHog event is captured, **When** the payload is inspected, **Then** it does not contain API keys, workspace names, user names, emails, raw URLs, document titles, file names, connector titles, or message content.
   - **And** the `trackConnectorEvent` helper only sends `connector_type`, `connector_group`, `is_oauth`, `connector_id`, `workspace_id`, and optional `source`/`error`.

5. **Error capture scoping**
   - **Given** an API request fails, **When** `base-api.service.ts` catches it, **Then** only 5xx server faults and network failures are sent to PostHog; 4xx client errors (401, 403, 404, 422) and `AuthenticationError` are not captured.
   - **And** `app/error.tsx`, `app/dashboard/error.tsx`, and `app/global-error.tsx` continue to lazy-load `posthog-js` and capture exceptions without breaking the UI when PostHog is disabled.

6. **Opt-out / self-host**
   - **Given** `NEXT_PUBLIC_POSTHOG_KEY` is unset or empty, **When** the app loads or a server-side error occurs, **Then** no PostHog client is created, no analytics requests are made, and `lib/posthog/server.ts` returns a no-op instead of throwing.

## Tasks / Subtasks

### Frontend

- [ ] `nowing_web/lib/posthog/events.ts`
  - [ ] Remove the workspace `name` property from `trackWorkspaceCreated` (keep `workspace_id` only).
  - [ ] Remove `workspace_name` from `trackWorkspaceInviteAccepted`, `trackWorkspaceUserAdded`, and `trackWorkspaceInviteDeclined`; keep `workspace_id` and `role_name` where applicable. Change `trackWorkspaceInviteDeclined` to accept `workspaceId?: number` (or no arg) instead of `workspaceName`.
  - [ ] Remove `connector_title` from `trackConnectorEvent`; keep `connector_type`, `connector_group`, `is_oauth`, plus `connector_id`, `workspace_id`, `source`, and `error`.
  - [ ] Remove the raw `url` from `trackYouTubeImport`; keep `workspace_id` and add `connector_type: "youtube"` (or remove the function if no call sites exist).
  - [ ] Delete dead analytics helpers with no callers: `trackWorkspaceViewed`, `trackWorkspaceDeleted`, `trackDocumentDeleted`, `trackDocumentBulkDeleted`, `trackConnectorSynced`.
  - [ ] Add a file-level comment documenting that all `posthog` calls must be `try/catch` wrapped and that outcome events should migrate to the backend module in a future story.

- [ ] `nowing_web/components/providers/PostHogIdentify.tsx`
  - [ ] Before calling `identifyUser(userId, ...)`, check `user.is_superuser`.
  - [ ] For superusers, call `identifyUser(userId, { is_superuser: true, is_verified: user.is_verified, is_internal_user: true })` (no `email`, no `name`).
  - [ ] For non-superusers, keep the existing `email`, `name`, `is_superuser`, `is_verified` properties.
  - [ ] Ensure the `previousUserIdRef` guard still prevents duplicate `identify` calls.

- [ ] `nowing_web/components/providers/PostHogReferral.tsx`
  - [ ] No logic change required; verify it still captures `?ref=` and persists to `sessionStorage`.

- [ ] `nowing_web/lib/apis/base-api.service.ts`
  - [ ] Extract a `captureApiException(error, url, method)` helper (mirroring upstream) that lazy-imports `posthog-js`.
  - [ ] In the `catch` block, call `captureApiException` only for:
    - `NetworkError` / `TypeError` network failures.
    - `AppError` where `error.status >= 500`.
  - [ ] Do **not** capture `AuthenticationError`, `AuthorizationError`, `NotFoundError`, or 422 validation errors.

- [ ] `nowing_web/lib/posthog/server.ts`
  - [ ] Return a no-op `PostHog`-like object (or `null`) when `NEXT_PUBLIC_POSTHOG_KEY` is missing instead of throwing.
  - [ ] Keep the same lazy singleton behavior when the key is present.

- [ ] `nowing_web/instrumentation.ts`
  - [ ] Handle a no-op / `null` return from `PostHogClient()` and skip capture when PostHog is disabled.

- [ ] `nowing_web/app/layout.tsx`
  - [ ] Confirm `PostHogProvider` wraps the entire app; no code change expected.

- [ ] `nowing_web/instrumentation-client.ts`
  - [ ] Confirm `posthog.init` is guarded by `process.env.NEXT_PUBLIC_POSTHOG_KEY`, uses `capture_pageview: "history_change"` and `capture_pageleave: true`, and the `before_send` hook adds `platform` / `ref_code` / `$set` / `$set_once`.

- [ ] Call-site cleanup
  - [ ] `nowing_web/components/layout/ui/dialogs/CreateWorkspaceDialog.tsx` line 70: change `trackWorkspaceCreated(result.id, values.name)` to `trackWorkspaceCreated(result.id)`.
  - [ ] `nowing_web/app/invite/[invite_code]/page.tsx` lines 100–101: change to `trackWorkspaceInviteAccepted(result.workspace_id, result.role_name)` and `trackWorkspaceUserAdded(result.workspace_id, result.role_name)`. Line 112: change to `trackWorkspaceInviteDeclined()` (or pass `inviteInfo?.workspace_id` if available).
  - [ ] `nowing_web/app/dashboard/[workspace_id]/team/team-content.tsx` lines 232 and 657: verify the updated `trackWorkspaceUsersViewed` and `trackWorkspaceInviteSent` signatures still compile and do not leak `workspace_name`.
  - [ ] `nowing_web/components/assistant-ui/connector-popup/hooks/use-connector-dialog.ts`: verify `trackConnectorEvent` no longer sends `connector_title`; no call-site change needed if the helper is updated.

### Tests / verification

- [ ] Add or update `nowing_web/lib/posthog/events.selfcheck.ts` (or `.test.ts`) that asserts:
  - `trackWorkspaceCreated` payload has no `name`.
  - `trackConnectorEvent` payload has no `connector_title`.
  - `trackWorkspaceInviteDeclined` payload has no `workspace_name`.
  - `trackYouTubeImport` payload has no `url`.
  - `safeCapture` swallows thrown errors from `posthog.capture`.

## Dev Notes

- **Port the pattern, not the file.** Nowing already has a PostHog skeleton. The work is privacy hardening and scoping, not a greenfield integration.
- **Why some outcome events stay in the frontend.** Upstream PR #1622 removes optimistic outcome events (`workspace_created`, `auth_login_success`, `document_upload_success`, `connector_connected`, etc.) because `surfsense_backend/app/observability/analytics.py` emits them authoritatively. Nowing does not yet have that backend product-analytics module, and this web story keeps server-side observability separate (PostHog for product analytics, OpenTelemetry for observability). Therefore the existing frontend outcome events are retained but must be scrubbed of PII. They should be removed when a future backend analytics story lands.
- **`NEXT_PUBLIC_*` are build-time constants.** For self-hosted builds, `NEXT_PUBLIC_POSTHOG_KEY` must be set during `next build`. An empty/unset key is the opt-out switch and must be safe at runtime.
- **Ad-blocker safety.** All `posthog` calls in the app are already wrapped in `try/catch` or lazy `import()`. Any new capture helper must follow the same rule.
- **Superuser rule.** A superuser is anyone with `User.is_superuser === true`. Their email and display name are never attached to the PostHog person, and their workspace content is not sent. This prevents internal/admin activity from polluting product analytics with PII.
- **Do not use PostHog for application logging.** Error tracking is limited to 5xx/network failures and uncaught runtime errors. 4xx validation/auth errors and business logic failures stay in normal logging, not PostHog.

## Verification

- [ ] Web typecheck and lint:
  ```bash
  cd nowing_web
  pnpm tsc --noEmit
  pnpm exec biome check --max-diagnostics=500 \
    instrumentation-client.ts \
    instrumentation.ts \
    lib/posthog/events.ts \
    lib/posthog/server.ts \
    lib/apis/base-api.service.ts \
    components/providers/PostHogIdentify.tsx \
    components/providers/PostHogReferral.tsx \
    components/layout/ui/dialogs/CreateWorkspaceDialog.tsx \
    app/invite/\[invite_code\]/page.tsx \
    app/dashboard/\[workspace_id\]/team/team-content.tsx
  ```
- [ ] With `NEXT_PUBLIC_POSTHOG_KEY=` (empty), the app builds and loads without PostHog network calls and without `lib/posthog/server.ts` throwing.
- [ ] With `NEXT_PUBLIC_POSTHOG_KEY=phc_...`, the browser devtools Network tab shows `pageview`, `identify` (non-superuser), `chat_message_sent`, `workspace_created`, `workspace_invite_sent`, and `connector_setup_started` events, and none of their payloads contain `name`, `workspace_name`, `email`, `url`, `connector_title`, or API keys.
- [ ] For a superuser, the `identify` call contains `is_internal_user: true` and no `email`/`name`.
- [ ] `base-api.service.ts` only sends `captureException` for 5xx and network failures; 403/404/422 are silent.
- [ ] Self-check or test for `lib/posthog/events.ts` passes:
  ```bash
  cd nowing_web
  npx tsx lib/posthog/events.selfcheck.ts
  ```

## References

- Upstream PR: `MODSetter/SurfSense#1622`
- Upstream commit: `dbedf0cfa53e604e4b9bc3f26f29691b691ddeb4`
- `nowing_web/app/layout.tsx` (`PostHogProvider`)
- `nowing_web/instrumentation-client.ts` (PostHog init, pageview, `before_send`)
- `nowing_web/instrumentation.ts` (server-side request error capture)
- `nowing_web/components/providers/PostHogProvider.tsx`
- `nowing_web/components/providers/PostHogIdentify.tsx`
- `nowing_web/components/providers/PostHogReferral.tsx`
- `nowing_web/lib/posthog/events.ts`
- `nowing_web/lib/posthog/server.ts`
- `nowing_web/lib/apis/base-api.service.ts`
- `nowing_web/lib/connector-telemetry.ts`
- `nowing_web/contracts/types/user.types.ts`
- `nowing_web/.env.example`
- `nowing_web/components/layout/ui/dialogs/CreateWorkspaceDialog.tsx`
- `nowing_web/app/invite/[invite_code]/page.tsx`
- `nowing_web/app/dashboard/[workspace_id]/team/team-content.tsx`
- `nowing_web/hooks/use-run-stream.ts`
- `nowing_web/lib/chat/stream-engine/engine.ts`
