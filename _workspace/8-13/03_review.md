# Code Review Report — Story 8.13

**Status:** ✅ PASS

## Changes Reviewed

- `nowing_web/lib/posthog/events.ts`
- `nowing_web/components/providers/PostHogIdentify.tsx`
- `nowing_web/lib/apis/base-api.service.ts`
- `nowing_web/lib/posthog/server.ts`
- `nowing_web/instrumentation.ts` (no change needed — already handles no-op return)
- `nowing_web/components/layout/ui/dialogs/CreateWorkspaceDialog.tsx`
- `nowing_web/app/invite/[invite_code]/page.tsx`
- `nowing_web/lib/posthog/events.selfcheck.ts`

## Findings

| # | Check | Result |
|---|---|---|
| H1 | `trackWorkspaceCreated` no longer sends workspace `name` | ✅ |
| H2 | `trackConnectorEvent` no longer sends `connector_title`; only type/group/is_oauth | ✅ |
| H3 | `trackWorkspaceInviteAccepted/UserAdded/Declined` no longer send `workspace_name` | ✅ |
| H4 | `PostHogIdentify` strips `email`/`name` for superusers and sets `is_internal_user` | ✅ |
| H5 | `base-api.service.ts` only captures `NetworkError` and 5xx `AppError` | ✅ |
| H6 | `lib/posthog/server.ts` returns a no-op when `NEXT_PUBLIC_POSTHOG_KEY` is missing | ✅ |
| M1 | Dead helpers removed (`trackWorkspaceViewed/Deleted`, `trackDocumentDeleted/BulkDeleted`, `trackConnectorSynced`, `trackYouTubeImport`) | ✅ |
| M2 | `events.selfcheck.ts` asserts payload shapes | ✅ |
| M3 | `pnpm tsc --noEmit` and `biome check` pass | ✅ |

## Verdict

Story 8.13 implementation is approved to proceed to Stage 4 (E2E testing).
