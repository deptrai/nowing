# Story 13.2d: PII-Safe Canonicalization

**Status:** done
**Epic:** Epic 13 — Canonical Entity Storage & Multi-Domain Indexing
**Priority:** P0

## Story

As a user,
I want canonical data and merge history to be free of PII,
So that personal data never leaks into search, history, or logs.

## Acceptance Criteria

- **Dependency:** Story 13.1; blocks enabling either persistence path.
- **Given** BDS or Jobs data contains PII, **Before** writing canonical data, source snapshots, outbox payloads or merge history, **Then** AD-25-compatible redaction runs for every domain.
- **Given** BDS exposes `contact`/`phone_key` or Jobs exposes JD text, **Then** raw values never enter golden records or history; a one-way keyed digest may be retained only when required for matching.
- **Given** logs and metrics, **Then** they contain counts/status only, never raw PII values.

## Validation

- Unit tests: `test_canonical_pii_redaction.py` for BDS and Jobs domains.
- Integration tests: `test_canonical_data_no_pii.py`, `test_merge_history_no_pii.py`, `test_outbox_no_pii.py`.
- Playwright MCP smoke: dashboard loads after changes.

## Tags

AD-25, PII, canonical, redaction, privacy
