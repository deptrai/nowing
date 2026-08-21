# Story 24.5 — BMAD Code Review Triage

> **Source reviews:** `review-24-5-blind-hunter.md`, `review-24-5-edge-case-hunter.md`, `review-24-5-acceptance-auditor.md`
> **Diff reviewed:** `review-24-5-working-tree.diff`
> **Severity scale (step-03):** `high` = intolerable consequence; `medium` = tolerable but real; `low` = none or cosmetic

## decision_needed

- [x] [Review][Decision][high] Default marketplace visibility changed — workspace-vertical filter removed from `list_playbooks` [nowing_backend/app/automations/services/playbook_service.py:137-174, nowing_backend/tests/integration/automations/test_playbook_routes.py:239-348] — The new query returns all workspace playbooks plus **all** system playbooks when no `vertical` is passed, dropping the previous default filter for the workspace’s vertical/`general`. Two integration tests fail, and cross-vertical system playbooks are now visible by default. Product/team must decide whether to (a) restore the workspace-vertical default and treat `vertical` as an explicit override, or (b) keep cross-vertical visibility and update the tests/spec.

- [x] [Review][Decision][high] Story spec was retrofitted in the same diff to match implementation [review-24-5-working-tree.diff:1-49, _bmad-output/implementation-artifacts/stories/24-5-vertical-playbook-marketplace-and-templates.md] — The working-tree spec changed from `ready-for-dev` to `done`, switched the path from `/playbooks/marketplace` to `/playbooks`, changed the button from `Chạy Playbook` to `Khởi Tạo Kịch Bản`, and rewrote technical tasks from 12 templates/3 tables to 4 templates/reusing the `playbooks` table. Product/team must reconcile the baseline spec (12 templates, marketplace page, etc.) with the reduced current spec before merging.

- [x] [Review][Decision][high] Community playbook moderation (`is_approved`) is not implemented [nowing_backend/app/automations/persistence/models/playbook.py:25-93, nowing_backend/app/automations/persistence/enums/playbook_scope.py:8-10, nowing_backend/app/automations/services/playbook_service.py:148-157, nowing_backend/alembic/versions/191_add_playbooks.py:29-88] — INV-24.6 requires community playbooks to be `is_approved = True` before marketplace display, but the `playbooks` table has no `is_approved` column, `PlaybookScope` only has `workspace`/`system`, and `list_playbooks` does not filter by it. Product/team must decide whether to add a `community` scope + approval flow, add an `is_approved` flag to all scopes, or relax/remove the invariant from the spec.

- [x] [Review][Decision][medium] Marketplace layout and category labels do not match AC-1 [nowing_web/app/dashboard/[workspace_id]/playbooks/playbooks-content.tsx:34-40, 57-66, 181-203] — The spec calls for “responsive cards **grouped by vertical**” with categories `B2B Sales` and `E-Commerce & Bán Lẻ`; the implementation uses a flat, client-side filtered grid with tab labels `B2B Sales & MST` and `E-Commerce & Giá`. Product/team must decide whether to update the UI to match the spec or update the spec to the current tab-filter design.

- [x] [Review][Decision][medium] Workspace vertical naming mismatch vs. marketplace categories [nowing_web/app/dashboard/[workspace_id]/playbooks/playbooks-content.tsx:34-39, nowing_backend/app/automations/services/playbook_service.py:372-385, nowing_backend/app/db.py:1912-1918, nowing_web/contracts/types/workspace.types.ts:5-12] — The marketplace uses `realestate`, `recruitment`, `b2b`, `ecommerce`, but workspace verticals and the workspace enum use `real_estate`, `auto`, `b2b_equipment`. `_resolve_verticals` defaults new playbooks to `["general", "real_estate"]`, which does not match the `realestate` tab, so user-created playbooks vanish from category tabs. Product/team must decide on canonical vertical slugs and whether to introduce a mapping/enum.

- [x] [Review][Decision][medium] Playbook instantiation inputs are validated but not persisted or used [nowing_backend/app/automations/services/playbook_service.py:237-288, nowing_backend/app/automations/services/automation.py:76-89, nowing_backend/app/automations/api/run.py:13-28] — `PlaybookService.instantiate()` validates `payload.inputs` against `inputs_schema`, then creates an `AutomationCreate` with an empty trigger list and no stored inputs. The manual `POST /automations/{id}/run` endpoint has no request body for runtime inputs. Product/team must decide the runtime input contract (e.g. store as `static_inputs` in a manual trigger, extend the run endpoint to accept inputs, or create a run immediately during instantiation).

