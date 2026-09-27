---
title: 'No-Mock E2E Phase 0+3 — backend seed script + gated connector provision endpoint'
type: 'feature'
created: '2026-09-26'
status: 'in-progress'
baseline_revision: '3609841652f8bb6083208697b74e118e5f424973'
review_loop_iteration: 0
followup_review_recommended: false
context: []
warnings: []
deferred: []
---

<intent-contract>

## Intent

**Problem:** Production Playwright E2E hiện tại fail ~40% vì thiếu seed data và connector OAuth thật; cần hạ tầng backend để provision connectors bằng credentials thật + seed workspace 15 với data `source='e2e-seed'` — không đụng test specs.

**Approach:** (1) Viết `seed_e2e_prod.py` chạy qua SSH `nowing` vào Postgres container, idempotent, tạo workspace 15 + member user + leads/documents/DNC/tables với canary tokens; (2) Thêm route `POST /__e2e__/connectors/provision` gated `x-playwright-test` + superuser, đọc `E2E_<PROVIDER>_*` env vars → tạo `search_source_connector` row đã connected, trả `connector_id`; (3) kèm `teardown_e2e_prod.py`.

## Boundaries & Constraints

**Always:**
- Idempotent seeding: mọi row seed đều có `source='e2e-seed'` (hoặc cột tương đương) và upsert theo (source, key).
- Provision endpoint chỉ mount khi `E2E_PROVISION_ENABLED=TRUE`; trả 404 khi disabled.
- Auth gate = `x-playwright-test: true` header + superuser session (không PAT, không impersonation).
- Không bao giờ trả token/credentials trong response — chỉ `connector_id`.
- Seed chạy qua SSH `nowing` (167.172.66.16, root, key `~/.ssh/id_nowing`) vào container `nowing-postgres` (user `nowing`, db `nowing`) — script có `--local` mode cho dev.
- User `e2e-member@nowing.net` password `E2ePassword123!` role **Member** trong workspace 15 (argon2id qua `PasswordHelper` của fastapi-users, không phải argon2 thuần).
- Seed data dùng canary tokens từ `nowing_web/tests/helpers/canary.ts` (đồng bộ).
- Workspace 15 đã tồn tại — chỉ update feature flags + insert membership, KHÔNG tạo mới.
- Tham chiếu user prod `e2e-test@nowing.net` id `e60920ff-bb72-4ae8-8434-f29bc7226afb` (đã là Owner ws15).

**Never:**
- KHÔNG đụng `nowing_web/tests/**` — test specs là phase sau.
- KHÔNG commit credentials thật vào repo — `.env.example` chỉ document key names.
- KHÔNG mount `__e2e__/connectors/provision` khi `E2E_PROVISION_ENABLED` unset/false — prod mặc định là 404.
- KHÔNG tạo connector row khi provider env thiếu → trả 404 cho provider đó.
- KHÔNG dùng raw SQL string concat — dùng SQLAlchemy ORM / parameterized upsert.
- KHÔNG seed data vào workspace khác ngoài id=15.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| SEED_HAPPY | Run `seed_e2e_prod.py --ssh nowing` lần 1 | Workspace 15 có flags; member user tồn tại; ~10 leads + docs + DNC `source='e2e-seed'` | exit 0, print summary |
| SEED_IDEMPOTENT | Run seed lần 2 | Không duplicate rows — upsert no-op | exit 0 |
| PROVISION_DISABLED | `E2E_PROVISION_ENABLED` unset/false | `POST /__e2e__/connectors/provision` → 404 | Route không được mount |
| PROVISION_NO_HEADER | `E2E_PROVISION_ENABLED=TRUE`, request thiếu `x-playwright-test: true` | 404 (ẩn existence) | Không tiết lộ gate |
| PROVISION_NON_SUPERUSER | Header OK nhưng user không phải superuser | 403 | `require_superuser` reject |
| PROVISION_MISSING_ENV | `{ "connector": "slack", "workspace_id": 15 }` nhưng `E2E_SLACK_BOT_TOKEN` unset | 404 + detail `provider "slack" not provisioned` | Không tạo row |
| PROVISION_HAPPY | Header + superuser + env OK | 200 `{ connector_id: int }`, row `search_source_connectors` tồn tại, tokens encrypted trong `config` | — |
| TEARDOWN | `teardown_e2e_prod.py --ssh nowing` | Xóa hết row `source='e2e-seed'` khỏi leads/documents/DNC/tables; membership `e2e-member` vẫn giữ (không phải seed row) | exit 0 |
| PROVISION_UNSUPPORTED | `{ "connector": "unknown", ... }` | 422 invalid connector key | Pydantic validate |
| SEED_DRY_RUN | `--dry-run` | Print actions, không commit | exit 0 |

