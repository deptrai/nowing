# Epic 21 Context: Lead Gen Intelligence & Social Graph

<!-- Compiled from planning artifacts. Edit freely. Regenerate with compile-epic-context if planning docs change. -->

## Goal

Build Nowing's central Lead Intelligence & CRM Hub that turns multi-source raw data into scored, contactable, compliant leads. The epic ingests signals and listings from BĐS, recruitment, procurement, e-commerce, Telegram, and social channels (via XActions), extracts and verifies contact information, classifies commercial intent, computes fit/intent scores, and triggers multi-channel outbound automation. The epic is in-progress: stories 21.1–21.20 are complete, and 21.21 (deterministic confidence gate + selective micro-LLM fallback) is the active ready-for-dev slice.

## Stories

- Story 21.1: Intent Signal Detection
- Story 21.2: Lead Scoring & Prioritization
- Story 21.3: Vietnam Phone & Contact Waterfall Engine
- Story 21.4: Outbound Prospecting Automation & Panel
- Story 21.5: CRM Integration & Lark Base / Google Sheets 1-Click Sync
- Story 21.6: Vietnam Outbound Automation (Zalo OA & Telegram Sender)
- Story 21.7: Outcome-Based Pricing & Transparent Credit Ledger
- Story 21.8: Social Ingress via XActions Integration
- Story 21.9: Executive Decision Maker Mapping & B2B Lead Outreach
- Story 21.10: 1-Click Reverse-ICP from Website / Project URL
- Story 21.11: Actionable Turn Dispatches (Suggested Action Pills)
- Story 21.12: Viral Social Outbound Co-pilot
- Story 21.13: Multi-Table Tabs & Send/Export Hub
- Story 21.14: Smart Whitelist & Do-Not-Call (DNC) Compliance Engine
- Story 21.15: Unified Multi-Source AI Lead Generation Orchestrator
- Story 21.16: Nowing Split-View Canvas & Workspace Modernization
- Story 21.17: Complete Origami Landing Page & Public Site Transformation
- Story 21.18: Partners Affiliate Portal & $0 Pricing Page Deployment
- Story 21.19: Lead Source Adapter Live Data Integration & Persistence
- Story 21.20: Extend Multi-Source Lead Gen Adapters
- Story 21.21: Deterministic Confidence Gate & Selective Micro-LLM Fallback Worker

## Requirements & Constraints

- The lead CRM ingests from any workspace-connected scraper or social source, normalizes records to a canonical `Lead`, and deduplicates by blind HMAC of phone/email/domain.
- Contact PII is encrypted at rest in `verified_contacts`, masked in the UI, and audited on every access. Unlock costs 1.5 credits, debited only after successful decryption.
- Vietnam phone resolution uses a 3-tier waterfall (Batdongsan/Muaban token pool → Chotot mobile API → carrier/Zalo verification) with a 90s timeout and circuit breaker. Dead-number reports are auto-refunded within 24h, capped at 15% of unlocked leads per billing cycle.
- DNC/whitelist rules block outreach and unlock attempts. Opt-out requests are honored within 24h; PII is deleted or irreversibly anonymized per Vietnamese Decree 13/2023/NĐ-CP and Decree 91/2020/NĐ-CP.
- Lead scoring produces a composite 0–100 score (50% fit, 50% intent) with Hot/Warm/Cold badges and a rule-based fallback when vector search is unavailable.
- Outbound sequences live in a separate bounded context (`Sequence`, `SequenceStep`, `SequenceEnrollment`, `SequenceEvent`, `SequenceRun`), not the `Automation` tables. MVP is email-only; Zalo and LinkedIn senders are deferred.
- CRM sync is read-first and deduplicated before write-back, supporting HubSpot, Salesforce, Lark Base, Google Sheets, and local Vietnamese CRMs via webhooks.
- Core operations (chat, table transforms, sequence creation, CSV export) are $0. Billable events are verified contact unlocks, deep-research dossiers, and qualified meetings booked.
- Multi-source lead generation decomposes natural-language prompts, runs relevant `LeadSourceAdapter`s concurrently, deduplicates and persists results, and streams rows live to the lead matrix.
- Deterministic parsing (regex, lxml, Pydantic) is the first pass. Records with completeness < 0.70 (or missing phone/price/district) go to a selective micro-LLM fallback; output is re-validated and merged only into missing fields. Target: ≥85% of records bypass LLM and total spend is < 4,000 tokens per 100-record batch.
- Signals write a `SignalEvent` and a `Memory` row tagged `lead_signal`, reuse `AlertRule` for notifications and sequence triggers, and are metered as a capability.