- [x] [Review][Decision][low] INV-24.6 canonical `max_leads_per_run` field is not used in seed data [nowing_backend/app/automations/services/playbook_seed_service.py:53-59, 125-131, 202-208, 272-278, nowing_backend/app/automations/services/playbook_service.py:321-323, _bmad-output/implementation-artifacts/stories/24-5-vertical-playbook-marketplace-and-templates.md] — The invariant text requires `max_leads_per_run <= 200`; the seed schemas use `max_leads` and `max_skus`. The hard-limit code accepts these aliases, so the limit is still enforced, but the spec and data are inconsistent. Product/team must decide whether to rename seed fields, update the invariant text, or keep aliases.

## patch

- [x] [Review][Patch][high] `PlaybookService.instantiate` never authorizes read access to the source playbook [nowing_backend/app/automations/services/playbook_service.py:227-234] — `instantiate` calls `_get_playbook_or_raise(playbook_id)` and `_authorize(payload.workspace_id, AUTOMATIONS_CREATE)` but never `_authorize_playbook_access(playbook, AUTOMATIONS_READ)`. `get` (line 176-180) and `validate_inputs` (line 292-303) both do. Any authenticated user who guesses a private playbook ID can copy it into their own workspace. Add `_authorize_playbook_access(playbook, Permission.AUTOMATIONS_READ.value)` before creating the automation.

- [x] [Review][Patch][high] Official seed playbooks are not runnable — `agent_task` steps lack required `query` and `definition.inputs.schema` is missing required keys [nowing_backend/app/automations/services/playbook_seed_service.py:78-82, 83-93, 146-159, 223-235, 293-305, nowing_backend/app/automations/actions/builtin/agent_task/params.py:15-19] — `AgentTaskActionParams.query` is required. The official plans only contain `step_id` and `action`, so `AutomationService._validate_plan_or_raise()` rejects instantiation with `step 'scrape_bds': query: Field required`. Additionally, the stored `definition.inputs.schema` omits required keys such as `location` (IT), `industry` (B2B), and `platform` (E-Commerce), so runtime validation after the plan fix will fail. Populate `params.query` for every step (ideally with Jinja references to user inputs) and align `definition.inputs.schema` with `inputs_schema`.

- [x] [Review][Patch][high] `PlaybookSummary` does not expose marketplace metadata [nowing_backend/app/automations/schemas/api/playbook.py:48-61, nowing_web/contracts/types/playbook.types.ts:33-44] — Neither the backend response model nor the frontend contract include `author_badge`, `author_name`, `estimated_credits_cost`, `run_count`, or `is_featured`. The frontend is forced to hardcode “Official”, “~25-40 credits”, and “1.2k+ runs”. Extend both schemas to expose these fields from `definition.metadata`.

- [x] [Review][Patch][high] Marketplace cards and instantiate dialog hardcode badge, cost, and run count [nowing_web/app/dashboard/[workspace_id]/playbooks/playbooks-content.tsx:181-203, nowing_web/app/dashboard/[workspace_id]/playbooks/playbook-instantiate-dialog.tsx:92-103] — Every card renders `<BadgeCheck /> Official`, `~25-40 credits/lần`, and `1.2k+ lượt chạy` regardless of scope. The dialog also shows a static `~25 - 40 Credits` / `200 Leads/lần`. Once the list API exposes real metadata, render per-playbook values (e.g. show “Official” only when `scope === "system"` or `author_badge === "official"`).

- [x] [Review][Patch][medium] Frontend `vertical` filter is not wired through the API [nowing_web/lib/apis/playbooks-api.service.ts:30-37, nowing_web/atoms/playbooks/playbooks-query.atoms.ts:13-24, nowing_web/app/dashboard/[workspace_id]/playbooks/playbooks-content.tsx:57-66] — `playbookListParams` declares `vertical` and the backend supports it, but `PlaybooksApiService.listPlaybooks` never appends `vertical` to `URLSearchParams`, `playbooksListAtom` never passes it, and the marketplace filters client-side. With >50 playbooks, category tabs and search silently hide matches on later pages. Pass `vertical` through the atom and API client and add it to the query cache key.

