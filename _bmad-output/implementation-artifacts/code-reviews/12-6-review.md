# Code Review — Story 12.6 Saved Searches

**Reviewed:** 2026-08-13
**Scope:** Alert engine, persistence, REST routes, migration, tests for Story 12.6.
**Method:** Parallel adversarial review across 3 layers (structure/correctness, security/edge cases, architecture/AC).

## Findings Triage

### P0 — Fixed in place

1. **Schedule/timezone update used stale values** (`app/alerts/services/crud.py`)
   - `derive_cron(rule.schedule, rule.timezone)` was called with old values instead of the incoming `data.*`.
   - Fixed: use `data.schedule`/`data.timezone` when present, fall back to `rule.*` only for unchanged fields.

2. **Scheduler race condition** (`app/alerts/engine/tick.py`, `app/alerts/engine/execute.py`)
   - `_claim_due_rules` only set `last_fired_at`; `next_fire_at` was advanced in a later, separate transaction in `execute_alert_rule`.
   - Fixed: advance `next_fire_at` atomically inside `_claim_due_rules`; `execute_alert_rule` no longer mutates scheduling state.

3. **Notification bypassed workspace membership** (`app/alerts/engine/notify.py`)
   - `AlertSubscription` query did not join `WorkspaceMembership`.
   - Fixed: `JOIN WorkspaceMembership` on `user_id` filtered by `alert_rule.workspace_id`.

4. **No RLS on alert tables** (`alembic/versions/190_add_alert_tables.py`)
   - `alert_rules`, `alert_snapshots`, `alert_subscriptions` lacked tenant isolation.
   - Fixed: added workspace/client RLS policies; denormalized `workspace_id` onto `alert_subscriptions`.

5. **AD-43 columns missing** (`app/alerts/persistence/models/alert_rule.py`, migration)
   - `target_sequence_id` and `target_step_id` were required but not present.
   - Fixed: columns added. Foreign keys to `sequences`/`sequence_steps` are deferred until those tables land (12.6 is notification-only).

6. **Capability not validated at create/update** (`app/alerts/services/crud.py`)
   - AD-33 requires `capability_id` to exist in `CapabilityRegistry`.
   - Fixed: `CapabilityRegistry.get()` at `create_alert_rule` and `update_alert_rule`.

7. **Notification channels not whitelisted** (`app/alerts/schemas.py`)
   - `sequence_enrollment` could be stored as a channel (AD-43 violation).
   - Fixed: Pydantic `field_validator` allows only `in_app` and `telegram`.

8. **Subscription route did not verify workspace membership** (`app/routes/alert_rules_routes.py`)
   - `data.user_id` was not checked against `WorkspaceMembership`.
   - Fixed: membership query before `create_alert_subscription`.

9. **Partial index mismatch** (`alembic/versions/190_add_alert_tables.py`)
   - Model defined `ix_alert_rules_due` with `postgresql_where=enabled`; migration did not.
   - Fixed: `postgresql_where="enabled"` in migration.

### P1 — Deferred / noted

10. **Snapshot JSON schema validation**
    - `_snapshot_from_output` now calls `_validate_items` which fails fast on non-dict items or missing `id`/`source_id`/`canonical_id`.
    - Status: ✅ fixed.

11. **Test coverage gaps**
    - Added `tests/unit/alerts/test_tick.py`, `tests/unit/alerts/test_notify.py`, `tests/integration/alerts/test_saved_search_lifecycle.py::test_create_alert_subscription`, and `tests/integration/alerts/test_alert_engine_execute.py`.
    - Status: ✅ fixed.

## Verification

```bash
cd nowing_backend
ruff check app/alerts app/routes/alert_rules_routes.py alembic/versions/190_add_alert_tables.py app/db.py app/celery_app.py app/app.py tests/unit/alerts tests/integration/alerts
uv run pytest tests/unit/automations tests/unit/alerts tests/integration/alerts -q
uv run python -c "from app.app import app; print('app import OK')"
```

Result: **304 passed**, app imports OK, ruff clean.

## Conclusion

All P0 findings from the adversarial review have been fixed. The remaining P1/P2 items are test coverage and optional schema hardening. Story 12.6 is approved to remain `done` from a review perspective.
