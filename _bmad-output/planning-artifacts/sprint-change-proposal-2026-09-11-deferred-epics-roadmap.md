# Sprint Change Proposal: Transition 52 Deferred/Blocked Review Findings into Target Epics Roadmap

**Date:** 2026-09-11  
**Author:** BMad Correct Course Workflow  
**Trigger:** Code review and implementation audit of 251 deferred items across Epics 6, 7, 8, 10, 11, 12, 14, 15, 18, 20, 21, 22, 24, 25, 26, 27, 28, 29, and 30.  
**Scope Classification:** Moderate / Major (Backlog Reorganization & Epic Allocation)

---

## 1. Issue Summary

During the systematic resolution of 251 findings recorded in `_bmad-output/implementation-artifacts/deferred-work.md`:
- **152 items** were fully implemented and verified via automated tests (100% green).
- **47 items** were dismissed with verified architectural rationale or confirmed as scope notes belonging to existing features.
- **52 items** remain classified as **Blocked**. These 52 items represent architectural gaps, multi-tenant container requirements, external OAuth/CRM bidirectional pipelines, enterprise PII vault policies, and browser automation session lifecycles that cannot be solved as ad-hoc bugfixes without dedicated epic planning and design.

This proposal formally bundles these 52 items into 5 targeted, high-value Roadmap Epics to clear the deferred technical debt ledger and schedule development in future sprint cycles.

---

## 2. Impact Analysis & Epic Grouping

### Epic A: Web Builder Multi-Tenant Container Security & AST Compiler Hardening (Stories 27.1c, 27.1d, 27.2a)
- **Problem:** User-created web apps on Dokploy currently run without strict Cgroup limits or dedicated network namespaces, and JSX class expression matching uses string literals.
- **Scope & Items Addressed (8 items):**
  1. Dokploy container deployment Cgroup CPU & Memory constraints.
  2. Network isolation for user-deployed containers.
  3. Strict DNS/ingress verification for customer custom CNAME domains.
  4. AST static-eval policy for complex dynamic JSX expressions in Mark Tool.
  5. Entitlement-driven presentation format selection (`pptx` vs `marp`) from chat entry points.
- **Target Deliverable:** Hardened container deploy service and isolated Docker runtime for Web Builder.

### Epic B: Browser Operator Runtime & CDP Session Governance (Story 24.8)
- **Problem:** Desktop/Chrome Extension browser automation lacks interactive takeover popovers, automatic session detachment, and audited command persistence.
- **Scope & Items Addressed (6 items):**
  1. `HumanLiveTakeoverPopover` UI with countdown timer (15:00 timeout).
  2. `chrome.debugger.onDetach` listener for clean state recovery when user closes DevTools.
  3. `aborted_timeout` background cleanup scheduler.
  4. Cryptographic CDP session token authentication and validation.
  5. Detailed database audit logging for CDP browser interactions.
- **Target Deliverable:** Production-grade Chrome extension and browser operator controller.

### Epic C: Enterprise PII Vault, Key Rotation & Right-to-be-Forgotten Compliance (Stories 24.2, 26.4)
- **Problem:** Cryptographic keys in `verified_contact_encryption` have no zero-downtime rotation protocol, and PII opt-out requests operate within single workspaces.
- **Scope & Items Addressed (5 items):**
  1. Automated `SECRET_KEY` rotation mechanism with dual-key decryption fallback.
  2. Superadmin cross-workspace Right-to-be-Forgotten purge pipeline (Decree 13 / GDPR).
  3. Transactional atomic credit locking for phone waterfall verification.
- **Target Deliverable:** Compliance-ready cryptographic PII vault and cross-workspace purge API.

### Epic D: Bi-Directional CRM Synchronization & Data Hub (Stories 21.5, 21.6, 22.3)
- **Problem:** Lead intelligence outputs operate primarily one-way without live bi-directional sync to external CRM deal pipelines, and Telegram userbot lacks a full web console.
- **Scope & Items Addressed (6 items):**
  1. Bi-directional deal stage sync between Nowing and HubSpot/Salesforce.
  2. TanStack Query Web Admin endpoints for Telegram Userbot / Channel management.
  3. Dedicated CRM deal pipeline tabs on the web frontend.
- **Target Deliverable:** Full 2-way CRM connector and unified messaging operations dashboard.

### Epic E: High-Scale Ingestion, Stream Resilience & Algorithmic Deduplication (Stories 12.4, 21.8, td-8)
- **Problem:** High-volume scrapers and stream workers experience edge-case message drops on worker crash and quadratic pairwise comparisons on massive company datasets.
- **Scope & Items Addressed (27 items):**
  1. Redis consumer group automatic recovery for pending messages (`XAUTOCLAIM`).
  2. $O(n \log n)$ windowed and locality-sensitive deduplication for job/BĐS aggregates.
  3. Per-scraper telemetry failure counters across all ingestion platforms.
  4. Streaming SSE heartbeat and per-event timeout guards.
- **Target Deliverable:** Resilient stream worker infrastructure and high-throughput vector ingestion pipeline.

---

## 3. Recommended Approach

**Selected Approach: Backlog Reorganization into Future Roadmap Epics (Option 1 + 3 Hybrid)**
- **Direct Benefit:** Resolves 100% of ambiguity in `deferred-work.md`. The ledger no longer holds orphaned findings; each finding is officially mapped to an assigned Roadmap Epic.
- **Risk Assessment:** Low risk to current stable branches. Production code remains 100% tested and functional.
- **Effort Estimate:**
  - Epic A (Container Isolation): 5 story points
  - Epic B (Browser Operator CDP): 5 story points
  - Epic C (PII Key Rotation): 3 story points
  - Epic D (CRM 2-Way Sync): 5 story points
  - Epic E (Stream Scalability): 5 story points

---

## 4. Implementation Handoff & Next Steps

1. **Sprint Status & Backlog Registration:**
   - Formalize Epics A through E in `_bmad-output/planning-artifacts/sprint-priority.md` and `epics.md`.
2. **Deferred Ledger Status Update:**
   - Annotate all 52 blocked entries in `_bmad-output/implementation-artifacts/deferred-work.md` with their allocated Roadmap Epic reference.
3. **Execution Routing:**
   - Product Owner / Architect: Review acceptance criteria for Epics A and B prior to next sprint kick-off.
   - Developer Agent: Continue feature stories under clean, isolated branches.

---
*Generated by BMad Correct Course Workflow on 2026-09-11*