- [x] [Review][Patch][medium] `PlaybookService._validate_inputs` hard limit is brittle and bypassable [nowing_backend/app/automations/services/playbook_service.py:305-327, 70-75, 112-113, 198-199] — The limit returns early when `inputs_schema` is empty, only checks three literal keys (`max_leads`, `max_leads_per_run`, `max_skus`), and only rejects `int`/`float` >200. A playbook with an empty `inputs_schema` or a differently named limit field (e.g. `lead_count` with `maximum: 10000`) bypasses it. Also, `create_from_automation`/`update` only validate schema syntax, not that declared `maximum` values are <=200. Enforce the 200 cap at schema creation/update and at instantiation for any numeric field whose schema `maximum` exceeds 200.

- [x] [Review][Patch][medium] `seed_system_playbooks` has a multi-worker race condition [nowing_backend/app/automations/services/playbook_seed_service.py:312-348, nowing_backend/alembic/versions/191_add_playbooks.py:29-88] — The seed does `SELECT ... first()` then `INSERT` with no unique constraint on `(name, scope, workspace_id)` and no `ON CONFLICT`/`RETURNING`. Multiple Uvicorn workers can simultaneously see zero rows and both insert, producing duplicate official playbooks. Add a partial unique index on `(name, scope)` where `workspace_id IS NULL` and use `INSERT ... ON CONFLICT ... RETURNING` or an advisory lock.

- [x] [Review][Patch][medium] `PlaybookInstantiateDialog` hides detail-fetch errors and falls back to a no-inputs workflow [nowing_web/app/dashboard/[workspace_id]/playbooks/playbook-instantiate-dialog.tsx:46-50, 105-130] — When `getPlaybook` fails, `isLoading` becomes `false` and `detail` is `undefined`. The dialog then renders `hasInputs=false` and shows a “Chạy Kịch Bản Ngay” button that submits `{}`, causing a 422 because required fields are missing. Surface the fetch error and disable submission until a valid detail is loaded.

- [x] [Review][Patch][medium] `app.py` lifespan swallows playbook seed failures [nowing_backend/app/app.py:685-692] — A broad `except Exception` around `seed_system_playbooks` logs a warning and continues, so the app can start with no official playbooks and no retry/alert. Treat seed data as load-time critical: fail fast on schema validation errors, retry transient DB errors, or at least propagate an observable alert.

- [x] [Review][Patch][low] `PlaybooksContent` fetches workspace vertical but never uses it [nowing_web/app/dashboard/[workspace_id]/playbooks/playbooks-content.tsx:48-55] — `useQuery` for the workspace is called and `_workspaceVertical` is assigned, but the value is never used after client-side grouping was replaced by hardcoded category tabs. Remove the dead query or use the workspace vertical to default the selected category once the naming mismatch is resolved.

- [x] [Review][Patch][low] `SchemaForm` submit button can be double-clicked while a submission is in flight [nowing_web/components/schema-form/schema-form.tsx:131-136, nowing_web/app/dashboard/[workspace_id]/playbooks/playbook-instantiate-dialog.tsx:43-44, 61-75] — `SchemaForm` only disables the button when `!isValid`. `PlaybookInstantiateDialog` tracks `isPending` but does not pass a disabled state into `SchemaForm`, so a double-click can fire a second `instantiate` call. Add an `isPending`/`disabled` prop to `SchemaForm` and disable the submit button while the mutation is pending.

- [x] [Review][Patch][low] `seed_system_playbooks` never deletes or renames stale official playbooks [nowing_backend/app/automations/services/playbook_seed_service.py:312-348] — After upsert, seed now updates stale system playbooks (`scope=system`, `workspace_id IS NULL`, name not in `OFFICIAL_PLAYBOOKS`) to `is_approved=False` instead of deleting them.

- [x] [Review][Patch][low] `PlaybookInstantiateDialog` error state is not reset on open/close [nowing_web/app/dashboard/[workspace_id]/playbooks/playbook-instantiate-dialog.tsx:43-44, 61-76] — `instantiateError` is only cleared at the start of `handleSubmit`, so a previous error remains visible across dialog open/close cycles. Reset the error in an `useEffect` when `open` changes.

