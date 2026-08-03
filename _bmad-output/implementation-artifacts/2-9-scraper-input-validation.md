---
baseline_commit: 25ba542c2a3dec95b0a4020da8c129242ba748e2
baseline_branch: develop
story_key: 2-9-scraper-input-validation
status: ready-for-dev
---

# Story 2.9: Scraper API Input Validation & Error Handling

**Status:** ready-for-dev
**Epic:** 2 — Connectors
**Priority:** MEDIUM
**Requirements:** FR-6
**Architecture:** AD-19
**Dependencies:** Existing scraper routes and schemas; stories 2-6 (Indeed) and 2-7 (Walmart) are **not yet implemented** (no `app/capabilities/indeed` / `app/capabilities/walmart` directories exist — they are `ready-for-dev`). This story does NOT update their schemas; AC-6 only requires `HttpUrlStr` to be ready for reuse when 2-6/2-7 get developed.

## Story

As an API consumer,
I want clear 422 validation errors and inline feedback when I submit invalid scrape URLs,
So that I can fix my request without guessing.

## Context

### Upstream reference

SurfSense PR #1623 (`MODSetter/SurfSense#1623`, commit `84cc1c9`) already implemented the pattern we need to port:

- Added `surfsense_backend/app/capabilities/core/validation.py` with a shared `HttpUrlStr` Pydantic field type. It trims whitespace, accepts only `http`/`https` URLs, and raises a `PydanticCustomError` with the message `must be a valid http(s) URL`.
- Replaced `list[str]` URL fields with `list[HttpUrlStr]` in every scraper schema (`amazon`, `walmart`, `google_maps` + reviews, `indeed`, `reddit`, `tiktok` + comments, `youtube` + comments, `web/crawl`).
- Updated the FastAPI `RequestValidationError` handler in `app.py` to emit `error.fields`, each item carrying `{ "loc": [...], "msg": "..." }`, and improved the human-readable summary message.
- Fixed a YouTube host-spoofing bug in `url_resolver.py`: non-YouTube hosts with YouTube-shaped paths (e.g. `https://evil.com/@handle`) are now rejected by requiring `hostname in _YOUTUBE_HOSTS` before classifying channel/playlist/search pages.
- Frontend: added `AppError.fields`, extracted `fields` in `base-api.service.ts`, mapped 422 field errors to `SchemaForm` inline in `playground-runner.tsx`, added client-side per-platform URL warnings in `url-hints.ts`, and added `field-errors.ts` to convert `loc` paths to top-level field names.

### Nowing current state

- `nowing_backend/app/capabilities/*/schemas.py` URL fields are still `list[str]`. No shared `HttpUrlStr` exists.
- `nowing_backend/app/app.py` `_validation_error_handler` (lines 226-238) returns a 422 with a flat, human-readable `message` but **no `error.fields` array**.
- `_build_error_response` (lines 94-117) does **not accept a `fields` argument**.
- `nowing_backend/app/proprietary/platforms/youtube/url_resolver.py` has the same pre-1623 host-spoofing issue: it classifies by path (`/@handle`, `/shorts/...`, `/playlist?list=...`) without first validating the hostname.
- `nowing_web/lib/error.ts` `AppError` does **not carry `fields`**.
- `nowing_web/lib/apis/base-api.service.ts` parses `error.message`, `code`, `request_id`, `report_url` but **does not extract `fields`**.
- `nowing_web/app/dashboard/[workspace_id]/playground/components/schema-form.tsx` already supports a `fieldErrors?: Record<string, string>` prop (lines 27-35, 149-183), but `playground-runner.tsx` never passes it.
- `nowing_web/lib/url.ts` has a `tryGetHostname` helper, but the playground does not use it.

The dependency `validators` is already installed and used by `nowing_backend/app/utils/validators.py` (`validate_url`).

## Acceptance Criteria

1. **Shared backend URL validator**
   - **Given** any scraper input schema with a URL list, **When** a malformed or non-http(s) URL is provided, **Then** Pydantic raises a validation error and the URL is rejected before the scraper runs.
   - **And** the validator lives in a single shared module (`app/capabilities/core/validation.py`) as `HttpUrlStr`, reused by every scraper schema.

2. **Structured 422 field errors**
   - **Given** an invalid or unsupported URL for any scraper, **When** I submit, **Then** the response is `422` with `error.code = "VALIDATION_ERROR"` and `error.fields` as an array of `{ "loc": [...], "msg": "..." }` objects.
   - **And** the top-level `error.message` is human-readable and does not leak the raw `body` path prefix.

