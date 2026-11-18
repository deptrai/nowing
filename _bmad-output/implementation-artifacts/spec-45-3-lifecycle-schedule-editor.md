---
type: feature
status: done
created: 2026-11-18
context:
  - _bmad-output/implementation-artifacts/epic-45-context.md
  - _bmad-output/implementation-artifacts/spec-45-1-wire-reconcile-campaign-list-page.md
  - _bmad-output/implementation-artifacts/spec-45-2-campaign-detail-run-history-leads.md
---

# Spec 45.3 — Lifecycle actions + Schedule editor (cross-stack PATCH)

## Intent

Đóng 2 gap đã pin trong skeleton Epic 45 (review G-1, G-6) và đưa lifecycle
actions lên UI:

1. **G-1 — schedule scalars unreachable**: `schedule_frequency` /
   `schedule_cron` / `max_runs` trên `lead_campaigns` (models/campaigns.py:67-70)
   không có API writer → `next_run_at` luôn `None` → scheduler
   `check_campaign_schedules` (celery beat, celery_app.py:373-377) không bao giờ
   fire. Phải wire từ 2 cửa: PATCH update + POST create (map từ
   `input_payload.launch_config`).
2. **G-6 — archived không terminal**: `update_campaign_route`
   (campaign_routes.py:475-534) chỉ check `payload.status ∈
   _USER_SETTABLE_STATUSES` — campaign đã `archived` vẫn PATCH sang trạng thái
   khác được. Archive phải là đường một chiều (trừ khi tạo campaign mới).
3. **FE lifecycle**: detail page (45.2) có đủ nút Launch/Pause/Resume/Archive +
   schedule editor dialog; lỗi 409/422/429 hiển thị detail message qua toast.

## Always

- `schedule_*` scalar columns = **single source of truth** cho scheduler.
  `launch_config` trong `input_payload` chỉ còn vai trò display (45.1 mapper đã
  trả); KHÔNG wire ngược.
- `compute_next_run_at(campaign, *, runs_count=None, now=None)`
  (campaign_service.py:208-256) là seam duy nhất tính `next_run_at` — đọc
  `schedule_cron` trước (croniter), rồi `schedule_frequency`
  (hourly/daily/weekly/monthly; `'once'`/giá trị lạ → `None`).
- Mọi PATCH path thay đổi schedule hoặc `status='scheduled'` đều recompute
  `next_run_at` kèm `runs_count` (query `func.count()` trên `campaign_runs`
  như hiện tại :504-513) — tránh stale.
- Validate cron bằng `croniter` (import trong hàm như campaign_service.py:233)
  — expression lỗi → **422** (không im lặng set `None`).
