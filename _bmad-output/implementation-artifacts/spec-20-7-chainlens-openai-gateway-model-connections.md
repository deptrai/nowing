---
title: 'Story 20.7: ChainLens OpenAI Gateway Model Connections'
type: 'feature'
created: '2026-09-21'
status: 'in-review'
review_loop_iteration: 1
baseline_revision: 5fd99c78983ca1f978bf27d3cc155af4aae7f2ba
followup_review_recommended: false
context:
  - '_bmad-output/implementation-artifacts/epic-20-context.md'
  - '_bmad-output/planning-artifacts/ux-spec-epic20-chainlens-agent-tools-2026-09-20.md'
warnings: []
deferred: []
---

<intent-contract>

## Intent

**Problem:** Nowing users (superadmin/workspace owner) muốn dùng ChainLens grounded models (web-search-augmented LLM) trong chat, nhưng ChainLens không xuất hiện trong provider picker — chỉ có generic `openai_compatible` với manual base_url entry. Điều này giấu khả năng web-grounded và buộc user phải biết endpoint URL `https://research-api.chainlens.net/v1`.

**Approach:** Đăng ký `chainlens` làm preset provider trong backend `REGISTRY` (reuse `OPENAI_COMPATIBLE` transport, `default_base_url=https://research-api.chainlens.net/v1`, bearer auth, `openai_models` discovery). Frontend thêm display metadata (`name: "ChainLens"`, `subtitle: "Web-Grounded"`, `iconKey: "globe"`) + `PROVIDER_ORDER` entry + globe icon + i18n keys `chainlens.model_group`/`model_tooltip`. Zero backend schema change.

## Boundaries & Constraints

**Always:**
- Backend: append entry `chainlens` vào `REGISTRY` trong `app/services/provider_registry.py` với `Transport.OPENAI_COMPATIBLE`, `litellm_prefix="openai"`, `discovery="openai_models"`, `default_base_url="https://research-api.chainlens.net/v1"`, `base_url_required=False`, `auth_style="bearer"`, `display_name="ChainLens"`.
- Frontend `PROVIDER_DISPLAY` (trong `provider-metadata.tsx`): thêm `chainlens: { name: "ChainLens", subtitle: "Web-Grounded", iconKey: "globe", defaultBaseUrl: "https://research-api.chainlens.net/v1" }`.
- Frontend `PROVIDER_ORDER`: chèn `"chainlens"` SAU `"openrouter"` và TRƯỚC `"requesty"` (grouping OpenAI-compatible providers).
- Frontend icon: extend `getProviderIcon` trong `lib/provider-icons.tsx` — thêm `case "CHAINLENS": return <Globe className={cn(className)} .../>` (import `Globe` từ `lucide-react`).
- i18n: thêm keys `chainlens.model_group` (`"ChainLens (Web-Grounded)"`) và `chainlens.model_tooltip` (vi + en) vào `messages/vi.json` + `messages/en.json` dưới namespace `chainlens`.
- Model picker UI: khi provider === "chainlens", render model names trong group header `t("chainlens.model_group")` với globe icon + tooltip `t("chainlens.model_tooltip")` — dùng pattern có sẵn cho provider groups.
- Connection test: `GET {base_url}/models` phải return HTTP 200 (ChainLens sẽ expose `claude-sonnet-4-6`, `haiku-4.5`, `deepseek-v4-pro` — không hardcode, để discovery fetch).

**Block If:**
- ChainLens chưa expose `GET /v1/models` (upstream endpoint chưa sẵn sàng) → HALT `blocked`, condition `upstream /v1/models not live` — không ship UI cho provider mà không test được.
- Phát hiện provider key `chainlens` đã tồn tại trong `REGISTRY` (conflict) → HALT `blocked`, condition `provider key collision`.

**Never:**
- Không thêm Alembic migration (zero schema change — chỉ registry entry).
- Không hardcode model list trong backend (để `discovery="openai_models"` tự fetch từ `GET /v1/models`).
- Không tạo custom LiteLLM transport (reuse `OPENAI_COMPATIBLE` — ChainLens tuân OpenAI SSE spec).
- Không modify `openai_compatible` existing entry (giữ nguyên cho generic providers).
- Không skip i18n — Vietnamese-first rule.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| HAPPY_PATH | Admin chọn "ChainLens" trong provider dropdown | Form hiện `base_url=https://research-api.chainlens.net/v1` (prefilled), auth field = bearer token | — |
| DISCOVERY | Connection đã tạo, click "Discover models" | `GET https://research-api.chainlens.net/v1/models` trả `{data: [{id: "claude-sonnet-4-6"}, ...]}` → list models | Nếu 404/5xx → toast error (existing pattern) |
| MODEL_PICKER | Workspace model picker mở | ChainLens models xuất hiện dưới group "ChainLens (Web-Grounded)" với globe icon + tooltip | — |
| BAD_BASE_URL | Admin sửa `base_url` thành URL khác | Form cho phép (vì `base_url_required=False`) nhưng test connection fail nếu endpoint không OpenAI-compatible | Existing validation |
| MISSING_AUTH | Không nhập bearer token | Form submit blocked (existing auth_style="bearer" validation) | Existing form validation |
| CONNECTION_TEST_FAIL | `GET /v1/models` trả 401/403/timeout | Toast "Connection failed" (existing error path) | Existing test_connection error handling |
| I18N_VI | User locale = vi | Tooltip + group header hiển thị tiếng Việt | Fallback `en` nếu key missing |
| I18N_EN | User locale = en | Tooltip + group header hiển thị English | — |

