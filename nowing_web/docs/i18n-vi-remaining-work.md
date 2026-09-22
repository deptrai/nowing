# Vietnamese i18n — remaining work (resume guide)

## Status
- `messages/vi.json` is fully translated (commit a69524572). Remaining `vi==en` are legit proper nouns (Nowing, GitHub, Email, DNC, 99.2%, 15+).
- Done & committed: `app/(home)/free/page.tsx` (b6fe579de), `ChatUnavailableNotice` (c850abba2).
- `components/landing/*` (homepage) already translated. `components/homepage/*` is dead code (unused by `app/(home)/page.tsx`).

## Architecture
Client-side next-intl. `contexts/LocaleContext.tsx` detects vi (timezone Asia/Ho_Chi_Minh / navigator.languages) → localStorage `nowing-locale` → `components/providers/I18nProvider.tsx` → `NextIntlClientProvider`. No `[locale]` route; locale applies app-wide incl. dashboard & admin.
- Client components: `const t = useTranslations("<ns>")` (+ `import { useTranslations } from "next-intl"`).
- Server components: `const t = await getTranslations("<ns>")` (+ `import { getTranslations } from "next-intl/server"`, make export `async`).
- `en.json` uses space indent; `vi.json` uses tab indent — preserve when editing.

## What remains (≈260 files, run when inference gateway is healthy)
Prioritize user-facing, then internal:
1. Legal/marketing: `app/(home)/privacy|terms|partners|mcp-server|connectors|external-mcp-connectors|blog` pages.
2. Dashboard: `app/dashboard/[workspace_id]/{user-settings,team,automations,playground,research,new-chat,onboard,crm,purchase-*,web-builder}` + `components/{settings,leads,free-chat,new-chat,documents,pricing,usage,crm,connectors,...}`.
3. Internal/ops: `components/tool-ui/*`, `components/assistant-ui/*`, `app/admin/*`, `features/*` HITL cards.

## How to translate a file
1. Find hardcoded English: JSX text `>Some text<`, `placeholder=`, `aria-label=`, `title=`, `alt=`, `label=`, and object-array props (`title:`, `description:`).
2. Wrap each with `t("<snake_key>")` under a sensible namespace. For array/object strings, move them inside the component so `t()` can be used (or keep a keys array and map `t(key)`).
3. Add key to BOTH `messages/en.json` (English) and `messages/vi.json` (Vietnamese). Preserve `{placeholders}`/ICU plural.
4. `npx tsc --noEmit` → clean. Validate JSON parses. Commit per area.

## Codemod helper
`/Users/luisphan/.claude/jobs/1d92d639/tmp/i18n_codemod.py` (ephemeral — recreate if gone) does mechanical `>Capitalized<` → `t()` extraction. It under-extracts lowercase/array strings — always hand-review the diff and supply vi values. Safer: use it to LIST strings (`extract_strings.py`), then edit by hand or via sub-agent.

## Verify
- `npx tsc --noEmit`
- Playwright: `tests/i18n/vietnamese-locale-detection.spec.ts` + browse pages with locale=vi (localStorage `nowing-locale=vi` or vi-VN Accept-Language).

## ROOT CAUSE FIX (committed 0feaf94e0)
Pages "not translating despite vi selected" was NOT missing keys — it was that **server components' `getTranslations` always resolved `en`**, because `requestLocale` is undefined (no `[locale]` route) and the vi choice lived only in localStorage. Fix: `LocaleContext` now writes a `NEXT_LOCALE` cookie on detect/switch, and `i18n/request.ts` `getRequestConfig` prefers that cookie. Verified: `GET /free` with `Cookie: NEXT_LOCALE=vi` returns Vietnamese HTML on a dev server. **Caveat:** statically-prerendered pages (marketing) bake the build-time locale — to honor per-request locale they need `export const dynamic = "force-dynamic"` OR move translated copy into client `useTranslations`. Dashboard/client pages already work via `useTranslations` + localStorage.
