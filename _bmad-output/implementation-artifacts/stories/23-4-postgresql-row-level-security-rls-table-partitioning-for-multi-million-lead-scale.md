---
story_key: 23-4-postgresql-row-level-security-rls-table-partitioning-for-mul
status: done
epic: 23
---

# Story 23.4: PostgreSQL Row-Level Security (RLS) & Table Partitioning for Multi-Million Lead Scale

**Status:** `done`  
**Epic:** Epic 23 — Lead Capture & Outreach Infrastructure

## Story

As a platform operator,  
I want the leads database to support millions of rows across multi-tenant workspaces with sub-10ms query latency and strict tenant isolation,  
so that performance and security scale independently.

## Acceptance Criteria

- **Given** a database connection with tenant session variable set to `app.current_workspace_id = '1'`, **When** executing `SELECT * FROM leads`, **Then** PostgreSQL engine-level RLS strictly filters out rows belonging to any other `workspace_id`, even in raw SQL queries.
- **Given** a partitioned `leads` table containing over 5,000,000 records, **When** executing workspace-scoped filter and search queries, **Then** `EXPLAIN ANALYZE` confirms partition pruning eliminates unneeded partitions, maintaining p95 response under 15ms.
- **Given** an active production database, **When** applying partition migration, **Then** shadow table creation, dual-write triggers, and batched backfill migrate records with zero table locking and zero downtime.

## Dev Notes

- Migration: `217_partition_leads_table_zero_downtime.py`
- 16 hash partitions: `leads_p0` .. `leads_p15` + `leads_default`
- Composite PK: `(id, workspace_id)`; composite FKs on `lead_scores`, `verified_contacts`, `zalo_message_logs`
- Zero-cache publication: `publish_via_partition_root = true`
- RLS: `FORCE ROW LEVEL SECURITY` with session context `app.current_workspace_id`

## Verification

- Migration: `217_partition_leads_table_zero_downtime.py`
- Tests: RLS isolation, partition pruning p95 latency, zero-downtime migration