3. **Inline playground feedback**
   - **Given** the playground UI, **When** a 422 occurs, **Then** the offending fields show a red border and an inline error message.
   - **And** a toast is shown for global failures that cannot be attached to a specific field.
   - **And** if the error is inside the collapsed "Advanced" section, that section is auto-expanded and the first invalid field is focused.

4. **Per-platform URL hints (optional UX improvement)**
   - **Given** a platform playground form, **When** a URL line does not match the expected platform host, **Then** a non-blocking warning is shown before the run is submitted.

5. **YouTube host-spoofing guard**
   - **Given** a well-formed non-YouTube URL with a YouTube-shaped path, **When** it is resolved, **Then** `resolve_url` returns `None` instead of misclassifying it as a channel / playlist / search / hashtag.

6. **Future-scrapers ready**
   - **Given** new scrapers (Indeed, Walmart, or any future capability), **When** their schemas declare a `list[HttpUrlStr]` field, **Then** they receive URL validation, 422 field errors, and playground URL hints automatically.

## Tasks / Subtasks

### Backend

- [x] Create `nowing_backend/app/capabilities/core/validation.py`
  - [x] Define `HttpUrlStr = Annotated[str, AfterValidator(_validate_http_url)]`.
  - [x] `_validate_http_url` trims whitespace, uses `validators.url(url)` and `urlsplit(url).scheme.lower() in {"http", "https"}`.
  - [x] Raise `PydanticCustomError("http_url", "must be a valid http(s) URL")` on failure.
  - [x] Add `nowing_backend/tests/unit/capabilities/core/test_validation.py`.

- [x] Update `nowing_backend/app/app.py`
  - [x] Extend `_build_error_response` with an optional `fields: list[dict[str, Any]] | None = None` argument and include `error["fields"]` when present.
  - [x] Rewrite `_validation_error_handler` to build `fields` as `[{ "loc": [...], "msg": "..." }]` and pass them to `_build_error_response`.
  - [x] Drop the `"body"` root from `error.message` summaries.
  - [x] Update `nowing_backend/tests/unit/test_error_contract.py` for new `error.fields` assertions.

- [x] Update scraper input schemas to use `HttpUrlStr`
  - [x] `nowing_backend/app/capabilities/amazon/scrape/schemas.py` (`urls`)
  - [x] `nowing_backend/app/capabilities/google_maps/scrape/schemas.py` (`urls`)
  - [x] `nowing_backend/app/capabilities/google_maps/reviews/schemas.py` (`urls`)
  - [x] `nowing_backend/app/capabilities/reddit/scrape/schemas.py` (`urls`)
  - [x] `nowing_backend/app/capabilities/tiktok/scrape/schemas.py` (`urls`)
  - [x] `nowing_backend/app/capabilities/tiktok/comments/schemas.py` (`video_urls`)
  - [x] `nowing_backend/app/capabilities/youtube/scrape/schemas.py` (`urls`)
  - [x] `nowing_backend/app/capabilities/youtube/comments/schemas.py` (`urls`)
  - [x] `nowing_backend/app/capabilities/web/crawl/schemas.py` (`startUrls`)
  - [x] ~~`nowing_backend/app/capabilities/instagram/scrape/schemas.py` and `details/schemas.py`~~ — **DECISION (2026-08-03, red-phase): instagram KHÔNG switch** — `urls` field chấp nhận bare profile IDs (contract documented), upstream #1623 cố ý loại instagram, AC-4 xác nhận bare handles hợp lệ. `HttpUrlStr` chỉ áp cho field thuần URL.
  - [x] Keep `google_search/scrape` unchanged (it uses search queries, not URLs) unless it has a URL field.

- [x] Fix YouTube host-spoofing
  - [x] Define `_YOUTUBE_HOSTS = frozenset({"www.youtube.com", "youtube.com", "m.youtube.com"})` in `nowing_backend/app/proprietary/platforms/youtube/url_resolver.py`.
  - [x] In `resolve_url`, require `hostname in _YOUTUBE_HOSTS` before classifying playlist / search / hashtag / channel pages.
  - [x] Reuse `get_youtube_video_id` for shorts so youtu.be short links still work.
  - [x] Update `nowing_backend/tests/unit/platforms/youtube/test_parsers.py` with host-spoof test cases.

### Frontend

- [x] `nowing_web/lib/error.ts`
  - [x] Add `ValidationFieldError` interface `{ loc: string[]; msg: string }`.
  - [x] Add `fields?: ValidationFieldError[]` to `AppError`.
  - [x] **Do NOT create a new `ValidationError` class** — it already exists in `lib/error.ts:19-23` (subclasses `AppError` with code `VALIDATION_ERROR`). Only extend the `AppError` constructor.