</intent-contract>

## Code Map

- `nowing_backend/scripts/seed_test_users.py` — **pattern idempotent user+workspace seed**; reuse `_get_or_create_user`, `_ensure_roles`, `_ensure_membership` style. **Read-only reference.**
- `nowing_backend/scripts/seed_agent_chat_e2e.py` — pattern arg `--force` + `_require_dev_environment`. **Read-only reference.**
- `nowing_backend/app/models/connectors.py:66-134` — `SearchSourceConnector`: `workspace_id`, `user_id`, `connector_type`, `name`, `config` (JSONB), `is_indexable`. Unique `(workspace_id, user_id, connector_type, name)`.
- `nowing_backend/app/models/leads/main.py:33-` — `Lead`: `workspace_id`, `source`, `company_name`, `domain`, `value_hmac` (unique per ws). `generate_lead_hmac(ws_id, company, domain)` in `app/lead_intelligence/services/lead_stream_service.py:47`.
- `nowing_backend/app/models/documents.py:69-167` — `Document`: `title`, `content`, `content_hash`, `connector_id` (nullable), `document_type`, `status` JSONB `{state: ready}`.
- `nowing_backend/app/models/workspaces.py:29-` — `Workspace`: `web_builder_enabled`, `presentation_studio_enabled` cols (already exist, default true). `WorkspaceDncRecord` (line 681): `workspace_id`, `record_type`, `value`, `value_hmac`, `source='manual'|'e2e-seed'`. `WorkspaceTable` (line 650): `name`, `filter_preset` JSONB. `WorkspaceMcpToolSetting` (line 421): `workspace_id`, `tool_name`, `enabled`.
- `nowing_backend/app/db/enums.py:57-93` — `SearchSourceConnectorType` enum: `SLACK_CONNECTOR`, `NOTION_CONNECTOR`, `LINEAR_CONNECTOR`, `JIRA_CONNECTOR`, `CONFLUENCE_CONNECTOR`, `CLICKUP_CONNECTOR`, `COMPOSIO_GOOGLE_DRIVE_CONNECTOR`, `COMPOSIO_GMAIL_CONNECTOR`, `COMPOSIO_GOOGLE_CALENDAR_CONNECTOR`, `GOOGLE_DRIVE_CONNECTOR`, `GOOGLE_GMAIL_CONNECTOR`, `GOOGLE_CALENDAR_CONNECTOR`, `DROPBOX_CONNECTOR`, `ONEDRIVE_CONNECTOR`.
- `nowing_backend/app/routes/mcp_oauth_route.py:361-474` — **canonical connector persistence pattern**: `connector_config = {"server_config": {...}, "mcp_service": svc_key, "mcp_oauth": {"access_token": enc.encrypt_token(...), "refresh_token": ..., "token_endpoint": ..., "client_id": ..., "expires_at": isoformat}, "_token_encrypted": True, ...account_meta_keys}`. Tokens encrypted via `TokenEncryption(config.SECRET_KEY)` (Fernet).
- `nowing_backend/app/routes/slack_add_connector_route.py:269-324` — non-MCP OAuth config pattern: `{"bot_token": enc.encrypt_token(bot_token), "refresh_token": ..., "bot_user_id": ..., "team_id": ..., "team_name": ..., "_token_encrypted": True}`.
- `nowing_backend/app/routes/notion_add_connector_route.py:325-410` — Notion config shape: `{"access_token": enc, "refresh_token": enc|None, "expires_in", "expires_at", "workspace_id", "workspace_name", "bot_id", "_token_encrypted": True}`.
- `nowing_backend/app/routes/composio_routes.py:285-405` — Composio config: `{"composio_connected_account_id", "toolkit_id", "toolkit_name", "is_indexable"}` (no local tokens — Composio hosts them).
- `nowing_backend/app/schemas/{slack,notion,linear,clickup,atlassian}_auth_credentials.py` — per-provider `to_dict()` shape used by indexers.
- `nowing_backend/app/users.py:410` — `require_superuser(auth)` dep: rejects PAT + impersonation; checks `auth.user.is_superuser`.
- `nowing_backend/app/auth/context.py` — `AuthContext` (session auth).
- `nowing_backend/app/config/oauth.py` — env-var config pattern (`os.getenv`); add new `app/config/e2e.py` here.
- `nowing_backend/app/routes/__init__.py` — router registry; conditional mount at bottom behind `if config.E2E_PROVISION_ENABLED:`.
- `nowing_backend/app/utils/oauth_security.py:155` — `TokenEncryption.encrypt_token`/`decrypt_token` (Fernet w/ `SECRET_KEY`).
- `nowing_backend/app/services/mcp_oauth/registry.py` — `MCP_SERVICES` map service_key → `connector_type`, `mcp_url`, `allowed_tools`, `account_metadata_keys`. **Reuse** để build `server_config.url` + `mcp_service` cho provisioned connectors (Linear/Jira/ClickUp/Slack/Airtable/Notion/Confluence).
- `nowing_backend/.env.example` — thêm section `E2E_*` keys (comment-only placeholders).
- `nowing_web/tests/helpers/canary.ts` — **read-only** source of `CANARY_TOKENS` (do NOT edit).
- `nowing_backend/tests/e2e/auth_mint.py` — **read-only** reference: existing `__e2e__` test-only route pattern (mounted by run_backend.py, NOT prod). New provision route is DIFFERENT: lives in `app/routes/` so it ships in prod image but stays gated.

