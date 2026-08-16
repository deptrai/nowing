# Story 7.8: Vietnamese i18n & Smart Geo-Locale Auto-Detection

**Status:** done  
**Epic:** 7 — Multi-surface Clients (Web UI & Localization)  
**Priority:** HIGH  
**Requirements:** FR-1, FR-25, UI-I18N  

---

## Story

As a Vietnamese user or international visitor,  
I want Nowing to support Vietnamese language and automatically detect my location / locale on my first visit to present the appropriate language,  
So that I can immediately experience the application in my native language without manual switching, while retaining my language preferences if I choose to change them.

---

## Context

Nowing is expanding deeply into the Vietnam market (Real Estate, Recruitment, Business Tax Verification, Lead Gen). The frontend `nowing_web` currently supports 6 languages (`en`, `es`, `pt`, `hi`, `zh`, `ko`), but lacks Vietnamese (`vi`).

Furthermore, users entering the application for the first time currently default to English (`en`) regardless of their browser locale or geographic location.

### Objectives
1. Add full Vietnamese translation dictionary `messages/vi.json` covering 100% of keys present in `messages/en.json`.
2. Update `routing.ts` to include `"vi"` in supported locales.
3. Update `LocaleContext.tsx` to:
   - Include `"vi"` in `Locale` type and dynamic message loader.
   - Implement `detectInitialLocale()` to check `navigator.languages` (e.g. `vi`, `vi-VN`) and Vietnam timezone (`Asia/Ho_Chi_Minh`, `Asia/Saigon`, `Asia/Hanoi`, `Asia/Bangkok`).
   - On first visit (`localStorage.getItem("nowing-locale") === null`), automatically detect and set the initial locale, persisting it to `localStorage`.
   - On subsequent visits or if a user has explicitly chosen a locale, preserve the stored locale and **do not override** it.
4. Update UI language selectors (`LanguageSwitcher.tsx`, `SidebarUserProfile.tsx`) with `🇻🇳 Tiếng Việt`.

---

## Acceptance Criteria

1. **First-Time Visit Auto-Detection (Vietnamese)**:
   - **Given** a first-time user with no `nowing-locale` in `localStorage`,
   - **When** their browser language starts with `vi` OR their timezone is `Asia/Ho_Chi_Minh` / `Asia/Saigon` / `Asia/Hanoi` / `Asia/Bangkok`,
   - **Then** the application automatically selects `vi`, loads `messages/vi.json`, updates `<html lang="vi">`, and persists `nowing-locale="vi"` to `localStorage`.

2. **First-Time Visit Auto-Detection (Other Locales & Fallback)**:
   - **Given** a first-time user with no `nowing-locale` in `localStorage`,
   - **When** their browser language matches a supported locale (`es`, `pt`, `hi`, `zh`, `ko`),
   - **Then** the application auto-selects that locale and persists it;
   - **Otherwise** it defaults to `en` and persists it.

3. **User Preference Persistence (No Override)**:
   - **Given** a user who has previously visited or manually changed language via `LanguageSwitcher` or `SidebarUserProfile`,
   - **When** they reload the page, open a new tab, or navigate between routes,
   - **Then** the application strictly retains the stored language from `localStorage` without re-triggering auto-detection.

4. **UI Components & Language Switchers**:
   - **Given** the `LanguageSwitcher` in the header or `SidebarUserProfile` menu,
   - **When** opened,
   - **Then** `🇻🇳 Tiếng Việt` is present with proper flag icon and label, and clicking it immediately switches the UI language to Vietnamese.

5. **Typecheck & Code Hygiene**:
   - `pnpm tsc --noEmit` and `pnpm exec biome check` in `nowing_web/` pass with 0 errors.

---

## Tasks / Subtasks