- [x] `nowing_web/lib/apis/base-api.service.ts`
  - [x] Extract `envelope?.fields`.
  - [x] For 422, throw `ValidationError` with `fields` (class already exists — reuse it).
  - [x] **Note:** the comment at `base-api.service.ts:158` ("Extract structured fields from new envelope or legacy shape") is legacy — fields are **not** currently extracted. Do not mistake it for completed work.
  - [x] Avoid logging/capturing 4xx client errors in PostHog.

- [x] `nowing_web/lib/playground/field-errors.ts` (new)
  - [x] `fieldErrorsFromError(error): Record<string, string>` — map `loc` array to top-level field name, keep the first failure per field.

- [x] `nowing_web/lib/playground/url-hints.ts` (new, optional)
  - [x] `urlFieldWarning(platform, fieldName, value): string | undefined` for known URL fields and platforms.
  - [x] `urlFieldWarnings(platform, values): Record<string, string>`.
  - [x] Skip Instagram `urls` (accepts bare handles) and unknown fields.

- [x] `nowing_web/app/dashboard/[workspace_id]/playground/components/playground-runner.tsx`
  - [x] Add `fieldErrors` state, clear on change / on run start.
  - [x] On `run.status === "error"`, call `fieldErrorsFromError(run.error)`, set state, and suppress the toast when errors are displayed inline.
  - [x] Pass `fieldErrors` and optional `fieldWarnings` to `SchemaForm`.

- [x] `nowing_web/app/dashboard/[workspace_id]/playground/components/schema-form.tsx`
  - [x] Add `fieldWarnings?: Record<string, string>` prop (amber text, shown when no error).
  - [x] Auto-expand Advanced and focus the first field with an error.

### Tests

- [x] `nowing_backend/tests/unit/capabilities/core/test_validation.py` — accept/reject URL cases.
- [x] `nowing_backend/tests/unit/test_error_contract.py` — 422 `error.fields` shape.
- [x] `nowing_backend/tests/unit/platforms/youtube/test_parsers.py` — host-spoof guard.
- [x] Per-scraper `test_schemas.py` files — add malformed URL cases.
- [x] `nowing_web/lib/playground/field-errors.selfcheck.ts` — mapping tests (the `.selfcheck.ts` convention is established: `code-snippets`, `csv`, `json-schema` already follow it).
- [x] `nowing_web/lib/playground/url-hints.selfcheck.ts` — warning tests.

## Dev Notes

- **Port, do not blindly copy.** The SurfSense stack is the same (FastAPI + Pydantic v2, Next.js + TypeScript), but Nowing uses `validators` (pyvalidators) and has its own `app/utils/validators.py`. The Pydantic `AfterValidator` pattern is the same.
- The `HttpUrlStr` validator intentionally does **not** normalize URLs (keeps trailing slashes, query strings, fragments). It only trims whitespace. This matches upstream behavior and prevents changing the URL that downstream scrapers expect.
- Do **not** over-engineer per-platform URL rules in Pydantic. Platform-specific host matching belongs in the client-side `url-hints.ts` (warnings) and in the platform `url_resolver.py` / scraper logic. The backend `HttpUrlStr` is a strict boundary rule.
- The `PlaygroundRunner` `fieldErrors` state should reset when the user edits a field or starts a new run. This prevents stale red borders.
- The `nowing_mcp` server calls the same REST routes, so it will automatically receive 422 field errors through `base-api.service` / `AppError`. No separate MCP validation code is needed unless the MCP client wants to render field errors (out of scope for this story).

## Verification

- [x] Backend unit tests pass:
  ```bash
  cd nowing_backend
  pytest tests/unit/capabilities/core/test_validation.py tests/unit/test_error_contract.py tests/unit/platforms/youtube/test_parsers.py -q
  pytest tests/unit/capabilities/*/test_schemas.py -q
  ```
  Result: 3979 passed, 7 skipped (full suite).
- [x] Web typecheck and lint:
  ```bash
  cd nowing_web
  pnpm tsc --noEmit
  pnpm exec biome check --max-diagnostics=500 \
    lib/error.ts \
    lib/apis/base-api.service.ts \
    lib/playground/field-errors.ts \
    lib/playground/url-hints.ts \
    app/dashboard/\[workspace_id\]/playground/components/playground-runner.tsx \
    app/dashboard/\[workspace_id\]/playground/components/schema-form.tsx
  ```
  Result: `tsc --noEmit` clean (0 errors); biome 8 files clean.
- [x] Playground self-checks pass (`.selfcheck.ts` convention):
  ```bash
  cd nowing_web
  npx tsx lib/playground/field-errors.selfcheck.ts
  npx tsx lib/playground/url-hints.selfcheck.ts
  ```
  Result: both print "all assertions passed".

