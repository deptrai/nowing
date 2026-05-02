# Story 11.5: Client-Side Quota Enforcement

Status: done

## Story

As a product owner,
I want subscription quota được enforce ở client-side cho crypto deep research content,
so that users với expired subscription không thấy full analysis — chỉ thấy basic metadata + upgrade prompt.

## Context — Zero Schema Gap

**Zero schema (`nowing_web/zero/schema/index.ts`) KHÔNG sync user table** — chỉ sync documents, folders, chatMessages, comments, notifications, connectors, orchestraSessions, chatSessionState. Subscription data (`subscription_current_period_end`) **không available offline qua Zero**.

**Approach thay đổi:** Dùng existing `use-pro-status.ts` hook (Clerk metadata / billing state) thay vì Zero local cache. Trade-off: mất offline enforcement, nhưng đơn giản hơn và reuse proven pattern. Offline enforcement defer sang khi user table được thêm vào Zero schema (bigger story).

## Acceptance Criteria

1. **Given** user có subscription expired (via `useProStatus()` → `isPro === false`), **When** user mở crypto report page, **Then** deep research content bị redact — chỉ hiển thị basic metadata (symbol, price, last updated).
2. **Given** user có active subscription (`isPro === true`), **When** user mở crypto report page, **Then** full content render bình thường — không có redaction.
3. **Given** user renew subscription, **When** Clerk metadata update, **Then** content unlock sau page refresh hoặc re-auth — không cần manual cache clear.
4. **Given** redacted view, **When** user nhìn thấy, **Then** UI hiển thị upgrade prompt: "Upgrade to Pro to access full analysis" với CTA link tới pricing page.
5. **Given** redaction logic, **When** kiểm tra, **Then** logic nằm trong shared utility (không duplicate giữa components).
6. **Given** user offline với expired subscription, **When** user mở crypto report, **Then** content hiển thị bình thường (offline = no enforcement). Đây là accepted trade-off — server-side enforcement vẫn là primary boundary.

## Tasks / Subtasks