- `archived` → bất kỳ status nào → **422** ("Chiến dịch đã lưu trữ, không thể
  thay đổi trạng thái"). `archived` vẫn nằm trong `_USER_SETTABLE_STATUSES`
  (:57-62) — nó LÀ đường archive.
- `schedule_frequency` chấp nhận: `once` | `hourly` | `daily` | `weekly` |
  `monthly` | `custom`. `custom` **bắt buộc** `schedule_cron` hợp lệ → 422 nếu
  thiếu/sai. `once` → clear schedule (`schedule_cron=None`,
  `schedule_frequency='once'`, `next_run_at=None`). Frequency hợp lệ khác →
  clear `schedule_cron` (trừ khi PATCH gửi kèm cron mới).
- `max_runs`: `int ≥ 1` hoặc `null` (unlimited). `0`/âm → 422.
- POST create (`create_campaign_route` ~:418): sau khi `CampaignSpec.from_payload`
  OK, map `input_payload.launch_config` → scalars trước insert:
  - `schedule_type == 'recurring'` → `schedule_cron = launch_config.cron_expression`
    (validate → 422 nếu thiếu/invalid), `schedule_frequency='custom'` nếu cron
    có, `max_runs` từ `launch_config.max_runs` nếu có; rồi
    `next_run_at = compute_next_run_at(...)`.
  - `schedule_type == 'once'` hoặc không có launch_config → scalars `None`.
- Status transitions FE dùng (pin từ skeleton): **resume** = PATCH
  `status='scheduled'`; **archive** = PATCH `status='archived'`; **pause** =
  POST `/pause` (đã có :611-636); **launch** = POST `/launch` (đã có :538).
  KHÔNG thêm endpoint mới.
- Lỗi surface cho FE: `CampaignQuotaExceededError` → 429 (đã có); `ConcurrentCampaignRunError`
  → 409 (đã có); validation mới → 422 với detail tiếng Việt.
- FE `updateCampaign` request type += `schedule_frequency?` / `schedule_cron?` /
  `max_runs?` (nullable). `campaignSchema` đã có các field này từ 45.1 — không
  đổi.
- FE actions trên `CampaignDetail` (tạo ở 45.2): header buttons theo status —
  `draft` → [Chạy ngay] + [Lên lịch]; `scheduled` → [Tạm dừng] [Chỉnh lịch]
  [Lưu trữ]; `running` → [Tạm dừng]; `paused` → [Tiếp tục] [Lưu trữ];
  `completed`/`failed` → [Chạy lại] [Lưu trữ]; `archived` → không nút (read-only).
- Confirm dùng `components/ui/alert-dialog.tsx` cho action phá huỷ/không thể
  hoàn tác ngay (Lưu trữ; Tạm dừng khi đang `running`). Schedule editor dùng
  `components/ui/dialog.tsx` + `select.tsx` (frequency) + `input.tsx` (cron,
  max_runs).
- i18n: keys `leads.campaign_actions_*` + `leads.campaign_schedule_*` trong
  **en.json và vi.json** (parity test `tests/leads/i18n-parity.test.ts`).

## Never

- KHÔNG thêm endpoint resume/archive/delete/duplicate/clone riêng.
- KHÔNG cho edit `icp_config`/`supply_criteria`/`source_budget_config` sau
  create (non-goal Epic 45).
- KHÔNG sửa `open_campaign_run` internals, quota constants, hay
  `check_campaign_schedules` (đã đúng — chỉ thiếu writer cho scalars).
- KHÔNG đổi `compute_next_run_at` signature; KHÔNG parse cron bằng lib khác
  ngoài `croniter` đã dùng.
- KHÔNG thêm `campaign:*` PAT scope; KHÔNG đụng `webset_campaigns`.
- KHÔNG retry-failed-run endpoint hay nút "retry run" (defer Platform).
- KHÔNG sửa `_run_to_response` hay `campaign_to_response` (45.1 đã chốt shape).

## I/O contract matrix

| # | Row | Khi | Kỳ vọng |
|---|-----|-----|---------|
| M1 | PATCH_SCHEDULE_CUSTOM | PATCH `{schedule_frequency:'custom', schedule_cron:'0 9 * * 1'}` | scalars set, `next_run_at` = croniter next fire |
| M2 | PATCH_CRON_INVALID | PATCH `{schedule_cron:'not-cron'}` hoặc custom+cron xấu | 422 |
| M3 | PATCH_SCHEDULED_NO_SCHEDULE | PATCH `{status:'scheduled'}` khi campaign không có freq/cron (next_run_at=None) | 422 |
| M4 | PATCH_ARCHIVED_GUARD | campaign `archived` + PATCH `{status:'scheduled'}` (hoặc bất kỳ status nào) | 422 |
| M5 | PATCH_RESUME | `paused` + PATCH `{status:'scheduled'}` + có cron | `next_run_at` recomputed ≠ None |
| M6 | PATCH_FREQ_CHANGE_SCHEDULED | campaign `scheduled` + PATCH `{schedule_frequency:'daily'}` | recompute `next_run_at` (không stale), `schedule_cron=None` |
| M7 | PATCH_ONCE_CLEARS | PATCH `{schedule_frequency:'once'}` | `schedule_cron=None`, `next_run_at=None` |
| M8 | POST_CREATE_RECURRING | POST payload `launch_config:{schedule_type:'recurring', cron_expression:'0 8 * * *'}` | campaign có `schedule_cron`, `next_run_at≠None`, `schedule_frequency='custom'` |
| M9 | POST_CREATE_RECURRING_NO_CRON | recurring nhưng thiếu/sai `cron_expression` | 422 |
| M10 | FE_ACTIONS | theo ma trận status→buttons ở Always | đúng nút hiển thị, gọi đúng endpoint |
| M11 | FE_ERROR_TOAST | launch → 429 quota / 409 concurrent | toast hiển thị `detail` từ response |

## Tasks

- **T1 (BE)**: `CampaignUpdateRequest` (:65-69) += `schedule_frequency: str|None`,
  `schedule_cron: str|None`, `max_runs: int|None` (Field ge=1). Extend PATCH
  handler: validate freq/cron/max_runs → apply scalars → recompute
  `next_run_at` khi (a) schedule fields thay đổi HOẶC (b) status→'scheduled';
  archived-guard trước mọi mutation status; 422 theo matrix M2/M3/M4/M7.
- **T2 (BE)**: POST create — sau `from_payload`, đọc `input_payload.launch_config`
  (dict) → map scalars + `next_run_at` trước insert (M8/M9). Helper nhỏ
  `_apply_launch_config_schedule(campaign, input_payload)` có thể đặt trong
  campaign_service.py hoặc route file — giữ route thin.
- **T3 (BE tests)**: extend `tests/unit/routes/test_campaign_crud_routes.py`
  — cover M1–M9 (fake session pattern có sẵn; `compute_next_run_at` có thể để
  thật chạy với `now` hiện tại, assert `next_run_at` not None / None theo case;
  hoặc patch deterministic).
- **T4 (FE)**: `updateCampaign` request type += 3 fields; `CampaignDetail` +=
  action buttons theo status + `CampaignScheduleDialog` (mới, cùng folder
  `components/leads/campaigns/`) với Select frequency + Input cron (hiện khi
  'custom') + Input max_runs; AlertDialog confirm cho Lưu trữ + Tạm dừng
  (running). Sau mỗi action → refetch campaign (router.refresh hoặc refetch
  local state như 45.2 pattern).
- **T5 (FE)**: toast cho 409/422/429 lấy `detail` từ error body (pattern
  `use-campaign-builder.ts` launch toast); i18n keys en+vi; `npx tsc --noEmit`
  clean.

## Acceptance Criteria

- AC1: PATCH set schedule 'custom'+cron → GET detail trả `schedule_cron`,
  `next_run_at` tương lai gần nhất theo cron.
- AC2: `scheduled` campaign + PATCH đổi frequency → `next_run_at` đổi tương ứng.
- AC3: campaign `archived` → mọi PATCH status → 422; `archived` vẫn PATCH tên OK.
- AC4: POST create với `launch_config.recurring`+cron → campaign response có
  scalars + `next_run_at`; thiếu cron → 422 (không tạo campaign).
- AC5: FE detail: đúng button set theo status; schedule dialog lưu → campaign
  refetch hiển thị lịch mới; 429/409 toast hiển thị message backend.
- AC6: `pytest tests/unit/routes/test_campaign_crud_routes.py -x -q` pass
  (cũ + mới); `npx tsc --noEmit` clean; i18n parity test pass.

## Verification

```bash
cd nowing_backend && .venv/bin/python -m pytest tests/unit/routes/test_campaign_crud_routes.py tests/unit/services/test_campaign_service.py -x -q
cd nowing_web && npx tsc --noEmit
cd nowing_web && npx vitest run tests/leads/
```
