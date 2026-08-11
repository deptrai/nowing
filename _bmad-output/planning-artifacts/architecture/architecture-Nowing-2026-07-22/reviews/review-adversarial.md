# Adversarial Review — Epic 21 Lead Intelligence (post-2026-08-11 final update)

**Date:** 2026-08-11
**Artifacts reviewed:**
- `/Users/luisphan/Documents/GitHub/nowing/_bmad-output/planning-artifacts/architecture/architecture-Nowing-2026-07-22/ARCHITECTURE-SPINE.md`
- `/Users/luisphan/Documents/GitHub/nowing/_bmad-output/planning-artifacts/implementation-artifacts/epic21-engineering-handoff-2026-08-11.md`
- `/Users/luisphan/Documents/GitHub/nowing/_bmad-output/planning-artifacts/ux-designs/ux-Nowing-2026-07-22/ux-contract-lead-intelligence-panel.md`

**Scope:** Literal-but-incompatible seams in the five target categories. Implementation-only gaps (missing Alembic migrations, unbuilt Epic 21 tables, `client_id` CITEXT migration) are ignored as expected for a backlog epic.

## Verdict

🟢 **PASS with implementation conditions**

All five literal-but-incompatible seams identified in earlier review rounds are now closed at the architecture, UX-contract, and call-site levels.

## Five-target seam status

| # | Category | Verdict |
|---|----------|---------|
| 1 | `AlertRule` columns (`target` JSONB vs `target_sequence_id`/`target_step_id` FKs, `client_id` Text vs CITEXT) | **CLOSED** — `target_sequence_id` (FK to `Sequence.id`) and `target_step_id` (FK to `SequenceStep.id`, nullable) are real columns; `client_id` is `CITEXT | null` in AD-33 and AD-43. |
| 2 | `Sequence`/`SequenceRun`/`SequenceEnrollment` model shape and `client_id` ownership | **CLOSED** — client-scoped `Sequence`s require matching rule `client_id`; shared `Sequence`s (`shared=true`, `client_id IS NULL`) may be targeted by any `AlertRule`, but the matched `Lead.client_id` must equal the rule's `client_id` (or rule is workspace-global). `SequenceRun`/`SequenceEnrollment` `client_id` is always the matched `Lead.client_id`; `triggering_lead_id` / `triggering_alert_rule_id` are present. |
| 3 | `Capability` identifier/metadata and lead-source picker data source | **CLOSED** — `Capability.name` is canonical; `Capability.metadata` is the sole metadata store; `CapabilityRegistry.query_metadata(key)` and `query_metadata_for(name, key)` are canonical. Lead-source dropdown and source-specific tabs both query the workspace-scoped `LeadSource` cache; `CapabilityRegistry` is only used for optional display metadata. |
| 4 | `Memory` provenance authority (`source_uuid` vs `source_run_id`) | **CLOSED** — `Memory.source_uuid` + `source_entity_type` are the authoritative source pointer for Epic 21 UUID entities; `source_run_id` is only for `Run` audit context. `MemorySourceType` is extended. |
| 5 | `VerifiedContact` redaction and consent authority | **CLOSED** — raw PII stays in `VerifiedContact` encrypted at rest; `redact_pii(..., context='lead_enrichment')` applies to `Memory`, `Chunk[]`, logs, and non-privileged UI. `VerifiedContact.consent_status`/`legal_basis` are the authoritative first-outreach gate. |

## Implementation conditions (not architecture seams)

- Create Alembic migration for `Memory.source_uuid`/`source_entity_type` and `MemorySourceType` extension.
- Create Alembic migration for existing `client_id: Text` → `CITEXT` on `Memory`, `Run`, `TokenUsage`, `ResearchThread`, `PersonalAccessToken`, `NewChatThread` per AD-45.
- Wire `MemoryRepository.create_memory` / `update_memory` to accept `source_uuid`/`source_entity_type`.
- Build Epic 21 tables and `lead_extractor` capability; close business/legal gates.