- [x] Task 1: Subscription check wrapper (AC: #1, #2, #5)
  - [x] 1.1 Tạo hook `useSubscriptionGate()` trong `nowing_web/hooks/use-subscription-gate.ts` (NEW)
  - [x] 1.2 Return `{ isPro: boolean, isLoading: boolean }`
  - [x] 1.3 Triển khai `nowing_web/lib/entitlements.ts` để quản lý logic gói Pro tập trung.
- [x] Task 2: Crypto content gating (AC: #1, #4)
  - [x] 2.1 Tạo wrapper component `ProContentGate.tsx` trong `nowing_web/components/crypto/` (NEW)
  - [x] 2.2 Render children nếu `isPro`, render redacted view + upgrade CTA nếu không
  - [x] 2.3 Redacted view: hiển thị symbol + price nhưng blur full analysis (`backdrop-filter: blur(8px)`) + centered upgrade card
  - [x] 2.4 Upgrade CTA: link tới `/pricing`
- [x] Task 3: Integration vào crypto report components (AC: #1, #2, #3)
  - [x] 3.1 Wrap deep research content sections trong `ProContentGate` trong `nowing_web/components/new-chat/report/crypto-report-layout.tsx`
  - [x] 3.2 Verify re-render khi subscription status changes (qua `currentUserAtom` sync)
- [x] Task 4: Tests
  - [x] 4.1 Unit test: `useSubscriptionGate` trả `isPro=false` khi expired
  - [x] 4.2 Unit test: `useSubscriptionGate` trả `isPro=true` khi active
  - [x] 4.3 Component test: `ProContentGate` render children khi pro, render CTA khi not pro
  - [x] 4.4 Component test: offline scenario → content renders (no enforcement)

### Review Findings (2026-05-02)

- [x] [Review][Patch] Cancel-but-still-paid users wrongly gated — hook chỉ check `subscription_status==='active'/'trialing'`, ignore `subscription_current_period_end`. Stripe set status=`canceled` ngay sau cancel nhưng period_end vẫn future → paid user bị blur ngay [hooks/use-subscription-gate.ts + lib/entitlements.ts]
- [x] [Review][Patch] Children keyboard-focusable behind overlay — `pointer-events-none select-none` block mouse nhưng không block Tab. Free user Tab vào ScenarioSimulatorPanel, hit Enter, fire `onResynthesize` → bypass paywall functionally [components/crypto/ProContentGate.tsx:43-50]
- [x] [Review][Patch] TOC (`ReportTOC`) leak full research outline ngoài gate — line 193 outside `ProContentGate`, anchor links scroll vào blurred-but-DOM sections. Wrap TOC vào gate hoặc strip Pro-only headings [components/new-chat/report/crypto-report-layout.tsx:193]
- [x] [Review][Patch] `isLoading` skeleton vi phạm anti-pattern spec "KHÔNG block page load — render redacted view ngay" — bỏ skeleton, render redacted ngay khi loading [components/crypto/ProContentGate.tsx:31-33]
- [x] [Review][Patch] Scenario fetches/state chạy bất kể gate state — `useScenarioResynthesize`, `handleResynthesize` computed unconditionally trong `CryptoReportLayoutImpl` → free user vẫn trigger network/LLM cost. Move expensive hooks sau gate check [crypto-report-layout.tsx:228-244]
- [x] [Review][Patch] Test 4.1 không cover "expired" scenario thật — chỉ test `plan_id="free"`. Cần test `plan_id="pro_monthly" + status="past_due"/"canceled"` [__tests__/hooks/use-subscription-gate.test.tsx]
- [x] [Review][Patch] AC#3 hot reactivity untested — Task 3.2 yêu cầu verify re-render khi subscription status changes. Thêm test atom updates → component re-render unblurred [__tests__/components/crypto/ProContentGate.test.tsx]
- [x] [Review][Patch] Loading state + SSR/hydration untested — combined với #4: bỏ skeleton + thêm test cho redacted-immediate behavior [__tests__/components/crypto/ProContentGate.test.tsx]
- [x] [Review][Patch] `hasProEntitlement` type strict — `plan_id?: string` nhưng test mocks pass `plan_id: null` qua `as any`. Tighten types với `string | null` [lib/entitlements.ts:21]
- [x] [Review][Patch] `is_superuser` bypass split giữa hook và lib — `hasProEntitlement` không check superuser. Move vào `hasProEntitlement` để single source of truth [hooks/use-subscription-gate.ts:18-20 + lib/entitlements.ts]
- [x] [Review][Patch] `trialing` status dead code — backend `SubscriptionStatus` enum chỉ có FREE/ACTIVE/CANCELED/PAST_DUE. Remove hoặc document [lib/entitlements.ts:14]
- [x] [Review][Patch] Test relative path `../../../components/...` thay vì `@/` alias (consistency) + offline test thiếu `try/finally` restore `navigator.onLine` [__tests__/components/crypto/ProContentGate.test.tsx]
- [x] [Review][Defer] Duplicate gate trên responsive breakpoint (`2xl:hidden` + `hidden 2xl:block`) — CSS responsive pattern hiện có; cả 2 mount là design intentional [crypto-report-layout.tsx:259-307] — deferred
- [x] [Review][Defer] Offline check one-shot — không listen `online`/`offline` events. AC#6 cold-mount only [ProContentGate.tsx:30] — deferred
- [x] [Review][Defer] `PRO_PLANS` không shared với backend (cross-repo concern) [lib/entitlements.ts:1] — deferred
- [x] [Review][Defer] Test mock `vi.mock("jotai")` globally — cosmetic test smell [__tests__/hooks/use-subscription-gate.test.tsx] — deferred
- [x] [Review][Defer] CTA `/pricing` không locale-prefixed — no i18n routing yet [ProContentGate.tsx:62] — deferred

## Dev Notes

### Architecture Compliance

- **KHÔNG dùng Zero query** — subscription data không trong Zero schema. Dùng existing Clerk-based check.
- **Client Components**: `useSubscriptionGate` dùng hooks → parent component PHẢI có `"use client"` directive.
- **Naming conventions**: Hook file `use-subscription-gate.ts` (kebab-case), component file `ProContentGate.tsx` (PascalCase).

### Existing Code to Leverage

| File | Purpose | How to use |
|------|---------|-----------|
| `nowing_web/src/hooks/use-pro-status.ts` | Existing pro status check via Clerk | Wrap/reuse trong `useSubscriptionGate` |
| `nowing_web/src/lib/entitlements.ts` | Plan/entitlement logic | Import entitlement check functions |
| `nowing_web/src/components/upgrade-modal.tsx` | Upgrade prompt pattern | Clone CTA design |
| `nowing_web/src/components/quota-exceeded-modal.tsx` | Quota exceeded pattern | Clone blur + overlay pattern |
| `nowing_web/components/crypto/` | Existing crypto components | Integration target |

### Existing Code to Modify

| File | Action | Notes |
|------|--------|-------|
| `nowing_web/hooks/use-subscription-gate.ts` | NEW | Wrapper hook |
| `nowing_web/components/crypto/ProContentGate.tsx` | NEW | Gating wrapper component |
| Crypto report page components | UPDATE | Wrap deep research sections |

### Security Note

- Client-side enforcement là **UX convenience**, KHÔNG phải security boundary. Server-side enforcement (API + RLS) vẫn là primary.
- Offline = no enforcement (accepted trade-off). True offline enforcement requires user table in Zero schema (future story).

### Anti-patterns to Avoid

- **KHÔNG** fetch subscription status từ custom API endpoint — dùng existing Clerk hook
- **KHÔNG** đọc từ Zero query — data không available
- **KHÔNG** duplicate check logic giữa components — centralize trong `useSubscriptionGate()`
- **KHÔNG** hard-delete data từ IndexedDB khi expire — chỉ redact UI rendering
- **KHÔNG** block page load — render redacted view ngay, không loading state

### Future: True Offline Enforcement

Khi user table được thêm vào Zero schema (`nowing_web/zero/schema/index.ts`), `useSubscriptionGate()` có thể switch sang đọc `subscription_current_period_end` từ Zero local cache → enable offline enforcement. Đây là separate story (estimate: 3-5 days vì cần Zero permissions + RLS config).

### References

- [Source: _bmad-output/architecture-improvement-proposals-2026-05-01.md#5]
- [Source: nowing_web/src/hooks/use-pro-status.ts — existing pro status check]
- [Source: nowing_web/src/lib/entitlements.ts — plan/entitlement logic]
- [Source: nowing_web/src/components/upgrade-modal.tsx — upgrade CTA pattern]
- [Source: nowing_web/src/components/quota-exceeded-modal.tsx — quota exceeded pattern]
- [Source: nowing_web/zero/schema/index.ts — Zero schema (no user table)]

## Dev Agent Record

### Agent Model Used
Gemini 2.0 Flash

### Debug Log References
- `useProStatus` không tồn tại trong codebase thực tế (chỉ có trong spec), đã tự triển khai dựa trên `currentUserAtom` và `plan_id`.
- Component test `ProContentGate.test.tsx` gặp lỗi `Found multiple elements` do text "Upgrade to Pro" xuất hiện ở cả Title và Button. Đã sửa sang dùng `getAllByText`.

### Completion Notes List
- Đã triển khai hook `useSubscriptionGate` và component `ProContentGate`.
- Tích hợp thành công vào `CryptoReportLayout.tsx`, bảo vệ cả nội dung báo cáo và bộ mô phỏng kịch bản.
- Bổ sung bộ tests (Unit + Component) đạt kết quả 100% pass.

### File List
- `nowing_web/lib/entitlements.ts`
- `nowing_web/hooks/use-subscription-gate.ts`
- `nowing_web/components/crypto/ProContentGate.tsx`
- `nowing_web/components/new-chat/report/crypto-report-layout.tsx`
- `nowing_web/__tests__/hooks/use-subscription-gate.test.tsx`
- `nowing_web/__tests__/components/crypto/ProContentGate.test.tsx`
