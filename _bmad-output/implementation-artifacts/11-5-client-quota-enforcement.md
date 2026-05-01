# Story 11.5: Client-Side Quota Enforcement (Zero-sync)

Status: ready-for-dev

## Story

As a product owner,
I want subscription quota được enforce ở client-side cho crypto data đã sync qua Zero,
so that users không bypass quota bằng cách đọc IndexedDB offline sau khi subscription expire.

## Acceptance Criteria

1. **Given** user có `subscription_current_period_end` đã qua, **When** user mở crypto report page, **Then** deep research content bị redact — chỉ hiển thị basic metadata (symbol, price, last updated).
2. **Given** user có active subscription, **When** user mở crypto report page, **Then** full content render bình thường — không có redaction.
3. **Given** user's subscription expire trong khi đang offline, **When** user mở app offline, **Then** client check `subscription_current_period_end` từ local Zero cache và apply redaction ngay.
4. **Given** user renew subscription, **When** Zero-sync push `subscription_current_period_end` mới, **Then** content unlock ngay — không cần refresh page.
5. **Given** redacted view, **When** user nhìn thấy, **Then** UI hiển thị upgrade prompt: "Upgrade to Pro to access full analysis" với CTA link tới pricing page.
6. **Given** redaction logic, **When** kiểm tra, **Then** logic nằm trong shared utility (không duplicate giữa components).

## Tasks / Subtasks

- [ ] Task 1: Subscription check utility (AC: #1, #2, #3, #6)
  - [ ] 1.1 Tạo hook `useSubscriptionGate()` trong `nowing_web/hooks/` (NEW) — đọc `subscription_current_period_end` từ Zero user record
  - [ ] 1.2 Return `{ isActive: boolean, expiresAt: Date | null, isPro: boolean }`
  - [ ] 1.3 Logic: `isActive = subscription_current_period_end > Date.now()` — pure client-side check
- [ ] Task 2: Crypto content gating (AC: #1, #5)
  - [ ] 2.1 Tạo wrapper component `ProContentGate` (NEW) — render children nếu active, render redacted view + upgrade CTA nếu expired
  - [ ] 2.2 Redacted view: hiển thị symbol + price + "Updated X ago" nhưng blur/hide full analysis text
  - [ ] 2.3 Upgrade CTA: link tới `/dashboard/[search_space_id]/settings` hoặc pricing page
- [ ] Task 3: Integration vào crypto report components (AC: #1, #2, #4)
  - [ ] 3.1 Wrap deep research content sections trong `ProContentGate`
  - [ ] 3.2 Verify Zero-sync reactive: khi `subscription_current_period_end` update, component re-render
- [ ] Task 4: Tests
  - [ ] 4.1 Unit test: `useSubscriptionGate` trả `isActive=false` khi expired
  - [ ] 4.2 Unit test: `useSubscriptionGate` trả `isActive=true` khi active
  - [ ] 4.3 Component test: `ProContentGate` render children khi active, render CTA khi expired
  - [ ] 4.4 Component test: dynamic unlock khi subscription renew (mock Zero update)

## Dev Notes

### Architecture Compliance

- **Zero-first approach**: Đọc subscription data từ Zero query hook, KHÔNG fetch từ REST API.
- **Client Components**: `useSubscriptionGate` dùng hooks → parent component PHẢI có `"use client"` directive.
- **Naming conventions**: Hook file `use-subscription-gate.ts` (kebab-case), component file `ProContentGate.tsx` (PascalCase).
- **State management**: Hook đọc từ Zero cache — TanStack Query KHÔNG cần thiết cho data này.

### Existing Code to Modify

| File | Action | Notes |
|------|--------|-------|
| `nowing_web/hooks/use-subscription-gate.ts` | NEW | Subscription check hook |
| `nowing_web/components/crypto/ProContentGate.tsx` | NEW | Gating wrapper component |
| Crypto report page components | UPDATE | Wrap deep research sections |

### Security Note

- Client-side enforcement là **UX convenience**, KHÔNG phải security boundary. Server-side enforcement (API + RLS) vẫn là primary. Story này chỉ prevent passive offline bypass.
- KHÔNG expose sensitive business logic (pricing tiers, feature flags) trong client-side code — chỉ check timestamp.

### Anti-patterns to Avoid

- **KHÔNG** fetch subscription status từ API — đọc từ Zero local cache
- **KHÔNG** duplicate check logic giữa components — centralize trong `useSubscriptionGate()`
- **KHÔNG** hard-delete data từ IndexedDB khi expire — chỉ redact UI rendering
- **KHÔNG** block page load — render redacted view ngay, không loading state

### References

- [Source: _bmad-output/architecture-improvement-proposals-2026-05-01.md#5]
- [Source: _bmad-output/planning-artifacts/architecture.md#Data Architecture — Crypto Cache Workspace Isolation]
- [Source: _bmad-output/planning-artifacts/architecture.md#Frontend Architecture — State Management]
- [Source: nowing_web/hooks/ — existing hook patterns]

## Dev Agent Record

### Agent Model Used

### Debug Log References

### Completion Notes List

### File List
