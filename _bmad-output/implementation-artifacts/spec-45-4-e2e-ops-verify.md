---
type: feature
status: done
created: 2026-11-18
context:
  - _bmad-output/implementation-artifacts/epic-45-context.md
  - _bmad-output/implementation-artifacts/epic-44-retro-2026-11-18.md
---

# Spec 45.4 — E2E browser flow + Ops verify (AI-44.2 carry-in)

## Intent

Chứng minh Epic 45 chạy end-to-end bằng trình duyệt thật (Playwright — đã có
infra: `nowing_web/playwright.config.ts`, port **8000**, auth storageState +
token helper) và đóng nợ ops **AI-44.2** từ retro Epic 44: verify celery
worker + beat thực sự consume queue `nowing.campaigns` và tick
`check_campaign_schedules` trên môi trường dev.

## Always

- Playwright test đặt tại `nowing_web/tests/` theo convention hiện có (config
  `playwright.config.ts:38,101` — baseURL port 8000, storageState auth có sẵn).
- Test phủ **demand flow** (tạo → list → detail → lifecycle) VÀ **supply flow**
  (tạo "Tìm nhà cung cấp" → list badge direction → detail supply_criteria).
- Backend dev server trước test: uvicorn port 8000 (theo playwright config) —
  test dùng API thật + UI thật, không mock adapter ở tầng FE.
- Ops verify (AI-44.2) là checklist chạy tay trong task, ghi kết quả vào
  test-summary:
  1. `celery -A app.celery_app inspect registered` chứa `launch_campaign_run`,
     `check_campaign_schedules`.
  2. Worker consume queue `nowing.campaigns` (CAMPAIGN_QUEUE).
  3. Beat entry `check-campaign-schedules` (celery_app.py:373-377) active —
     quan sát tick trong log hoặc `-Q`/`inspect active_queues`.
  4. `alembic upgrade head` trên dev DB → rev 251 present (3 bảng + RLS).
- Ghi phát hiện vào `_bmad-output/implementation-artifacts/tests/test-summary.md`
  (section "## Spec 45.4").

## Never

- KHÔNG chạy scrape thật / gọi adapter ngoài trong e2e (tạo campaign + UI flow
  là đủ; execute thật đã cover ở backend integration tests Epic 44).
- KHÔNG viết test vào framework khác (không Cypress, không Jest DOM mới).
- KHÔNG sửa playwright.config.ts trừ khi thiếu project setup (giữ port 8000).
- KHÔNG block spec trên việc hạ `require_tax_id` default hay nới supply yield.

## Tasks

- **T1**: Playwright spec `nowing_web/tests/campaigns/campaign-lifecycle.spec.ts`
  (hoặc folder test hiện có tương đương): login state → `/leads/campaigns/new`
  tạo demand campaign → list page thấy row → click vào detail → thấy config
  card + tabs → PATCH schedule qua dialog → status 'scheduled' + next_run_at
  hiển thị → pause → resume → archive → row detail read-only.
- **T2**: cùng spec file (hoặc case thứ 2): tạo supply campaign
  ("Tìm nhà cung cấp") → list hiển thị badge direction đúng → detail hiển thị
  supply_criteria (không phải icp_config).
- **T3**: ops verify checklist (Always) — chạy lệnh, dán output vào
  test-summary; nếu worker/beat không có trong môi trường dev thì ghi
  `blocked-env` + đường verify prod thay thế, KHÔNG giả pass.
- **T4**: cập nhật test-summary + spec status.

## Acceptance Criteria

- AC1: `npx playwright test tests/campaigns/` (hoặc path tương đương) green
  trên dev stack — demand + supply flow.
- AC2: Ops checklist có output thật cho 4 mục (hoặc `blocked-env` rõ ràng).
- AC3: Không test nào phụ thuộc dữ liệu scrape thật.

## Verification

```bash
cd nowing_web && npx playwright test tests/campaigns/
cd nowing_backend && .venv/bin/python -m pytest tests/unit/routes/test_campaign_crud_routes.py tests/unit/routes/test_campaign_leads_route.py -x -q
celery -A app.celery_app inspect registered | grep -E 'launch_campaign_run|check_campaign_schedules'
cd nowing_backend && alembic current && alembic heads
```