## Tasks & Acceptance

**Execution:**

- `nowing_backend/app/config/e2e.py` -- CREATE -- load `E2E_PROVISION_ENABLED` + `E2E_<PROVIDER>_*` env vars; expose `E2E_PROVISION_ENABLED: bool` + `E2E_PROVIDER_ENV: dict[str, dict[str, str|None]]` keyed by provider (`slack`, `notion`, `linear`, `jira`, `clickup`, `confluence`, `google_drive`, `gmail`, `google_calendar`, `composio_drive`, `composio_gmail`, `composio_calendar`, `dropbox`, `onedrive`, `mailgun`, `stripe_test`). Import-time safe (no exceptions on missing keys).
- `nowing_backend/app/config/__init__.py` -- EDIT -- `from app.config.e2e import *` after `oauth` import; keep `__all__` update minimal.
- `nowing_backend/app/routes/e2e_provision.py` -- CREATE -- `APIRouter(prefix="/__e2e__", tags=["__e2e__"])` with `POST /connectors/provision`; deps: header check `x-playwright-test: true` → 404 if missing, then `Depends(require_superuser)`; body schema `ProvisionRequest{connector: str, workspace_id: int}`; return `ProvisionResponse{connector_id: int, connector_type: str}`; per-provider config builder fn (private `_build_<provider>_config`) using `TokenEncryption(config.SECRET_KEY)`; reuse `generate_unique_connector_name`; handle IntegrityError→409, missing env→404.
- `nowing_backend/app/routes/__init__.py` -- EDIT -- import + conditional `router.include_router(e2e_provision_router)` wrapped in `if config.E2E_PROVISION_ENABLED:` (import at top is fine; mount is the gate).
- `nowing_backend/scripts/seed_e2e_prod.py` -- CREATE -- async main; modes `--local` (default `DATABASE_URL`), `--ssh` (spawn `ssh nowing "docker exec nowing-postgres ..."` shelling into psql via stdin heredoc, OR run python inside the backend container — pick simplest reliable: `docker exec -i nowing-backend python - <<'PY'` so we reuse backend deps + session maker); `--dry-run` flag; `--force` to skip env check; seeds: workspace 15 feature flags ON; user `e2e-member@nowing.net` + WorkspaceMembership role=Member; 10 `Lead` rows `source='e2e-seed'` with canary company names; 1 `WorkspaceTable` "E2E Leads Table"; 5 `WorkspaceDncRecord` `source='e2e-seed'` (phone + domain + email mix); 3 `Document` rows `document_type=FILE`, `document_metadata.source='e2e-seed'`, content embeds `CANARY_TOKENS.driveCanaryFile` + `manualUploadMdCanary` + `manualUploadPdfCanary`; 3 `WorkspaceMcpToolSetting` rows (e.g. `slack_send_message`, `linear_save_issue`, `jira_createJiraIssue`) `enabled=True`.
- `nowing_backend/scripts/teardown_e2e_prod.py` -- CREATE -- same modes; deletes rows WHERE `source='e2e-seed'` (or `document_metadata->>'source'='e2e-seed'` for documents) on tables: `leads`, `documents`, `workspace_dnc_records`, `workspace_tables` (by name prefix `E2E %`), `workspace_mcp_tool_settings` (by tool_name list). User `e2e-member` row + membership kept (not `source`-tagged; safe).
- `nowing_backend/.env.example` -- EDIT -- append `# --- E2E provision endpoint (Phase 0/3 no-mock) ---` section listing all `E2E_*` keys commented out with brief safe comments.
- `nowing_backend/tests/routes/test_e2e_provision.py` -- CREATE -- unit tests: disabled→no route (404 even w/ header); missing header→404; non-superuser→403; missing env for provider→404; happy path returns connector_id and creates row with encrypted `access_token`; unsupported connector→422.