## Technical Decisions

- Epic 21 tables use UUID `id`, `workspace_id`, and `client_id`.
- Contact deduplication and DNC checks use a canonical HMAC input (`phone|email|domain`); `value_hmac` is `NOT NULL` and `UNIQUE` per workspace.
- Bulk lead ingestion is at `POST /api/v1/workspaces/:workspace_id/leads/batch-ingest` (50–100 items, 30 batches/min). SQL upserts sort by `value_hmac` before `ON CONFLICT DO UPDATE` to avoid deadlocks.
- The `leads` table is published via `zero_publication` for Zero-Cache CDC, but PII-derived columns are excluded; `chunks` is also excluded.
- Business events (contact unlock, scoring, signal scan, email send, meetings, enrichments) write to `BillingEvent`; `TokenUsage` is for LLM consumption only.
- `LeadSourceAdapter` contract is `search_leads`, `normalize_lead`, and `extract_contact_candidates`. Adapter selection is driven by `CapabilityRegistry` and the prompt's buy/sell intent.
- Signal-to-sequence triggers are `AlertRule` templates with a registered signal `capability_id`.
- Phone/email unlock is one atomic transaction: decrypt, set `is_unlocked=true`, debit wallet, write `BillingEvent`, and log audit.
- The micro-LLM fallback (Story 21.21) uses Tier 1 models only, sends ≤200 input tokens per extraction, micro-batches 5–10 snippets, and falls back to `needs_enrichment=true` on timeout or 429.

## UX & Interaction Patterns

- Workspace is a resizable 2-panel split view: 340px chat co-pilot on the left and a dynamic lead table canvas on the right. The divider can be dragged; double-click resets to 340px.
- The lead matrix supports multi-table tabs, filter chips, live Zero-Cache row insertion, and an export hub (CSV, Lark Base, Google Sheets, share link).
- Clicking a lead opens a flyout with enrichment history, fit-score breakdown, and 1-click Zalo/phone actions.
- Suggested action pills (max 3) appear below assistant turns, each carrying an action type, prompt template, and credit cost. Clicking one dispatches the action immediately.
- Contact unlock is two-tier: a smart confirmation popover on first unlock (masked preview, 1.5 credit cost), then a session-level 1-click fast-unlock toggle.
- Lead rows without a phone show a primary "Mở khóa SĐT" action; successful unlock updates the row in place.
- Visual design uses an Emerald/Mint palette, Sọc Caro grid-paper background, fit-score color tiers, and per-lead cost indicators.

## Cross-Story Dependencies

- 21.1 (signals) feeds 21.2 (scoring) and 21.4/21.11 (outbound triggers and action pills).
- 21.15/21.19/21.20 (multi-source adapters) feed 21.3 (phone waterfall), 21.4 (outbound), and 21.5 (CRM sync).
- 21.7 (outcome pricing) depends on billing events from 21.3, 21.4, and 21.6.
- 21.13/21.16 (tables and split-view UI) depend on 21.15/21.19 live data and 21.3 unlock state.
- 21.21 enriches adapter output upstream and feeds back into `LeadGenOrchestrator` without changing its interface.
- Epic 21 relies on the XActions social integration and LinkedIn B2B architecture for data, and on Epic 23 infrastructure for high-volume execution.
- Lead data uses a separate PII/consent pipeline from HR/job data (Epic 12) and must not reuse Epic 12 redacted contact data.
