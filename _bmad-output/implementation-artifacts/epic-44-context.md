# Epic 44 Context: Lead Campaign Persistence — `lead_campaigns`/`campaign_runs`/`campaign_leads`

<!-- Generated from planning artifacts. Regenerate with compile-epic-context if planning docs change. -->

## Goal

Campaign trở thành durable first-class entity thay vì free-text `spec.name`: mọi launch/persist run được record vào `campaign_runs`, mọi lead attach campaign qua junction `campaign_leads(role)`, identity sống sót qua rename. Đây là unblock cho rate-limit/abuse guard (đã cắt khỏi Epic 43 vì thiếu durable counter store), recurring schedule (`ScheduleConfig` đang inert), per-run usage accounting, và match queue ở Platform phase. Invariants ràng buộc: **AD-1** (mọi lead write qua `ingest_batch` — junction insert xảy ra SAU ingest, không bypass), **AD-4** (dedupe key giữ nguyên).

## Stories

- Story 44.1: Schema + opt-in campaign identity binding — tables, run seam, junction end-to-end
- Story 44.2: Campaign CRUD + launch flow + async run task
- Story 44.3: Recurring scheduler + rate-limit/abuse guard trên `open_campaign_run`
- Story 44.4: Per-run usage accounting (`cost_micros` từ TokenUsage) + vertical #2 proof e2e

## Requirements & Constraints

- **DoD epic-level (analyst G3):** (a) 6 FE dead calls → 0 lỗi 404; (b) mọi persist path campaign-managed có `campaign_runs` row đúng status/stats; (c) `campaign_leads.role` là reader đầu tiên đọc role từ junction thay vì đào `extra_metadata` JSONB — tag `lead_role='supplier'` của Epic 43.4 từ write-only thành queryable.
- **Opt-in bookkeeping (review F4/F10):** `execute_and_persist` có 3 callers ngoài campaign route (`orchestrator_tool.py:191`, `executor.py:86` — agent paths tự build `CampaignSpec('sales-copilot-{ws}')`, spec luôn non-None). Bookkeeping CHỈ chạy khi caller truyền `campaign`/`campaign_run_id` explicit — agent/ad-hoc paths không truyền → không tạo row, không ăn quota. KHÔNG suy ra từ `spec.name`. Pin regression test "agent call không tạo run, không bị throttle".
- **Dual-write giữ nguyên:** tag `extra_metadata` (43.4: `lead_role`, `campaign_direction`, `campaign_key`, `visibility`) + `campaign_id` không đổi; junction là nguồn queryable song song, không thay thế tags.
- **`persist=false` preview** không tạo row nào (không campaign, không run, không junction).
- **Schema validation fail-closed:** duplicate `(workspace_id, name, direction)` → 409 + message thân thiện (không để 500). Status enum khớp FE `campaignStatusSchema` 1:1 {draft, scheduled, running, paused, completed, failed, archived} — không mapping.
- **E2E vertical #2 (44.4):** đề xuất TMĐT supply (legal-entity MST qua `supply_eligible` enterprise+muasamcong) — `POST /campaigns` → launch → run record → `campaign_leads.role` đúng → list/detail history; rename → `campaign_id` không đổi; re-launch → run mới, không duplicate membership; demand regression cũng có run + junction.
- **Alembic:** repo có NHIỀU HEADS (mainline '250' + nhánh cũ 39/51/69/71/89/18/07582243b847) — BẮT BUỘC `alembic heads` trước migration, chain off mainline head; KHÔNG merge heads cũ. Upgrade+downgrade sạch.

## Technical Decisions

### Schema (44.1)

