# Blind Hunter Prompt — Story 24.7 Multi-Channel Drip Outreach Campaign Engine

## Diff

See: `_bmad-output/implementation-artifacts/review-24-7-working-tree.diff`

This diff covers the following Story 24.7 files (filter out changes unrelated to these files / Story 24.7):

- `nowing_backend/app/config/__init__.py`
- `nowing_backend/app/db.py`
- `nowing_backend/app/schemas/sequence.py`
- `nowing_backend/app/services/sequencer_service.py`
- `nowing_backend/app/services/billing_event_service.py`
- `nowing_backend/app/gateway/zalo/zns_client.py`
- `nowing_backend/app/gateway/telegram/adapter.py`
- `nowing_backend/app/gateway/telegram/client.py`
- `nowing_backend/app/gateway/registry.py`
- `nowing_backend/app/gateway/accounts.py`
- `nowing_backend/app/gateway/zalo/webhook.py`
- `nowing_backend/app/gateway/telegram/callbacks.py`
- `nowing_backend/app/gateway/inbox_processor.py`
- `nowing_backend/app/automations/tasks/sequence_tasks.py`
- `nowing_backend/app/celery_app.py`
- `nowing_backend/tests/unit/services/test_sequencer_service.py`
- `nowing_backend/tests/integration/services/test_sequence_scheduler.py`
- `nowing_web/contracts/types/sequence.types.ts`
- `nowing_web/lib/apis/sequence-api.service.ts`
- `nowing_web/components/automations/VisualCadenceBuilder.tsx`
- `nowing_web/app/dashboard/[workspace_id]/automations/campaigns/new/page.tsx`
- `nowing_web/app/dashboard/[workspace_id]/automations/campaigns/[sequence_id]/page.tsx`
- `nowing_web/tests/automations/campaign-sequence-builder.spec.ts`

## Instructions

Invoke the `bmad-review-adversarial-general` skill on this diff. Focus on Story 24.7 only. Report security, concurrency, logic, and correctness issues.
