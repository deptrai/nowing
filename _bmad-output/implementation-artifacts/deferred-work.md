# Deferred Work

## Deferred from: code review of story 11.1

- **Finding:** Concurrent `PATCH /users/me/notification-preferences` updates can lose keys because `_merge_notification_preferences` reads the user row, merges in memory, and overwrites the whole JSONB column.
- **Action:** Marked `[x] [Review][Defer]` in `11-1-telegram-notification-foundation.md`.
- **Reason / when to revisit:** Resolving this correctly requires either `SELECT FOR UPDATE` on the user row or an optimistic lock on `updated_at` so overlapping patches merge against the latest value atomically. This is a real correctness issue but is out of scope for the foundation story; it should be picked up when notification preferences expand beyond a single top-level key or when the endpoint is exposed to higher concurrency (e.g., user-facing automation toggles from multiple devices).

## Deferred from: code review of 10-1-batdongsan-scraper (2026-08-03) — RESOLVED

- **Finding:** `ScrapeOutput.cost_micros` is set to 0 for degraded runs in `batdongsan.scrape/executor.py`, but `charge_capability` in `app/capabilities/core/billing.py` still debited the wallet via `_charge_platform_meter` when `output.billable_units > 0`, creating a mismatch between displayed cost and actual charge.
- **Action taken (2026-08-03):** Updated `_charge_platform_meter` in `app/capabilities/core/billing.py` to detect `output.degraded`, record a 0-cost `TokenUsage` audit row, and skip `service.charge`. This fix is cross-platform and applies to `batdongsan`, `muaban_bds`, and `chotot` platform scrapers.
- **Verification:** `ruff check app/capabilities/core/billing.py` ✅ / `pytest tests/unit/capabilities/test_billing.py -q` ✅ 63 passed / `pytest tests/unit/capabilities/batdongsan ...` ✅ 44 passed.