- **Tên table = `lead_campaigns`** (KHÔNG `campaigns`) vì `webset_campaigns` đã chiếm namespace (`app/models/webset_campaign.py:15` — ChainLens, unrelated).
- `lead_campaigns`: {id UUID PK, workspace_id FK→workspaces.id CASCADE, name, direction, status str default `'draft'`, `input_payload` JSONB nullable (raw FE payload khi create qua FE — response mapper dùng), `schedule_frequency`/`schedule_cron`/`max_runs` scalar nullable (denormalized — `next_run_at` compute từ đây, KHÔNG đào JSONB), `next_run_at timestamptz nullable` (materialized schedule — scheduler đọc thẳng, không parse `ScheduleConfig.frequency/cron_expression` mỗi tick), `source` enum `('created'|'execute'|'api')` default `'created'`, `skipped_by_quota` int default 0, created_by, TimestampMixin} + **`UniqueConstraint(workspace_id, name, direction)`**.
- `campaign_runs`: {id UUID PK, campaign_id FK CASCADE, workspace_id FK, status('queued'|'running'|'succeeded'|'failed'), trigger('manual'|'scheduled'|'api'), `spec_snapshot` JSONB = `spec.model_dump(mode="json")` — per-run immutable record, campaign KHÔNG giữ snapshot (kill staleness question), started_at/finished_at, stats JSONB, cost_micros bigint nullable, error nullable}.
- `campaign_leads`: {campaign_id FK, run_id FK, lead_id, workspace_id, role, created_at} — composite FK `(lead_id, workspace_id)`→`leads(id, workspace_id)` (precedent `leads/signals.py:67`), `UniqueConstraint(campaign_id, lead_id)`; `run_id` ghi run đầu tiên attach (pin trong migration comment).
- **RLS (corrected — review F0):** `leads` ĐÃ có `ENABLE + FORCE ROW LEVEL SECURITY` từ migration 221 (tenant policy + lead-visibility policy multi-seat, `_create_lead_rls` :349-372) — KHÔNG phải "app-level only". → 3 tables mới BẬT tenant RLS (workspace policy, predicate copy pattern migration 221: `USING (workspace_id = current_setting('app.workspace_id')::int)` — verify setting name thật trong 221); `campaign_leads` KHÔNG replicate lead-visibility policy (membership là workspace-level metadata — documented deviation).
- **Indexes:** `campaign_runs(workspace_id,campaign_id,created_at)`, `campaign_leads(campaign_id)`, `campaign_leads(lead_id,workspace_id)`, `lead_campaigns(workspace_id,status)`, `lead_campaigns(workspace_id,source)`.
- **Placement:** models tại `app/models/leads/campaign.py` (composite FK→`leads` cùng package); enums `CampaignStatus`/`CampaignRunStatus`/`CampaignTrigger` trong `app/db/enums.py` (convention `Permission` :393); `campaign_leads.role` = `'buyer'`/`'supplier'` khớp giá trị `lead_role` tag 43.4 ghi ở `lead_gen_orchestrator.py:962-994`.

### Seams & contracts

- **Single run-creation seam:** `open_campaign_run(campaign_id, trigger, session)` là hàm DUY NHẤT INSERT `campaign_runs` — sống trong `app/lead_intelligence/services/campaign_service.py` (co-locate `lead_gen_orchestrator.py`; orchestrator 1159 dòng chỉ nhận thin hooks, bookkeeping logic sống ở service). `/execute`, `/launch`, async task, scheduler đều đi qua nó; `execute_and_persist` NHẬN `campaign_run_id` (không tự insert khi đã có) → không double-run.
- **Contained hook:** orchestrator chỉ gọi 1 hook `campaign_service.persist_campaign_bookkeeping(...)` — không inline logic (god-class không phình thêm).
- **Junction nguồn id = `accepted_lead_ids` DUY NHẤT** (review F5) — `lead_ids` chứa cả rejected/degenerate hmac; `ingest_batch` trả `accepted_lead_ids` + `lead_id_mapping` (`lead_batch_service.py:~533-544`), KHÔNG nhận campaign_id → junction insert sau ingest.
- **Transaction boundary (review F3 + architect A5) — T0 blocker cho spec-44-1:** `ingest_batch`/`execute_and_persist`/`campaign_routes` đều KHÔNG commit; junction fail-open phải dùng `session.begin_nested()` SAVEPOINT — junction raise → nhả SAVEPOINT, log, ingest vẫn commit được; bookkeeping KHÔNG chia abort-state với ingest. Convention repo = explicit commit ở caller (vd `lead_clipper_routes.py:368`, `radar.py:567`) nhưng `/campaigns/execute` grep `commit` = 0 → **task T0 của spec-44-1 = trace commit point thật qua toàn bộ call chain (kể cả inner helpers của `ingest_batch` — grep 3-file có thể miss delegate) và pin trong story spec trước khi code; nếu leads không commit → fix kèm trong 44.1.**
- **Serialization:** `spec_snapshot` = `spec.model_dump(mode="json")` — CampaignSpec chứa `user_id: UUID` (:164), `ScheduleConfig.start_at/end_at: datetime` (:33-35), `metadata: dict` (:203) → python-mode dump crash JSONB.
- **Identity uniqueness (review F2):** get-or-create = `INSERT ON CONFLICT DO NOTHING` + re-SELECT (convention `uq_leads_workspace_value_hmac`, leads/main.py:46-50) — race 2 request không duplicate.
- **Lock scheme:** `hashtext` theo `workspace_limits` pattern (`workspace_limits/service.py:112`) — scheme mới documented; KHÔNG reuse 4+ key-space billing đang共存. Concurrent-run guard (architect A3): advisory lock trong `open_campaign_run` cover chống 2 run `running` đồng thời cho 1 campaign — đã có run `running` → 409 (route) / skip + counter (scheduled); v1 REJECT, không queue.
- **Implicit campaign lifecycle (analyst G1):** campaign tạo ngầm qua `/execute` (không qua `POST /campaigns`) lifecycle giống explicit — `'running'` khi run active → `'completed'` khi xong; KHÔNG thêm giá trị enum mới (khớp FE `campaignStatusSchema` 1:1).
- **Implicit campaigns = tồn tại nhưng ẩn (party, user-approved):** `source='created'` = `POST /campaigns`, `'execute'` = get-or-create ngầm qua `/execute` (UI), `'api'` = ngầm qua PAT/machine caller. List endpoint mặc định `WHERE source='created'`; `?include_implicit=true` expose `'execute'`/`'api'` — FE toggle "xem auto-runs". Bookkeeping vẫn tồn tại cho dedupe/quota/reporting — chỉ hiển thị ẩn.
- **Quota-skip không im lặng (party Murat↔Mary):** scheduled skip vì quota KHÔNG tạo run row hư — `lead_campaigns.skipped_by_quota` counter++ mỗi lần skip (observable, không phình `campaign_runs`).
- **Async-celery + RLS trap (architect A4):** `launch_campaign_run` task BẮT BUỘC pattern `auto_refund_lead_task` (`phone_waterfall_worker.py:84-115`): `run_async_celery_task` wrap + `async_session_maker` riêng + `set_request_tenant_context(workspace_id=...)` — thiếu context thì tenant RLS mới chặn insert. Task KHÔNG chung `LEAD_SCRAPERS_QUEUE` và KHÔNG `time_limit=120` (dev D6 — full campaign execute vượt xa); queue + limit pin trong spec-44-2. Task gọi `execute_and_persist(..., campaign=campaign, campaign_run_id=run_id)` — KHÔNG tự insert run thứ hai (review F8); update status/stats/finished_at + `next_run_at` recompute nếu scheduled.
- **`/campaigns/execute`:** sync giữ nguyên + `?async=true` → cùng task path (open_campaign_run → apply_async → run_id); **`async=true&persist=false` → 422** (dev D7 — async implies persist).
- **`LeadGenOrchestratorResult`** (`orchestrator.py:74-92`) += `campaign_id`/`campaign_run_id` (không có campaign identity field hiện tại).

