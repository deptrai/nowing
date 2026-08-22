# E2E Verification — Story 16.1 masothue.com Company Data (2026-08-22)

## Summary
Re-verified Story 16.1 after `sprint-status.yaml` flagged it `in-progress` for missing masothue.scrape capability/billing + mutation retest.

## Findings & Fixes
- **Scraper empty-page logic regression:** `app/proprietary/platforms/masothue/scraper.py` degraded on *any* empty page, including page 2+ of a multi-page search. Fixed so that:
  - Page 1 empty → `degraded=true`, `degradation_reason="empty"`.
  - Page > 1 empty → clean stop, `degraded=false`.
- **Alembic head conflict:** Two migrations both claimed revision `226`:
  - `226_add_telegram_checkpoint_messages_table.py`
  - `226_add_verified_contact_external_chat_ids.py`
  Renamed the second to `227_add_verified_contact_external_chat_ids.py` and created `f984b591d763_merge_multiple_heads.py` to merge heads `193_add_playbook_is_approved`, `c610f68d47fb`, and `227`.

## Verification Results
| Check | Command | Result |
|---|---|---|
| Unit + integration masothue tests | `pytest tests/unit/platforms/masothue tests/unit/capabilities/masothue/scrape tests/unit/services/company_aggregator tests/integration/capabilities/masothue/scrape/test_masothue_scrape.py -q` | 128 passed, 1 skipped |
| Live masothue smoke | `SCRAPE_LIVE=1 pytest ... -k live` | PASSED |
| MCP selfcheck | `uv run python -m mcp_server.selfcheck` | 65 tools OK |
| Backend lint | `ruff check app/proprietary/platforms/masothue app/capabilities/masothue app/services/company_aggregator` | All checks passed |
| Alembic migration | `DATABASE_URL=... alembic upgrade head` | OK |

## Status
- `16-1` in `sprint-status.yaml` updated to `done`.
- Story file `16-1-masothue-company-data.md` Change Log updated.
