-- G5 helper: disable document auto-archiving for all workspaces before deploy.
--
-- Migration 176 adds `auto_archive_enabled` (default FALSE) and a daily cron
-- `apply_document_retention_policies` that archives/deletes old documents based on
-- `document_retention_days` + `document_retention_action`.
--
-- Run this on the target database to ensure NO workspace starts auto-archiving
-- immediately after deploy. Keep `document_retention_days`/`document_retention_action`
-- for future UI enablement.
--
-- Review the list first:
--   SELECT id, name, document_retention_days, document_retention_action
--   FROM workspaces WHERE auto_archive_enabled = TRUE;
--
-- Then disable:

BEGIN;

UPDATE workspaces
SET auto_archive_enabled = FALSE
WHERE auto_archive_enabled = TRUE;

COMMIT;