- [x] Task 1: Create complete `nowing_web/messages/vi.json` (AC: 1, 4)
  - [x] Generate comprehensive translations for all namespaces (`common`, `auth`, `workspace`, `userSettings`, `dashboard`, `navigation`, `nav_menu`, `usage`, `pricing`, `contact`, `connectors`, `documents`, `add_connector`, `upload_documents`, `add_webpage`, `add_youtube`, `settings`, `logs`, `onboard`, `model_config`, `sidebar`, `errors`, `workspaceSettings`, `homepage`, `public_chat`)
  - [x] Validate JSON syntax and structure alignment with `messages/en.json`
- [x] Task 2: Update `nowing_web/i18n/routing.ts` (AC: 1, 2, 4)
  - [x] Add `"vi"` to `locales` array: `["en", "vi", "es", "pt", "hi", "zh", "ko"]`
- [x] Task 3: Enhance `nowing_web/contexts/LocaleContext.tsx` (AC: 1, 2, 3)
  - [x] Update `Locale` type definition to include `"vi"`
  - [x] Add dynamic `loadMessages` case for `"vi"`
  - [x] Implement `detectInitialLocale()` helper for `navigator.languages` & timezone detection
  - [x] Update `useEffect` mount lifecycle to perform first-visit auto-detection and localStorage initialization
- [x] Task 4: Update UI Language Switcher components (AC: 4)
  - [x] Update `nowing_web/components/LanguageSwitcher.tsx` with `🇻🇳 Tiếng Việt`
  - [x] Update `nowing_web/components/layout/ui/sidebar/SidebarUserProfile.tsx` with `🇻🇳 Tiếng Việt`
- [x] Task 5: Verification & Quality Gate (AC: 5)
  - [x] Run `pnpm tsc --noEmit` in `nowing_web/`
  - [x] Run `pnpm exec biome check` in `nowing_web/`
  - [x] Verify unit behavior and hydration safety

---

## Dev Notes

### Files Being Modified
- `nowing_web/messages/vi.json` [NEW]
- `nowing_web/i18n/routing.ts` [MODIFY]
- `nowing_web/contexts/LocaleContext.tsx` [MODIFY]
- `nowing_web/components/LanguageSwitcher.tsx` [MODIFY]
- `nowing_web/components/layout/ui/sidebar/SidebarUserProfile.tsx` [MODIFY]

### Technical Guardrails
- **Hydration Mismatch Prevention**: `LocaleContext` initializes `locale` state with `"en"` and updates after mount in `useEffect`, matching existing design to prevent SSR hydration errors.
- **Font Support**: `app/layout.tsx` already includes `subsets: ["latin", "vietnamese"]` for `Inter` and `JetBrains_Mono`.
- **Locale Persistence Key**: Use existing `LOCALE_STORAGE_KEY = "nowing-locale"`.

---

## Dev Agent Record

### Agent Model Used
Gemini 3.7 Flash

### Completion Notes List
- Created `nowing_web/messages/vi.json` with 100% dictionary translations for all 25 namespaces.
- Updated `nowing_web/i18n/routing.ts` adding `"vi"`.
- Implemented `detectInitialLocale()` in `nowing_web/contexts/LocaleContext.tsx` with `navigator.languages` and VN timezone (`Asia/Ho_Chi_Minh`, `Asia/Saigon`, `Asia/Hanoi`, `Asia/Bangkok`) checks, alongside first-visit `localStorage` persistence and no-override guarantee.
- Added `🇻🇳 Tiếng Việt` to `nowing_web/components/LanguageSwitcher.tsx` and `nowing_web/components/layout/ui/sidebar/SidebarUserProfile.tsx`.
- Verified `pnpm tsc --noEmit` (0 errors) and `pnpm exec biome check` (clean).

### File List
- `nowing_web/messages/vi.json`
- `nowing_web/i18n/routing.ts`
- `nowing_web/contexts/LocaleContext.tsx`
- `nowing_web/components/LanguageSwitcher.tsx`
- `nowing_web/components/layout/ui/sidebar/SidebarUserProfile.tsx`
- `nowing_web/components/leads/NowingLeadMatrix.tsx`