</intent-contract>

## Code Map

- `nowing_backend/app/services/provider_registry.py` — EDIT: append `"chainlens"` entry vào `REGISTRY` dict (sau `"openrouter"`, trước `"requesty"` trong dict order for consistency).
- `nowing_backend/app/routes/model_connections_routes.py` — READ-ONLY verify `list_model_providers` (`:265`) enumerate `REGISTRY` — không cần sửa (auto-expose).
- `nowing_web/components/settings/model-connections/provider-metadata.tsx` — EDIT: append `chainlens` vào `PROVIDER_ORDER` (sau `"openrouter"`) + `PROVIDER_DISPLAY` entry.
- `nowing_web/lib/provider-icons.tsx` — EDIT: import `Globe` từ `lucide-react`, thêm `case "CHAINLENS": return <Globe .../>` trong `getProviderIcon` switch.
- `nowing_web/messages/vi.json` + `messages/en.json` — EDIT: thêm `chainlens` namespace với keys `model_group` (vi: `"ChainLens (Web-Grounded)"` — giữ nguyên English theo UX spec), `model_tooltip` (vi + en đầy đủ).
- `nowing_web/messages/{es,hi,ko,pt,zh}.json` — EDIT: thêm `chainlens` namespace với English placeholder (same as en.json) để tránh missing-key fallback.
- `nowing_web/app/admin/global-model-connections/page.tsx` — READ-ONLY verify provider dropdown uses `PROVIDER_ORDER` + `providerDisplay`/`providerDefaultBaseUrl`/`providerIcon` — không cần sửa nếu pattern chuẩn.
- `nowing_web/components/new-chat/model-selector.tsx` — EDIT: `connectionLabel()` dùng `t("chainlens.model_group")` khi `provider === "chainlens"`; group header render Globe icon + `title` tooltip `t("chainlens.model_tooltip")` khi connection là chainlens.
- `nowing_web/components/settings/model-connections/model-provider-connections-panel.tsx` — READ-ONLY verify admin connections panel renders provider name — không sửa.
- `nowing_backend/tests/unit/services/test_provider_capabilities.py` — EDIT: append test case `test_chainlens_provider_registered` assert `spec_for("chainlens").default_base_url == "https://research-api.chainlens.net/v1"` + `discovery == "openai_models"`.
- `app/services/chainlens/auth.py` — READ-ONLY: ChainLens bearer auth sẽ dùng workspace's `CHAINLENS_API_KEY` từ env hoặc admin nhập manual — không đụng (existing auth flow).

## Tasks & Acceptance

**Execution:**
- `nowing_backend/app/services/provider_registry.py` — append `"chainlens"` ProviderSpec entry vào `REGISTRY` — expose ChainLens preset.
- `nowing_backend/tests/unit/services/test_provider_capabilities.py` — add test `test_chainlens_provider_registered` — cover REGISTRY entry.
- `nowing_web/components/settings/model-connections/provider-metadata.tsx` — append `chainlens` vào `PROVIDER_ORDER` + `PROVIDER_DISPLAY` — frontend metadata.
- `nowing_web/lib/provider-icons.tsx` — add `case "CHAINLENS"` return Globe icon — provider icon.
- `nowing_web/messages/vi.json` — add `chainlens.model_group` + `chainlens.model_tooltip` — i18n vi.
- `nowing_web/messages/en.json` — add `chainlens.model_group` + `chainlens.model_tooltip` — i18n en.
- `nowing_web/messages/{es,hi,ko,pt,zh}.json` — add `chainlens` namespace với English placeholder — cover 5 locales còn lại.
- `nowing_web/components/new-chat/model-selector.tsx` — `connectionLabel()` returns `t("chainlens.model_group")` for chainlens connections; group header renders Globe icon + `title={t("chainlens.model_tooltip")}` when group is chainlens — model picker surface.
- `nowing_backend/tests/unit/services/test_provider_capabilities.py` — extend `test_chainlens_listed_in_registry` hoặc add test call `list_model_providers` route để assert chainlens appear trong serialized response — cover endpoint exposure (không chỉ dict).

