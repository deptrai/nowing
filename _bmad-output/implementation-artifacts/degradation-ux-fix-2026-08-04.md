# Deep-research degradation UX fix

## Root cause

`chainlens.research` returns a `ResearchOutput` whose `status` can be `engine_unavailable`, `partial`, `timeout`, or `insufficient_evidence`. The backend also sets `degraded: true`, a `degradation_reason`, a human-readable `next_action`, and—when KB fallback is used—`sources` from the workspace knowledge base.

The frontend timeline was dropping that signal in two places:

1. `nowing_web/features/chat-messages/timeline/build-timeline.ts` mapped the tool-call item status only from the thinking step (`step.status`) and never inspected `result.degraded`. So a `ResearchOutput` with `status = "engine_unavailable"` still became `ItemStatus = "completed"`.
2. `nowing_web/features/chat-messages/timeline/timeline.tsx:91-97` then saw every item as `completed`/`cancelled`/`error` and rendered the global header as **"Reviewed"**.
3. `nowing_web/features/chat-messages/timeline/tool-registry/fallback/default-fallback-card.tsx` only branched on `cancelled`/`error`/`running`; a `completed` item always got a green checkmark, and the raw result JSON was shown instead of a readable warning, `next_action`, and citations.

Because `nowing_web/features/chat-messages/timeline/tool-registry/registry.ts` has no dedicated `chainlens.research` body, the tool falls through to `FallbackToolBody` → `DefaultFallbackCard`, so the fix belongs in the shared fallback rather than a one-off component.

## Files changed

- `nowing_web/features/chat-messages/timeline/types.ts`
  - Added `degraded?: boolean` to `ToolCallItem`.
- `nowing_web/features/chat-messages/timeline/tool-registry/types.ts`
  - Added `degraded?: boolean` to `TimelineToolProps`.
- `nowing_web/features/chat-messages/timeline/tool-registry/adapt-props.ts`
  - Forwards `item.degraded` into `TimelineToolProps`.
- `nowing_web/features/chat-messages/timeline/build-timeline.ts`
  - Added `isDegradedResult()` helper.
  - Sets `degraded` on both joined and orphan `ToolCallItem`s.
- `nowing_web/features/chat-messages/timeline/timeline.tsx`
  - Header now reads `result.status` from any `degraded` item and shows:
    - `Engine unavailable — fallback`
    - `Partial result`
    - `No sources found`
    - `Degraded`
    - or the original `Reviewed` when nothing is degraded.
- `nowing_web/features/chat-messages/timeline/tool-registry/fallback/default-fallback-card.tsx`
  - Detects `ResearchOutput`-shaped results.
  - For degraded/chainlens research results:
    - amber warning icon and border,
    - status badge (`Engine unavailable`, `Partial result`, etc.),
    - `next_action` subtitle (including the fallback-KB message),
    - structured `Answer` + `Sources` view,
    - KB sources rendered with a `Database` icon and "Workspace KB" label,
    - web sources rendered as link chips with a `Globe` icon.
  - Non-research tools still get the original raw-JSON fallback.
- `nowing_web/contracts/enums/toolIcons.tsx`
  - Added icon and display name for `chainlens_research` so the card title renders as **"Deep research"** with a `Search` icon.

## What was NOT changed

- Backend was not modified.
  - `nowing_backend/app/capabilities/core/access/agent.py:145-179` returns `{"run_id": ..., "status": "running"}` for async deep-research starts; that path is unchanged.
  - `nowing_backend/app/capabilities/chainlens/research/executor.py:369-425` and `schemas.py` were only read to confirm the output contract.
- `nowing_web/features/chat-messages/timeline/tool-registry/registry.ts` was not modified; the fallback body now correctly handles `chainlens_research`, so a dedicated registry entry is unnecessary.

## Diff summary

- Added `degraded` propagation through `ToolCallItem` → `buildTimeline` → `adaptItemToProps` → `TimelineToolProps`.
- `DefaultFallbackCard` now branches on `degraded` and renders a `ResearchResultView` when the result is a `ResearchOutput` from `chainlens_research`.
- The timeline global header no longer says "Reviewed" when a deep-research step returned a degraded status.
- Citations are preserved and displayed; workspace KB hits use an internal `nowing://` URL and are labeled "Workspace KB", while web sources are clickable.

## Verification steps

From `nowing_web/`:

```bash
pnpm tsc --noEmit
pnpm exec biome check features/chat-messages/timeline/types.ts \
  features/chat-messages/timeline/build-timeline.ts \
  features/chat-messages/timeline/timeline.tsx \
  features/chat-messages/timeline/tool-registry/types.ts \
  features/chat-messages/timeline/tool-registry/adapt-props.ts \
  features/chat-messages/timeline/tool-registry/fallback/default-fallback-card.tsx \
  contracts/enums/toolIcons.tsx
```

Both commands passed.

### Manual UI smoke test (dev can do in browser)

1. Start the app with `pnpm dev` (or `pnpm dev:turbo`).
2. In a workspace with no `CHAINLENS_API_KEY` (or with the engine unreachable), ask a deep-research question.
3. Observe:
   - Timeline header changes from "Reviewed" to **"Engine unavailable — fallback"** (or "Partial result" / "No sources found").
   - The deep-research card shows an **amber warning icon**, a **"Engine unavailable"** or **"Partial result"** badge, and the `next_action` message.
   - If workspace KB fallback returned hits, the **"Workspace knowledge base sources"** list is rendered with titles and snippets.
4. With `CHAINLENS_API_KEY` set and the engine healthy, the same card shows a green checkmark and the normal sources list.

## Notes

- The fix is frontend-only and interpretation-based; it does not change the `ResearchOutput` schema or the executor.
- `degraded` is intentionally a generic flag so any future tool that returns `degraded: true` will also get the amber treatment, not just `chainlens.research`.