**Acceptance Criteria:**

- Given `E2E_PROVISION_ENABLED` is unset or `false`, when `POST /__e2e__/connectors/provision` is hit, then the endpoint is not registered → 404.
- Given `E2E_PROVISION_ENABLED=TRUE`, when the request lacks `x-playwright-test: true` header, then response is 404 (gate hidden).
- Given header present but user is not `is_superuser`, when provision is called, then response is 403 via `require_superuser`.
- Given provider `slack` requested but `E2E_SLACK_BOT_TOKEN` env is missing, when provision is called with valid auth, then response is 404 with detail naming the provider.
- Given valid auth + env vars set, when `POST /__e2e__/connectors/provision {connector:"slack", workspace_id:15}` succeeds, then response contains `connector_id` (int), DB row exists with `config.bot_token` encrypted by `TokenEncryption`, and no plaintext token is in the response body.
- Given `seed_e2e_prod.py` has run once, when run again, then no duplicate rows appear (idempotent by `source='e2e-seed'` + unique key).
- Given seed has run, when `teardown_e2e_prod.py` runs, then all rows tagged `source='e2e-seed'` are deleted while `e2e-member@nowing.net` user + membership persist.
- Given the diff is inspected, when reviewing for secrets, then no real token/credential values appear (only env var *names* in code and `.env.example`).

## Spec Change Log

## Review Triage Log

## Design Notes

### 1. Connector config shapes (per provider)

Provision endpoint builds `config` matching what the real OAuth callbacks write, so indexers + refresh logic work unchanged:

- **Slack** (`SLACK_CONNECTOR`): `{"bot_token": enc(bot_token), "refresh_token": enc|None, "bot_user_id", "team_id", "team_name", "token_type":"Bearer", "expires_in", "expires_at", "scope", "_token_encrypted": True}` — envs: `E2E_SLACK_BOT_TOKEN`, `E2E_SLACK_TEAM_ID`, `E2E_SLACK_TEAM_NAME`, optional `E2E_SLACK_BOT_USER_ID`, `E2E_SLACK_REFRESH_TOKEN`.
- **Notion** (`NOTION_CONNECTOR`): `{"access_token": enc, "refresh_token": enc|None, "expires_in", "expires_at", "workspace_id", "workspace_name", "bot_id", "_token_encrypted": True}` — envs: `E2E_NOTION_ACCESS_TOKEN`, optional `E2E_NOTION_WORKSPACE_ID`, `E2E_NOTION_WORKSPACE_NAME`, `E2E_NOTION_BOT_ID`.
- **MCP OAuth family** (Linear/Jira/ClickUp/Confluence/Airtable): shape = `{"server_config":{"transport":"streamable-http","url":svc.mcp_url},"mcp_service":<key>,"mcp_oauth":{"client_id","client_secret":enc,"token_endpoint","access_token":enc,"refresh_token":enc|None,"expires_at","scope"},"_token_encrypted":True, ...account_meta}` — envs: `E2E_<PROVIDER>_ACCESS_TOKEN`, `E2E_<PROVIDER>_REFRESH_TOKEN`, `E2E_<PROVIDER>_CLIENT_ID`, `E2E_<PROVIDER>_CLIENT_SECRET`, `E2E_<PROVIDER>_TOKEN_ENDPOINT` (falls back to `svc.token_endpoint_override` or known default).
- **Composio** (`COMPOSIO_*_CONNECTOR`): `{"composio_connected_account_id","toolkit_id","toolkit_name","is_indexable"}` — envs: `E2E_COMPOSIO_API_KEY`, `E2E_COMPOSIO_<TOOLKIT>_ACCOUNT_ID`. No token encryption needed (Composio hosts).
- **Google direct** (`GOOGLE_DRIVE_CONNECTOR`, `GOOGLE_GMAIL_CONNECTOR`, `GOOGLE_CALENDAR_CONNECTOR`): reuse OAuth callback shape — envs: `E2E_GOOGLE_CLIENT_ID`, `E2E_GOOGLE_CLIENT_SECRET`, `E2E_GOOGLE_REFRESH_TOKEN`. Backend mints access_token lazily via refresh flow (provision writes `refresh_token` + `client_id` + `client_secret` encrypted, leaves `access_token=None` — indexer refresh path handles it).
- **Dropbox / OneDrive**: `{"access_token": enc, "refresh_token": enc|None, ...}` — envs `E2E_DROPBOX_ACCESS_TOKEN`, `E2E_ONEDRIVE_ACCESS_TOKEN`, optional `_REFRESH_TOKEN`, `_CLIENT_ID`, `_CLIENT_SECRET`.
- **Mailgun / Stripe test**: not connector rows — just env wiring for downstream spec consumption. Document keys only.