**Acceptance Criteria:**
- Given admin mở "Add connection" trên `/admin/global-model-connections`, when chọn provider dropdown, then "ChainLens" xuất hiện với globe icon + subtitle "Web-Grounded" (AC-1).
- Given admin chọn ChainLens, when form render, then `base_url` prefilled `https://research-api.chainlens.net/v1` (AC-1).
- Given admin nhập bearer token + click "Test connection", when `GET /v1/models` được gọi, then trả HTTP 200 + list models (AC-3) — nếu upstream chưa live thì test case skip với note.
- Given workspace model picker, when models được fetch, then ChainLens models hiển thị trong group "ChainLens (Web-Grounded)" với globe icon + tooltip latency hint (AC-4).
- Given user locale = vi, when hover ChainLens group, then tooltip hiển thị tiếng Việt (AC-4 + i18n).
- Given backend `list_model_providers` endpoint, when GET, then response bao gồm `{provider: "chainlens", transport: "OPENAI_COMPATIBLE", default_base_url: "https://research-api.chainlens.net/v1", discovery: "openai_models"}` (AC-2 implicit — registry exposure).

## Spec Change Log

### 2026-09-21 — Review pass 1

**Trigger finding:** Model picker UI không được update để render "ChainLens (Web-Grounded)" group header + latency tooltip — i18n keys `chainlens.model_group`/`model_tooltip` được thêm nhưng không có code nào consume → AC4 unimplemented.

**What amended:** Code Map + Tasks thêm task cho `nowing_web/components/new-chat/model-selector.tsx` — group label dùng `t("chainlens.model_group")` khi provider === "chainlens" (fallback "ChainLens"), group header render globe icon + tooltip `t("chainlens.model_tooltip")` khi connection là chainlens. Thêm task thêm `chainlens` keys vào 5 locales còn lại (es/hi/ko/pt/zh — English placeholder). Thêm task cho endpoint test `list_model_providers` trực tiếp (không chỉ dict check).

**Known-bad state avoided:** Ship i18n keys không ai dùng (dead strings), AC4 fail ở review.

**KEEP:** Backend `provider_registry.py` entry + `provider-metadata.tsx` PROVIDER_ORDER/DISPLAY + `provider-icons.tsx` Globe case — đúng pattern, không đổi.

## Review Triage Log

### 2026-09-21 — Review pass 1
- intent_gap: 0
- bad_spec: 2: (high 1, medium 1)
- patch: 3: (low 3)
- defer: 3
- reject: 4
- addressed_findings:
  - `[high]` `[bad_spec]` Model picker UI không consume `chainlens.model_group`/`model_tooltip` — spec amended với task cho `model-selector.tsx`; code updated.
  - `[medium]` `[bad_spec]` Test chỉ check REGISTRY dict không check `/model-providers` endpoint — spec amended; `test_chainlens_serialized_by_list_model_providers` added.
  - `[low]` `[patch]` Missing `chainlens` keys trong 5 locales (es/hi/ko/pt/zh) — added English placeholder to all 5 locale files.
  - `[low]` `[patch]` `getProviderIcon` cho chainlens đã có — verified via `provider-metadata.tsx` `iconKey: "chainlens"` + `provider-icons.tsx` case "CHAINLENS".
  - `[low]` `[patch]` Group label hardcode `providerDisplay().name` không có "(Web-Grounded)" — model-selector render `t("chainlens.model_group")` thay thế khi provider === "chainlens".

## Design Notes

**Backend `list_model_providers` tự động expose REGISTRY entries** — không cần modify route code, chỉ thêm dict entry là đủ.

**Frontend provider dropdown cũng tự render từ `PROVIDER_ORDER` + `PROVIDER_DISPLAY`** — thêm metadata là đủ, không cần custom form (reuse `openai_compatible` connect form pattern — bearer token field only).

**ChainLens upstream phải expose `GET /v1/models`** — nếu chưa live thì discovery fail nhưng vẫn ship được (admin nhập manual model IDs như `openai_compatible_raw` flow).

**Tooltip latency hint (~3–6s first token)** là UX promise — không hardcode trong code, chỉ i18n string.

## Verification

**Commands:**
- `cd nowing_backend && python -c "from app.services.provider_registry import spec_for; s = spec_for('chainlens'); print(s.transport, s.default_base_url, s.discovery)"` — expected: `Transport.OPENAI_COMPATIBLE https://research-api.chainlens.net/v1 openai_models`
- `cd nowing_backend && pytest tests/unit/services/test_provider_capabilities.py -k chainlens -q` — expected: pass
- `cd nowing_web && pnpm tsc --noEmit` — expected: no type errors
- `cd nowing_web && pnpm exec biome check components/settings/model-connections/provider-metadata.tsx lib/provider-icons.tsx messages/vi.json messages/en.json` — expected: clean

**Manual checks:**
- Navigate to `/admin/global-model-connections` → "Add connection" → provider dropdown shows "ChainLens" with globe icon.
- Select ChainLens → `base_url` prefilled `https://research-api.chainlens.net/v1`.
- If ChainLens upstream live: paste bearer token → "Test connection" → success + models discovered.
- Open workspace model picker → verify "ChainLens (Web-Grounded)" group header with globe icon.
- Switch locale to vi → hover ChainLens group → tooltip in Vietnamese.
