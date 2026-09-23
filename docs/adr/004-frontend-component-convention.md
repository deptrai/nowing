# ADR-004: Convention tách frontend component/hook

## Status

Accepted — dự kiến thực hiện (Giai đoạn E)

## Context

Frontend có nhiều file/hook phình to:
- `apps/nowing_web/hooks/use-connector-dialog.ts` — 1.433 dòng
- `apps/nowing_web/components/assistant-ui/thread.tsx` — 2.413 dòng
- `apps/nowing_web/components/campaigns/CampaignBuilder.tsx` — 1.293 dòng
- `node_modules/.next` nặng 3.6 GB (cache, duplicate dependencies)

Các file này khiến bundle khó tối ưu, logic UI và logic nghiệp vụ lẫn lộn, khó viết test.

## Decision

### Hook tách theo chức năng
`use-connector-dialog.ts` thành:
- `useConnectorOAuth` — cookie OAuth, parse callback.
- `useConnectorIndexing` — date range, frequency, vision LLM, periodic sync.
- `useConnectorEdit` — update/delete connector.
- `useConnectorAccounts` — quản lý multiple accounts.
- `useMCPConnectors` — MCP list/connection.
- `useConnectorDialogState` — open/close/tab state.

### Component tách theo UI primitive
`thread.tsx` thành:
- `Composer.tsx`
- `Thread.tsx`
- `ThreadMessage.tsx`
- `ComposerAction.tsx`
- `ThreadScroll.tsx`

### Campaign builder tách theo step + state
- `AudienceStep`, `ContentStep`, `ScheduleStep`, `ReviewStep`
- `useCampaignBuilder()` quản lý state.

### Bundle size
- Chạy `next-bundle-analyzer` định kỳ.
- Lazy-load icons, connector views, heavy editors.
- Dọn `node_modules/.next` cache.
- Freeze API của `Button`, `cn`, `Input`, `Skeleton`, `Label`; thêm prop mới phải qua ADR.

## Consequences

- Component < 400 dòng, hook < 300 dòng.
- Tăng khả năng test và tái sử dụng.
- Cần theo dõi bundle analyzer để tránh regression.

## Related

- [[ADR-003-split-routes-and-services]]
