# Test Automation Summary — bmad-testarch-automate
**Date**: 2026-04-21  
**Stack**: `nowing_web` frontend (Vitest 3.2.4 + @testing-library/react)  
**Mode**: Sequential (Create)

---

## Files Generated This Session

| File | Tests | Status |
|------|-------|--------|
| `__tests__/lib/announcements/announcements-utils.test.ts` | 23 | ✅ PASS |
| `__tests__/lib/announcements/announcements-storage.test.ts` | 21 | ✅ PASS |
| `__tests__/lib/auth-utils.test.ts` | 32 | ✅ PASS |
| `__tests__/lib/chat/message-utils.test.ts` | 21 | ✅ PASS |
| `__tests__/lib/format-date.test.ts` | 15 | ✅ PASS |

**Total new tests**: 112 (covering `__tests__/lib/`)  
**All lib tests**: 112/112 PASS

---

## Coverage Map

### `lib/announcements/announcements-utils.ts`
- `isAnnouncementActive` — 8 tests (range, boundaries, invalid dates, inverted window)
- `announcementMatchesAudience` — 5 tests (all/users/web_visitors/unknown)
- `getActiveAnnouncements` — 4 tests (filter by active + audience)
- `msUntilNextTransition` — 6 tests (future start/end, nearest, all-past, empty, invalid)

### `lib/announcements/announcements-storage.ts`
- `getAnnouncementState` — 6 tests (empty, persisted, malformed JSON, partial state)
- `markAnnouncementRead` — 4 tests (add, dedup, persist, preserve existing)
- `markAllAnnouncementsRead` — 4 tests (mark all, dedup, no-op, empty input)
- `markAnnouncementToasted` — 3 tests (add, dedup, isolation from readIds)
- `isAnnouncementRead` / `isAnnouncementToasted` — 4 tests

### `lib/auth-utils.ts` — P0 Security Critical
- `isPublicRoute` — 19 tests (all public prefixes + protected routes)
- `handleUnauthorized` — 9 tests (clears both tokens, redirects on protected, saves redirect path, excluded paths: /auth /auth/callback /, no redirect on public)
- `getAndClearRedirectPath` — 4 tests (null, returns value, clears, null on 2nd call)

### `lib/chat/message-utils.ts`
- String content — 2 tests
- Non-string/non-array fallback — 2 tests
- Array content basic — 4 tests
- Filter mentioned-documents/attachments — 3 tests
- thinking-steps → data-thinking-steps migration — 4 tests
- Return shape (id, role, createdAt, metadata) — 6 tests

### `lib/format-date.ts`
- "Just now" (< 1 min) — 3 tests
- "Xm ago" (1–59 min) — 3 tests
- "Today, …" (same day, ≥ 60 min) — 2 tests
- "Yesterday, …" — 2 tests
- "Xd ago" (2–6 days) — 2 tests
- Absolute "MMM d, yyyy" (≥ 7 days) — 3 tests

---

## Previously Generated (Pre-Skill, AC Gaps)
| File | Tests |
|------|-------|
| `__tests__/lib/announcements/announcements-utils.test.ts` | (generated this session) |
| `__tests__/app/redeem/redeem-page.test.tsx` | 7 (FE-11) |
| `__tests__/components/pricing/offline-indicator.test.tsx` | 4 (FE-6, fixed) |
| `__tests__/components/new-chat/system-model-selector.test.tsx` | 11 (FE-5) |
| `__tests__/components/tool-ui/citation.test.tsx` | 8 (FE-4) |

---

## Notes
- All tests are pure unit/component level — no Playwright (detected_stack: frontend only)
- localStorage tests use mock store pattern (not `vi.clearAllMocks` to avoid wiping implementations)
- `formatRelativeDate` uses `vi.useFakeTimers()` + `vi.setSystemTime()` for deterministic date branches
- auth-utils P0 tests cover both clear-tokens AND redirect behavior precisely