### API contract (44.2)

- Endpoints FE đang gọi (đang 404): `leads-api.service.ts:151-235` + `use-campaign-builder.ts:484-490` — `GET /{workspace_id}/campaigns` list (paged, filter status theo FE enum, default `source='created'`), `GET .../{campaign_id}` detail, `GET .../{campaign_id}/runs`, `POST /{workspace_id}/campaigns` create, `PATCH .../{campaign_id}` name/status, `POST .../{campaign_id}/launch`, `POST /campaigns/execute`.
- **Route ordering:** `/presets` register TRƯỚC `/{campaign_id}` (FastAPI path precedence).
- **Create response = full Campaign theo `campaignSchema`** (review F7): mapper ưu tiên `input_payload`, fallback reconstruct từ spec_snapshot; FE dùng `created.id`/`created.name` ngay — pin wire test conformance với `campaign.types.ts:45-56` (`sources` min 1). `campaignSchema` đòi `icp_config`/`source_budget_config`/`launch_config` — shape CampaignCreateInput, KHÁC CampaignSpec → cần `input_payload` + mapper. Response = backend source-of-truth, FE sửa theo nếu lệch.
- `POST .../{campaign_id}/launch` → `open_campaign_run(campaign_id,'api')` → `launch_campaign_run.apply_async(run_id)`; paused → 409; response khớp FE `launchCampaign` expectation (pin chính xác shape trong story spec — review finding về 202 bị REJECTED, FE chấp nhận run-shape).
- Auth: PAT `leads:read`/`leads:write` — KHÔNG thêm `campaign:*` scope (Permission enum `app/db/enums.py:393-398` giữ nguyên); `check_workspace_access` unified seam.

### Scheduler + quota (44.3)

- MỘT meta-scheduler beat entry (pattern `check_periodic_schedules`, celery_app.py:348-356) quét `lead_campaigns WHERE next_run_at <= now()` → `open_campaign_run(trigger='scheduled')` → `launch_campaign_run.apply_async` — KHÔNG beat per-campaign.
- `max_runs` enforce bằng count `campaign_runs`; stale-run reaper cùng tick: `running` quá threshold → `failed`.
- `spec.metadata['launch_config']` decision pin trong spec story: wire `auto_start` hoặc drop khỏi contract (zero consumers hiện tại).
- **Quota check nằm TRONG `open_campaign_run`** (single door — cover manual + scheduled + async + agent-managed nếu sau này opt-in): đề xuất analyst **N=10 runs/campaign/day + M=500 leads/workspace/day** (conservative, tune sau; đếm qua `campaign_leads` join theo window — pin nguồn đếm); check + insert trong MỘT transaction + advisory lock `hashtext('campaign_run', campaign_id)`; vượt → 429 + detail (route) / skip + `skipped_by_quota`++ (scheduled); không charge, không run row.

