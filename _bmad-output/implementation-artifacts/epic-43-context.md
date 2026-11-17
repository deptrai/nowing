# Epic 43 Context: Two-Sided CampaignSpec — Supply Direction (stage Productized)

<!-- Generated from planning artifacts. Regenerate with compile-epic-context if planning docs change. -->

## Goal

Mở rộng `CampaignSpec` chạy được hai chiều: ngoài `direction="demand"` hiện tại (chủ campaign tìm entities khớp ICP), spec hỗ trợ `direction="supply"` — người dùng cần tìm nhà cung cấp — trên cùng một engine và spec, đúng thiết kế hai chiều đã sign-off. Phase này (chặng 2 Productized) chỉ gồm: schema + joint validation, direction-aware adapter routing, supply post-filter, role/visibility tagging, intake form tối thiểu và e2e. Pool matching và shared corpus là chặng 3 Platform — schema phải reject các tổ hợp đó ngay từ đầu.

## Stories

- Story 43.1: CampaignSpec direction fields + AD-5 joint validation matrix
- Story 43.2: Direction-aware adapter resolution (`_for_spec` + `_for_campaign` + query builder)
- Story 43.3: Post-filter supply tại persist seam + NormalizedLead `rating`/`verified`
- Story 43.4: Lead role + visibility tagging cho supply campaign
- Story 43.5: FE intake "Tìm nhà cung cấp" + wire contract direction
- Story 43.6: E2E supply campaign — enterprise/masothue path thật

## Requirements & Constraints

- **Joint validation tại schema layer (AD-5):** mọi tổ hợp vô nghĩa về semantics (supply thiếu `supply_criteria`, demand có supply fields, `match_mode` pool/hybrid, `corpus_scope="platform_b2b"`, supply mixing demand-shaped fields) phải bị reject ở `model_validate` — không trôi xuống runtime, không rải check ở routes/orchestrator. Toàn bộ ma trận ô validation phải có test parametrize, không ô nào silently pass.
- **Backward compatibility:** demand path không đổi hành vi — payload cũ thiếu field mới vẫn parse và chạy y hệt. CampaignSpec không persisted nên "backward" = demand behavior bit-for-bit.
- **Supply routing fail-closed:** supply campaign chỉ được resolve tới adapters có capability `supply_eligible` (hiện chỉ `enterprise`/masothue + `muasamcong`). Không bao giờ fall-through sang demand heuristics hay trả demand adapters, kể cả với query vô nghĩa. Explicit `target_sources` user override vẫn thắng (escape hatch documented).
- **Supply post-filter tại persist seam:** `require_tax_id`, `min_rating`, `require_verified`, sparse-identity guard (phải có `company_name` hoặc `tax_id`), và locations guard chạy ở execution path trước `ingest_batch` — không phải preview planner. Mọi lead bị drop phải có counter observable trong result meta; không nuốt leads âm thầm. Demand path không chạy filter này.
- **Role/visibility tagging:** leads từ supply campaign mang metadata `lead_role="supplier"`, `campaign_direction`, `campaign_key` (= `spec.name`), `visibility` — qua funnel `ingest_batch` (AD-1), không sửa service. Demand không ghi role tag.
- **FE intake tối thiểu:** form "Tìm nhà cung cấp" hỏi đúng subset (cần gì / ở đâu / yêu cầu chất lượng), validation client khớp server, reuse campaign create flow hiện có, i18n vi/en đầy đủ. Sau submit user thấy pre-flight plan trước khi launch — cùng flow demand.
- **E2E phải chứng minh xuyên suốt** spec → routing → filters → persist → role-tag trên dev stack thật, kèm demand regression (campaign cũ không silent break) và joint-validation 422.

## Technical Decisions

- **Invariants ràng buộc:** AD-1 (mọi lead write qua `ingest_batch` — auto-table ở service layer), AD-4 (dedupe `(workspace_id, value_hmac)` giữ nguyên; role không encode vào `client_id`), AD-5 (joint validation), AD-3 (envelope contract chỉ áp tool boundary, không áp HTTP route).
- **Code anchors đã verify (bmad-review):** registry `_register_defaults` không có adapter tên `masothue` hay `google-maps`/`Maps` — supply MVP chỉ `enterprise` (masothue bên trong) + `muasamcong`. `NormalizedLead` chưa có `rating`/`verified` — thêm trong epic này là deliverable. Có HAI đường resolve adapters (`resolve_adapters_for_spec` và wrapper `resolve_adapters_for_campaign` với fallback chain riêng) — supply guard phải cover cả hai. Có HAI seam query synthesis (planner preflight + orchestrator execute path) — phải vá cả hai. `spec.get("direction")` phải handle cả dict lẫn object. `resolve_adapters_for_campaign` wrapper nhận `dict` spec.
- **Campaign identity = `spec.name`** (không unique, documented — campaign trùng tên share lineage). Không có `campaigns`/`campaign_runs` table — mọi traceability qua `extra_metadata` trên lead.
- **Supply ordering deterministic:** thứ tự registration cố định, KHÔNG đọc `priority` (bị demand run mutate) và KHÔNG mutate `priority`/`lead_quota` trên shared adapter instances trong nhánh supply.
- **Đã chốt (user decision 2026-11-17):** giữ `muasamcong` dù tender notices sẽ bị `require_tax_id` default lọc (trade-off documented); cắt rate-limit/abuse guard supply (không có durable counter store, defer đến khi có `campaign_runs`).
- Accepted limitations (ghi spec/docstring): role tag single-key last-write-wins (junction `campaign_leads(role)` deferred); dedupe key không chứa `tax_id` — hai pháp nhân trùng tên khác MST merge một row.

## UX & Interaction Patterns

- Supply intake chỉ map subset của spec (§10: cần gì / ở đâu / yêu cầu chất lượng) — không build trang riêng, thêm mode selector vào campaign create flow hiện có.
- `require_tax_id` default on với ghi chú "áp dụng khi tìm pháp nhân có MST".
- Nhánh supply derive `location_profile` từ location đầu tiên để preflight coverage + location telemetry có nghĩa (không để `None` → mọi adapter hiện 0.6 nationwide).

## Cross-Story Dependencies

- 43.1 là nền: 43.2–43.6 đều phụ thuộc `direction`/`SupplyCriteria` + validation matrix.
- 43.2 (routing) phải xong trước 43.3 (post-filter) và 43.6 (e2e) — supply adapters phải resolve đúng mới có leads để filter/verify.
- 43.3 + 43.4 cùng tác động execution/persist path — 43.4 tag metadata tại điểm orchestrator gọi ingest, sau filter của 43.3.
- 43.5 (FE) cần wire contract của 43.1 ổn định (`from_campaign_create_input` dispatch supply/demand).
- 43.6 verify toàn bộ chuỗi và là gate close epic (runtime smoke trên dev như epic 42).
- Với epic 42: kế thừa PAT authz seam (`leads:write` scope — AI-42.4) cho e2e; kế thừa kỷ luật repro-before-fix (AD-6).

## Epic 43 Non-Goals

- No pool/hybrid matching engine, no `platform_b2b` corpus thực thi — schema reject, platform phase làm.
- No `campaign_leads` junction table, no `campaigns`/`campaign_runs` table.
- No rate-limit/abuse guard supply (defer — không có durable counter store).
- No buyer-intake đầy đủ (match queue, SLA auto-refund) — chỉ intake form tối thiểu.
- No Maps/Google-Maps adapter (chưa tồn tại trong code — "Maps" trong §10 là aspirational).
- No vertical supply cá nhân (BĐS owner, rao vặt B2C) — cần shared-adapter map design riêng, phase sau.