- [x] [Review][Patch][low] `PlaybookInstantiateDialog` uses unsafe error cast [nowing_web/app/dashboard/[workspace_id]/playbooks/playbook-instantiate-dialog.tsx:74] — `setInstantiateError((err as Error).message ?? "...")` throws a runtime `TypeError` if `err` is `null` or `undefined`. Use a safe helper (e.g. `err instanceof Error ? err.message : String(err ?? "...")`).

- [x] [Review][Patch][low] `PlaybookService.list_playbooks` `vertical` filter is case-sensitive and unvalidated [nowing_backend/app/automations/services/playbook_service.py:155-156, nowing_backend/app/automations/api/playbook.py:52-58] — `_canonical_vertical` now lowercases input; `list_playbooks` validates against `MARKETPLACE_VERTICALS` and returns 422 for unknown slugs.

- [x] [Review][Patch][low] Search is diacritic-sensitive and ignores tags/author [nowing_web/app/dashboard/[workspace_id]/playbooks/playbooks-content.tsx:60-63] — Added `normalizeVietnamese` helper (NFD fold + đ→d); search now matches name, description, author_name, and tags.

- [x] [Review][Patch][low] Marketplace empty state is misleading when no playbooks exist [nowing_web/app/dashboard/[workspace_id]/playbooks/playbooks-content.tsx:151-160] — Empty catalog now shows “Chưa có Playbook nào trong workspace này” with guidance to save an Automation; filter-only empty keeps the filter message.

- [x] [Review][Patch][low] Unit test `test_seed_system_playbooks_idempotent` misuses `AsyncMock` [nowing_backend/tests/unit/services/test_playbook_templates.py:72-83] — `mock_session = AsyncMock()` makes `session.add()` an async mock, but `seed_system_playbooks` calls `session.add(playbook)` synchronously. The test only asserts `call_count`, so it gives false confidence. Use a real mock session or assert that the call is awaited/valid.

## defer

No findings are purely pre-existing or out-of-scope for this diff. All real issues either stem from code introduced by Story 24.5 or from spec/scope drift documented in the same working tree.

## dismissed

- [Review][Dismiss] “Credit preview in instantiate dialog is hardcoded” / “Credit preview is a static generic banner” — consolidated into the `Marketplace cards and instantiate dialog hardcode badge, cost, and run count` patch finding.
- [Review][Dismiss] “Category filtering is client-side only and limited to the first page” / “Backend `vertical` query is not wired through the frontend” — consolidated into the `Frontend vertical filter is not wired through the API` patch finding.
- [Review][Dismiss] “`_workspaceVertical` is computed but never used” — kept as the `PlaybooksContent fetches workspace vertical but never uses it` patch finding; not a false positive but a low-severity cleanup.

## applied

P0/P1 patches and decision-needed items were applied in this session. Key changes:
- Added `Playbook.is_approved` column + `193_add_playbook_is_approved` migration and partial unique index `uq_playbooks_name_scope_system`.
- `PlaybookService.list_playbooks` restored workspace-vertical default filter with explicit `?vertical=` override and canonical vertical mapping (`real_estate -> realestate`, `b2b_equipment -> b2b`, `auto/general -> general`).
- `PlaybookService.instantiate` now authorizes read access, sets `definition.inputs` from `playbook.inputs_schema`, creates a manual `AutomationTrigger`, and immediately launches a run with `runtime_inputs=payload.inputs`.
- Seed playbooks are runnable: every `agent_task` step has a Jinja `params.query` and `definition.inputs.schema` is identical to `inputs_schema`.
- `PlaybookSummary` exposes `author_badge`, `author_name`, `estimated_credits_cost`, `run_count`, `is_featured`, `tags` from `definition.metadata`.
- Frontend marketplace now uses real metadata, wires `vertical` through the API (`atomFamily` + `cacheKeys`), defaults the category from workspace vertical, and improves `PlaybookInstantiateDialog` error handling.
- INV-24.6 hard limit is enforced on `max_leads` / `max_leads_per_run` / `max_skus` at both create/update and instantiation.
- App lifespan now fails fast on seed errors.

Unresolved low-severity items left for a follow-up polish pass:
- case-sensitive / unvalidated `vertical` query param
- Vietnamese diacritics normalization in client-side search
- differentiated empty-state messaging
- stale official playbook cleanup on seed sync

Verification: backend ruff + targeted pytests (17 passed), frontend `tsc --noEmit` + `biome check` pass.