Provider key naming in API body matches env prefix: `connector="slack"` → reads `E2E_SLACK_*`. Map connector_key → `SearchSourceConnectorType` via `_PROVIDER_TO_CONNECTOR_TYPE` dict.

### 2. Seeding idempotency strategy

- Leads: `value_hmac = sha256(f"{ws_id}:{domain}:{company_lower}")` — deterministic across runs. Upsert via `ON CONFLICT (workspace_id, value_hmac) DO NOTHING`.
- Documents: `unique_identifier_hash = sha256(f"{ws_id}:e2e-seed:{title}")` — unique index enforces idempotency.
- DNC: unique on `(workspace_id, record_type, value_hmac)` — `ON CONFLICT DO NOTHING`.
- Workspace tables: check-by-name + insert-if-missing (no unique constraint on name).
- MCP tool settings: unique on `(workspace_id, tool_name)` — `ON CONFLICT DO UPDATE enabled=true`.
- Membership: `SELECT`-then-`INSERT` (same pattern as `seed_test_users.py:_ensure_membership`).
- Workspace 15 feature flags: `UPDATE ... WHERE id=15` (idempotent by nature).

### 3. SSH execution mode

Prefer `ssh nowing 'docker exec -i nowing-backend python - <<PY' < seed_e2e_prod.py` so the seed script runs INSIDE the backend container with all deps + env vars already loaded (DATABASE_URL, SECRET_KEY for TokenEncryption, etc.). Avoids shipping SQL or re-implementing the ORM locally. `--local` mode runs against local `DATABASE_URL` for dev.

## Verification

**Commands:**
- `cd nowing_backend && uv run pytest tests/routes/test_e2e_provision.py -v` -- all cases pass
- `cd nowing_backend && uv run python -c "from app.config import config; print(config.E2E_PROVISION_ENABLED)"` -- prints `False` (no env set)
- `cd nowing_backend && E2E_PROVISION_ENABLED=TRUE uv run python -c "from app.config import config; print(config.E2E_PROVISION_ENABLED)"` -- prints `True`
- `cd nowing_backend && uv run python scripts/seed_e2e_prod.py --dry-run --local` -- prints intended actions without committing
- `cd nowing_backend && uv run ruff check app/routes/e2e_provision.py app/config/e2e.py scripts/seed_e2e_prod.py scripts/teardown_e2e_prod.py` -- clean
- `cd nowing_backend && uv run python -c "from app.routes import router; print([r.path for r in router.routes if 'e2e' in r.path])"` -- `[]` when env unset; `['/api/v1/__e2e__/connectors/provision']` (or whatever prefix) when set
- `git diff` -- no secrets in code/.env.example; only env var names

**Manual checks:**
- `ssh nowing 'docker exec nowing-postgres psql -U nowing -d nowing -c "SELECT count(*) FROM leads WHERE source='"'"'e2e-seed'"'"';"'` after real seed → ≥10
- `curl -i -X POST https://api.nowing.net/__e2e__/connectors/provision -H 'content-type: application/json' -d '{}'` on prod → 404 (E2E_PROVISION_ENABLED unset on prod by default)