## References

- Upstream PR: `MODSetter/SurfSense#1623`
- Upstream commit: `84cc1c9b6953adbe9cc0c15f7b55a920540d9d73`
- `nowing_backend/app/app.py` (`_build_error_response`, `_validation_error_handler`)
- `nowing_backend/app/utils/validators.py` (`validate_url`)
- `nowing_backend/app/capabilities/core/access/rest.py` (`build_capabilities_router`)
- `nowing_backend/app/capabilities/*/schemas.py`
- `nowing_backend/app/proprietary/platforms/youtube/url_resolver.py`
- `nowing_web/lib/error.ts`
- `nowing_web/lib/apis/base-api.service.ts`
- `nowing_web/lib/playground/json-schema.ts`
- `nowing_web/lib/url.ts`
- `nowing_web/app/dashboard/[workspace_id]/playground/components/playground-runner.tsx`
- `nowing_web/app/dashboard/[workspace_id]/playground/components/schema-form.tsx`

## Challenge Log (grill-me)

### Q1 — Already implemented?
- No `HttpUrlStr`/`validation.py` exists — confirmed not implemented.
- `app/utils/validators.py:434` already has `validate_url()` using `validators.url` (pyvalidators) — reuse its approach (trim + `validators.url` + scheme check) inside `HttpUrlStr`; do not invent a new validation library.
- **Web overlap found:** `nowing_web/lib/playground/platform-overrides/amazon.tsx` already establishes a per-platform override pattern (`getAmazonFieldOptions`, `AmazonMarketplaceHint`, `hasAmazonFranceValue`) wired through `playground-runner.tsx`. New `url-hints.ts` should follow the same file location/structure (or live under `lib/playground/platform-overrides/`) to avoid two parallel hint systems. `AmazonMarketplaceHint` is a static alert; `url-hints` adds per-field warnings — complementary, not duplicate.

### Q2 — Simpler alternative?
- Pydantic built-in `AnyHttpUrl`/`HttpUrl` is a candidate, but the story's custom `AfterValidator` is justified: AC requires whitespace trim + the exact upstream message `must be a valid http(s) URL`. Keep `AfterValidator` + `validators.url` (already a project dependency). No HALT.
- Reuse `lib/url.ts:tryGetHostname` inside `url-hints.ts` for host matching (already referenced in story references).

### Q3 — Edge cases spec misses (Pattern 3)
- [ ] Boundary: URL length cap — no max_length on URL strings anywhere in the story; `validators.url` has undocumented limits. Add a generous `max_length` (e.g. 2048) or test very long URLs explicitly.
- [ ] Boundary: Amazon EU TLDs (`amazon.de`/`amazon.fr`/`amazon.co.uk`) must pass `HttpUrlStr` — story 2.8 downstream depends on it; add explicit accept tests.
- [ ] Null/empty: `[]` empty list (valid) vs `[""]` vs `["   "]` (whitespace-only → must reject after trim); per-item trim behavior.
- [ ] Null/empty: `http://localhost:8080` and IP hosts — decide pass/fail explicitly (validators.url may require a TLD).
- [ ] Concurrent/UX: field name mismatch — `loc` paths like `["body","urls",0]` map to top-level `urls`, but `video_urls`/`startUrls` must map too; if `loc` doesn't match any form field, fall back to toast (AC-3 covers global failures — make the "unmappable field" case explicit).

### Q4 — Failure modes unspecified (Pattern 2, 4)
- [ ] `validators.url` returns False for odd-but-harmless inputs (empty host, scheme-only, `https://`) → PydanticCustomError message must still read `must be a valid http(s) URL` (consistent, no raw library jargon).
- [ ] Backend accepts `https://example.com` in `reddit.scrape` (valid http(s) but wrong platform host) — HttpUrlStr does NOT platform-check (by design, story line: strict boundary only). Confirm scraper-level behavior is out of scope for this story and platform mismatch surfaces as client-side `url-hints` warning (AC-4), not a backend error.
- [ ] 422 arrives without `error.fields` (legacy detail-only envelope from an older proxy/gateway) → `base-api.service` must not crash; throws plain `ValidationError` without fields → toast path (no inline).
- [ ] Frontend mapping loss: `fieldErrorsFromError` keeps only first failure per field — acceptable; multiple invalid fields still each get one error (verify with a 3-invalid-URLs request in self-check).

### Triage
- No Critical findings → **Clean — proceed** to 4.4 test-first-atdd.
- Actionable items: add Q3/Q4 cases to the test skeleton (HttpUrlStr max_length + EU TLD + whitespace tests; fieldErrors unmappable-loc fallback test; no-fields 422 test).