### Usage accounting (44.4)

- Campaign path HOÀN TOÀN unbilled (review F9): `LEADS_MULTI_SOURCE_GEN` `billing_unit=None` (definition.py:20), `charge_capability` return 0, 0 callers trong lead_intelligence → `cost_micros` chỉ đếm được từ TokenUsage tagged run_id, không có charge door.
- `campaign_runs.cost_micros` = tổng TokenUsage rows ghi trong run — attach `campaign_run_id` qua `call_details` JSON tại `record_token_usage` (token_tracking_service.py:581); pin chính xác propagation (run-scoped context hoặc caller truyền). Scrape-only run → `cost_micros=0` là giá trị ĐÚNG (usage, không phải charge). Failed run ghi usage đã phát sinh trước khi fail. Payer semantics `_resolve_workspace_owner`. Charge door cho campaign path = Platform design, không phải epic này.

### Test targets (dev pin)

`tests/unit/services/test_campaign_service.py` (44.1 — `open_campaign_run`, quota hook, get-or-create race) + `tests/unit/lead_intelligence/test_campaign_binding.py` (44.1 — opt-in, agent-path pollution regression, junction `accepted_lead_ids`) + `tests/unit/routes/test_campaign_crud_routes.py` + wire-contract test vs `campaign.types.ts` (44.2 — response shape `campaignSchema`, status enum, 409/422) + `tests/unit/tasks/test_campaign_scheduler.py` (44.3 — `next_run_at` tick, concurrent-run guard, quota 429/skip) + `tests/integration/campaigns/test_campaign_e2e.py` (44.4 — vertical #2, PAT thật, run + junction + rename/relaunch).

## UX & Interaction Patterns

- FE `campaignStatusSchema` = `draft|scheduled|running|paused|completed|failed` (`campaign.types.ts:4-11`) — status enum backend khớp 1:1, không mapping.
- FE `campaignSchema` đòi `icp_config`/`source_budget_config`/`launch_config` với `sources` min 1 — KHÁC CampaignSpec shape → backend trả qua `input_payload` + response mapper; wire-contract test bắt buộc.
- `handleSaveCampaign` = `createCampaign` + `launchCampaign` là launch flow chính thức của FE.
- List campaigns mặc định ẩn implicit runs; FE toggle "xem auto-runs" qua `?include_implicit=true`.
- Không build trang list/history UI mới — endpoints sống + FE dead path wire lại.

## Cross-Story Dependencies

- **44.1 là nền cho tất cả:** schema + `open_campaign_run` seam + opt-in binding phải xong trước 44.2 (CRUD/launch cần tables + seam), 44.3 (scheduler + quota cần `next_run_at` + seam door), 44.4 (accounting cần run rows + `campaign_run_id` propagation).
- **T0 blocker trong 44.1:** trace commit point thật (qua toàn bộ call chain `ingest_batch`) trước khi code — nếu leads không commit thì fix kèm trong 44.1.
- 44.2 phụ thuộc `open_campaign_run` từ 44.1; `/launch` và `/execute?async=true` share cùng task path.
- 44.3 quota + concurrent-run guard sống TRONG `open_campaign_run` — phải đặt ở 44.1 (seam) hoặc mở rộng seam ở 44.3 mà không phá contract.
- 44.4 phụ thuộc `campaign_run_id` truyền qua `record_token_usage` — propagation path phải được pin ở 44.1/44.2 trước.
- Kế thừa từ Epic 43: tags `extra_metadata` + `lead_role` (43.4) là dual-write song song với junction; supply adapters `enterprise`/`muasamcong` đã sẵn cho vertical #2 e2e.

## Epic 44 Non-Goals

- No `match_mode="pool"` matching / `corpus_scope="platform_b2b"` — vẫn gated Platform.
- No `campaign:*` PAT scope — reuse `leads:read`/`leads:write`.
- No lead-visibility RLS replication trên `campaign_leads` — tenant RLS only (documented deviation).
- No merge alembic heads cũ — chỉ chain off mainline head.
- No charge_capability door / billing design cho campaign path — `cost_micros` là usage accounting từ TokenUsage; charge per run/lead là pricing decision Platform (review F9).
- No SLA auto-refund async — `auto_refund_lead_task` vẫn dead-producer.
- No campaign list/history UI page mới — endpoints sống + FE dead path wire.
- No dedupe-key chứa tax_id, no role-array dual-role (deferred Epic 43).
- No backfill `campaign_leads` cho leads cũ — forward-only.
- No PDPD consent pipeline, no B2C supply routing, no Maps adapter.
- `launch_config` wire-or-drop = decision trong 44.3.
