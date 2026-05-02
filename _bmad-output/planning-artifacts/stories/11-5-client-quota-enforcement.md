# Story 11.5: Client-Side Quota Enforcement

Status: ready-for-dev

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

- [ ] Task 1: Subscription check wrapper (AC: #1, #2, #5)
  - [ ] 1.1 Tạo hook `useSubscriptionGate()` trong `nowing_web/hooks/use-subscription-gate.ts` (NEW) — wrapper quanh existing `useProStatus()`
  - [ ] 1.2 Return `{ isPro: boolean, isLoading: boolean }`
  - [ ] 1.3 Reuse logic từ `nowing_web/src/hooks/use-pro-status.ts` và `nowing_web/src/lib/entitlements.ts`
- [ ] Task 2: Crypto content gating (AC: #1, #4)
  - [ ] 2.1 Tạo wrapper component `ProContentGate.tsx` trong `nowing_web/components/crypto/` (NEW)
  - [ ] 2.2 Render children nếu `isPro`, render redacted view + upgrade CTA nếu không
  - [ ] 2.3 Redacted view: hiển thị symbol + price nhưng blur full analysis (`backdrop-filter: blur(8px)`) + centered upgrade card
  - [ ] 2.4 Upgrade CTA: link tới `/pricing` — clone pattern từ `upgrade-modal.tsx` và `quota-exceeded-modal.tsx`
- [ ] Task 3: Integration vào crypto report components (AC: #1, #2, #3)
  - [ ] 3.1 Wrap deep research content sections trong `ProContentGate`
  - [ ] 3.2 Verify re-render khi subscription status changes (Clerk triggers)
- [ ] Task 4: Tests
  - [ ] 4.1 Unit test: `useSubscriptionGate` trả `isPro=false` khi expired
  - [ ] 4.2 Unit test: `useSubscriptionGate` trả `isPro=true` khi active
  - [ ] 4.3 Component test: `ProContentGate` render children khi pro, render CTA khi not pro
  - [ ] 4.4 Component test: offline scenario → content renders (no enforcement)

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

### Debug Log References

### Completion Notes List

### File List
