# Story 8.13: PostHog Product Analytics

**Status:** in-progress
**Epic:** 8 — Platform Operations
**Priority:** MEDIUM
**Requirements:** NFR-3
**Architecture:** AD-9

## Story

As a product team,
I want PostHog analytics integrated into the web app,
So that I can understand user flows, feature adoption, and retention.

## Acceptance Criteria

1. **Initialization & pageview** — `posthog-js` initializes, history-change pageviews, page-leave, platform/ref person properties, deferred load.
2. **User identification & superuser anonymization** — superusers omit `email`/`name`, set `is_internal_user: true`; reset on public routes/logout.
3. **Key action event capture** — workspace create, scraper run, chat, invite send low-cardinality identifiers only.
4. **Privacy / secrets** — no API keys, workspace/user names, emails, raw URLs, document/connector titles, or message content.
5. **Error capture scoping** — only 5xx and network failures go to PostHog; 4xx silent.
6. **Opt-out / self-host** — empty `NEXT_PUBLIC_POSTHOG_KEY` means no client, no requests, no throw from server helper.

## Task List

- `nowing_web/lib/posthog/events.ts` — privacy hardening, remove dead helpers, add safeCapture comment.
- `nowing_web/components/providers/PostHogIdentify.tsx` — superuser PII guard.
- `nowing_web/lib/apis/base-api.service.ts` — scope PostHog exception capture to 5xx/network.
- `nowing_web/lib/posthog/server.ts` — no-op when key missing.
- `nowing_web/instrumentation.ts` — handle no-op PostHog.
- Call-site cleanup in `CreateWorkspaceDialog`, invite page, team content.
- Add `lib/posthog/events.selfcheck.ts` and run.
- Typecheck + lint.
- E2E Playwright smoke with seed account.
