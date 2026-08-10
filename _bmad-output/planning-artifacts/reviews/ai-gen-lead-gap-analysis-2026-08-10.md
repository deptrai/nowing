# Gap Analysis: Nowing chuyển sang AI gen lead / lead intelligence

**Date:** 2026-08-10  
**Author:** Mary (Business Analyst)  
**Scope:** PRD, Architecture Spine, Epics, UX contracts, market/technical/domain research  
**Status:** P0/P1 governance and doc-sync items closed by SCP `sprint-change-proposal-nowing-ai-gen-lead-positioning-2026-08-10.md` (ADOPTED 2026-08-10). P2 implementation gates remain open; Epic 21 is NOT ready for dev until those close.

---

## Executive Summary

PRD and Epics have been updated to add **Epic 21 — Lead Gen Intelligence** with 7 new FRs (FR-63..FR-69) and the `ARCHITECTURE-SPINE.md` now contains AD-36..AD-42 for signal detection, scoring, enrichment, sequencing, CRM, Zalo, and outcome-based pricing. UX work is partially covered by `ux-contract-lead-intelligence-panel.md` and `epic21-lead-intelligence-ux.md`.

However, **downstream strategic documents (product definition, business plan, GTM, marketing plan, 3-year roadmap, domain expansion research) remain in the pre-2026-08-10 state** and continue to describe a "knowledge intelligence / research memory" positioning. This creates severe conflicts on target user, beachhead, pricing, PII/legal policy, and scraper/data strategy.

In addition, the positioning change appears to have been applied inside the PRD without a visible Sprint Change Proposal (SCP) while §2.4 explicitly freezes positioning until 2026-08-24. FR-65 and FR-69 also appear to violate Non-Goal NG-1 ("do not sell research data") unless a documented exception is approved.

The Implementation Readiness Reports (final and v2) declare "READY", but the underlying gaps show that readiness is premature.

---

## Source-of-truth files reviewed

| File | Path | Note |
|------|------|------|
| PRD | `planning-artifacts/prds/prd-Nowing-2026-07-22/prd.md` | Lines 12, 17-18, 31-42, 63-72, 118-123, 158-167, 286-343, 543-998, 981-998 |
| Epics | `planning-artifacts/epics.md` | Lines 38-54, 1425-1540, 1542-1634, 2439-2528 |
| Architecture Spine | `planning-artifacts/architecture/architecture-Nowing-2026-07-22/ARCHITECTURE-SPINE.md` | Lines 34-76, 663-667, 1013-1159, 1163-1179 |
| Epic 21 architecture draft | `planning-artifacts/architecture/epic21-architecture-update.md` | Lines 1-20, 26-100 |
| UX contract (panel) | `planning-artifacts/ux-designs/ux-Nowing-2026-07-22/ux-contract-lead-intelligence-panel.md` | Lines 1-6, 10-19, 50-56, 65-80, 128-136 |
| Epic 21 UX draft | `planning-artifacts/ux-design/epic21-lead-intelligence-ux.md` | Lines 1-6, 150-169, 213-237 |
| Product definition | `planning-artifacts/product-definition-nowing-2026-08-06.md` | Lines 17-31, 79-88, 105-113 |
| Business plan baseline | `planning-artifacts/business-plan-baseline-nowing-2026-08-04.md` | Lines 18-47, 55-59, 131-149 |
| GTM business plan | `planning-artifacts/gtm-business-plan-nowing-2026-08-04.md` | Lines 15-16, 21-31, 127-155, 160-169 |
| Marketing plan | `planning-artifacts/marketing-plan-nowing-2026-08-07.md` | Lines 32-34, 120-130 |
| 3-year roadmap | `planning-artifacts/research/nowing-3-year-roadmap-2026-08-06.md` | Lines 17-23, 29-34, 99-120 |
| Domain expansion research | `planning-artifacts/research/domain-expansion-research-report-2026-08-06.md` | Lines 36-47, 67-68 |
| Lead generation market research | `planning-artifacts/research/market-ai-lead-generation-market-research-2026-08-10.md` | Lines 770-784, 820-828 |
| HR vertical feature brief | `planning-artifacts/feature-brief-hr-vertical-vietnam-2026-08-05.md` | Lines 12-14, 29, 61 |
| TopCV / ITviec spike | `planning-artifacts/research/technical-spike-topcv-itviec-2026-08-05.md` | Lines 33-47, 123-124, 131-136, 149-159 |
| Implementation readiness (final) | `planning-artifacts/implementation-readiness/implementation-readiness-report-final-2026-08-10.md` | Lines 6-12, 62-66, 94-104, 110-112, 158-160 |
| Implementation readiness (v2) | `planning-artifacts/implementation-readiness/implementation-readiness-report-v2-2026-08-10.md` | Lines 61-72, 132-148, 154-155 |
| Extracted requirements | `planning-artifacts/prd-requirements-extracted-2026-08-08.md` | Date 2026-08-08; no FR-63..FR-69 entries |

---

## Conflicts and gaps (by severity)

### P0 — Governance / Strategy

#### 1. Positioning freeze 2026-08-24 appears breached without an SCP
- PRD line 12: "FREEZE POSITIONING tới 2026-08-24 (D4): §1 Vision · §2 Target User · §2.4 Non-Goals · §6 MVP Scope — đổi phải qua SCP mới."
- PRD lines 17-18 and 31-42: `§1.0 Lead Intelligence` and related notes were added 2026-08-10, changing Vision and Target User.
- No SCP for this positioning change was found in the planning-artifacts folder (the existing `sprint-change-proposal-2026-08-10.md` is about Epic 18, not lead gen).
- `business-plan-baseline-2026-08-04.md` line 18 and `gtm-business-plan-nowing-2026-08-04.md` line 15 also reference the same freeze date.
- **Gap:** Missing SCP to (a) lift the freeze, (b) approve the new positioning, (c) record the decision.

#### 2. Non-Goal NG-1 "do not sell research data" conflicts with FR-65 / FR-69
- PRD lines 158-167: NG-1 forbids selling research data as a product. The only allowed variant is "bán research output/deliverable đã cấu trúc cho một vertical cụ thể" but it is explicitly marked `chưa phê duyệt`.
- PRD lines 564-573 (FR-65): Enriched Contact Data — verified email/phone via waterfall providers.
- PRD lines 981-998 (FR-69): Outcome-Based Pricing — `$0.50/lead enriched` or `$50/meeting booked`.
- **Conflict:** Lead enrichment and pay-per-lead pricing are functionally selling structured contact/lead data. This requires a documented NG-1 exception or an amended Non-Goal.

#### 3. PII pipeline contradiction: HR vertical requires redaction; lead gen requires storage
- PRD lines 335-343 (FR-47) and Architecture Spine lines 663-667 (AD-25): job data must have phone/email/names redacted before memory.
- Architecture Spine lines 1013-1032 (AD-36) and `epic21-architecture-update.md` lines 41-43: `VerifiedContact` model stores `email`, `phone` for leads.
- **Conflict:** The same PII pipeline cannot both redact and persist contact data. A data-classification policy (job data vs. lead data, legal basis, consent) is missing.

#### 4. Zalo / LinkedIn strategy conflicts with domain-expansion research
- `domain-expansion-research-report-2026-08-06.md` lines 44-46: "Avoid: Facebook, Zalo, LinkedIn (high anti-bot + legal risk)."
- PRD lines 543-552 (FR-63 sources), 575-584 (FR-66 channels), 596-604 (FR-68 Zalo); Architecture Spine lines 1035-1054 (AD-37), 1077-1095 (AD-39), 1124-1139 (AD-41): Zalo and LinkedIn are selected as primary channels/signal sources.
- `market-ai-lead-generation-market-research-2026-08-10.md` lines 770-782: Zalo is described as a Vietnam market opportunity.
- **Conflict:** Two research files contradict each other. Legal/ToS review and an explicit exception/decision are required before build.

#### 5. Strategic/GTM documents have not been updated for lead gen
| Document | Conflict |
|---|---|
| `product-definition-nowing-2026-08-06.md` | "knowledge intelligence platform"; target users do not include sales/SDR (lines 17-31, 79-88). |
| `business-plan-baseline-nowing-2026-08-04.md` | Beachhead = AI agent builder + research team; revenue = cloud credit wallet; no outcome-based pricing (lines 18-47, 55-59). |
| `gtm-business-plan-nowing-2026-08-04.md` | Beachhead = agent builder → research team; revenue streams lack outcome pricing (lines 21-31, 127-155, 160-169). |
| `marketing-plan-nowing-2026-08-07.md` | Vision = "From data to knowing"; beachhead = Agent Builder → BDS → Researchers; no sales/SDR persona (lines 32-34, 120-130). |
| `nowing-3-year-roadmap-2026-08-06.md` | Year 1 = entity-centric model / 7 domains; no lead gen (lines 17-23, 29-34, 99-120). |
| `innovation-strategy-nowing-2026-08-04.md` | Research memory / open-core PLG; no lead gen (lines 11-22, 108-117). |

- **Gap:** If lead intelligence is the new direction, these downstream documents must be updated or superseded to avoid contradictory execution.

---

### P1 — Architecture / Epics / UX

#### 6. Epic 21 architecture draft is marked DRAFT/needs review but was merged into the Spine as ADOPTED
- `epic21-architecture-update.md` lines 1-7: "DRAFT — Cần review bởi Luisphan"; assumptions must be confirmed before merge.
- `epic21-architecture-update.md` lines 12-20: AD-36..AD-42 are tagged `[ASSUMPTION]` (Cleanlist/BetterContact, daily monitoring, weighted scoring, email/LinkedIn/Zalo, read-first CRM, Zalo OA, pay-per-meeting).
- `ARCHITECTURE-SPINE.md` lines 1013-1159: AD-36..AD-42 are tagged `[ADOPTED 2026-08-10]`.
- **Conflict:** The Spine says decisions are adopted while the source draft still says they are unvalidated assumptions. Reconcile or validate assumptions before calling them adopted.

#### 7. Implementation readiness reports are premature and inconsistent
- `implementation-readiness-report-final-2026-08-10.md` lines 6-12 and 158-160: declares "READY — All checks passed".
- `implementation-readiness-report-v2-2026-08-10.md` lines 61-72 and 154-155: also declares "READY" but says "7 missing FRs (Epic 21) represent a clear roadmap" and "Next Step: Add Epic 21 to epics.md", even though `epics.md` already contains Epic 21 (lines 2439-2528).
- **Conflict:** The reports ignore the unresolved assumptions, the PII conflict, the positioning freeze, and the stale strategic docs. They should not be considered authoritative until these are closed.

#### 8. CRM sync scope mismatch
- PRD lines 586-594 (FR-67): "sync bidirectionally" immediately.
- Architecture Spine lines 1099-1120 (AD-40): Phase 1 read-only dedup, Phase 2 write-back, Phase 3 bidirectional sync.
- **Conflict:** PRD and Architecture disagree on CRM sync scope.

#### 9. Epic 13 was dropped but its stories remain in `epics.md`
- `epics.md` lines 1542-1546: Epic 13 `Canonical Entity Storage & Multi-Domain Indexing [DROPPED 2026-08-08]`.
- `epics.md` lines 1551-1634: Stories 13.1, 13.2a-e, 13.3 are still present with detailed AC.
- **Gap:** Leftover stories can be misread as active work. Move to archive or remove.

#### 10. Epic 21 UX is not fully merged into canonical UX contracts
- `epic21-lead-intelligence-ux.md` lines 1-6: status "Draft — Ready for review".
- `ux-contract-lead-intelligence-panel.md` exists in the canonical UX folder but lacks Zalo OA flows and outcome-pricing display.
- `implementation-readiness-report-v2-2026-08-10.md` lines 61-72: reports 14 UX contracts aligned, but Epic 21 UX is not merged.
- **Gap:** Lead intelligence UX is not a fully integrated canonical contract.

#### 11. `prd-requirements-extracted-2026-08-08.md` is stale
- File date is 2026-08-08; FR-63..FR-69 were added 2026-08-10.
- Grep found no entries for FR-63..FR-69 in the extracted file.
- **Gap:** This extracted requirement list does not match the canonical PRD and can mislead implementation or traceability.

---

### P2 — Technical / Detail

#### 12. AD model definitions are inconsistent between draft and Spine
- `epic21-architecture-update.md` line 61: `SignalEvent` has `company_id`; line 66 (and Spine line 1047): `SignalEvent` has `workspace_id, company_name`.
- `epic21-architecture-update.md` line 85: `LeadScore` has `lead_id`; Spine line 1071: `LeadScore` has `workspace_id, company_name`.
- **Gap:** Schema must be unified before implementation.

#### 13. TopCV anti-bot and ITviec salary data quality are unblocked
- `technical-spike-topcv-itviec-2026-08-05.md` lines 33-47: TopCV returns Cloudflare "Just a moment..." challenge (HTTP 403); requires headless browser / residential proxy / bypass POC.
- Same file lines 123-124: ITviec hides salary ("Sign in to view salary"), creating data quality risk.
- Same file lines 131-136, 149-159: recommendation is "POC first" for TopCV and "Build" for ITviec with salary caveat.
- **Gap:** TopCV cannot be built until anti-bot POC passes; ITviec salary model needs a confidence/low-confidence strategy.

#### 14. Data strategy may be exceeded
- `product-definition-nowing-2026-08-06.md` lines 105-113 and PRD lines 63-72: built-in scrapers limited to 30-50 max; expansion via OAuth connectors and ChainLens.
- Lead gen plus domain expansion could push beyond 30-50 built-in scrapers if not carefully scoped.
- **Gap:** Need a scraper count/budget gate for new lead-gen sources.

#### 15. HR vertical vs. lead gen positioning ambiguity
- `feature-brief-hr-vertical-vietnam-2026-08-05.md` lines 12-14, 29, 61: HR pilot is "not a new product line or pivot".
- `epics.md` lines 2439-2443: Epic 21 says "Nowing chuyển từ 'research tool' sang 'lead intelligence platform'".
- **Gap:** Need a single narrative: is lead gen a pivot, a vertical, or a use-case pilot?

---

## Recommended next steps

### Immediate (P0)

1. **Create a Sprint Change Proposal (SCP)** for the 2026-08-10 positioning change. It must decide:
   - Is lead gen a pivot, vertical expansion, or pilot use case?
   - Is the primary beachhead now sales/SDR or still agent-builder/research team?
   - Does NG-1 get an exception for structured lead-enrichment deliverables, or is FR-65/FR-69 re-scoped?
   - Is the positioning freeze lifted, superseded, or amended?
2. **Legal/compliance review** for:
   - Selling verified contact data / pay-per-lead (FR-65, FR-69) against NG-1.
   - Zalo OA, LinkedIn automation/scraping against ToS and Decree 356.
   - VietnamWorks/TopCV/ITviec ToS and PII handling.
3. **Separate PII policy** for HR redaction vs. lead-gen enrichment with documented legal basis and consent model.
4. **Halt "READY" declarations** in implementation-readiness reports until assumptions are validated and strategic docs are synced.

### Short-term (P1)

5. **Sync downstream strategy docs** (product-definition, business-plan, GTM, marketing, roadmap, innovation strategy, domain expansion research) with the lead intelligence positioning, target user, and outcome-based pricing.
6. **Reconcile Epic 21 architecture**: validate assumptions, remove `[ASSUMPTION]` tags or keep them as open risks, and delete/merge `epic21-architecture-update.md` draft into the Spine.
7. **Unify AD model schemas**: `SignalEvent`, `LeadScore`, `VerifiedContact`.
8. **Align CRM sync scope**: change FR-67 or AD-40 so they match (read-first vs. bidirectional).
9. **Merge Epic 21 UX** into canonical UX contracts and add Zalo OA / outcome-pricing screens.
10. **Update `prd-requirements-extracted-2026-08-08.md`** to include FR-63..FR-69 or mark it `[stale]`.
11. **Archive Epic 13 leftover stories** in `epics.md`.

### Follow-up (P2)

12. Close TopCV anti-bot POC and ITviec salary strategy.
13. Enforce scraper count budget; prioritize ChainLens / external APIs / OAuth for lead-gen sources.
14. Consolidate the two conflicting implementation-readiness reports into one canonical version.

---

## Bottom line

Lead intelligence has been added to the PRD and Architecture. **P0/P1 governance and doc-sync items are now closed** by SCP `sprint-change-proposal-nowing-ai-gen-lead-positioning-2026-08-10.md`. However, the change is **still not safe to implement** until P2 gates close:
- TopCV anti-bot POC (or decision to drop TopCV from P0).
- ITviec salary low-confidence strategy.
- Scraper count budget for new lead-gen sources.
- Vendor contracts, legal/ToS review, Zalo OA business verification, and PII/consent pipeline design for Epic 21.
- Consolidation of readiness reports is complete (`implementation-readiness-report-final-2026-08-10.md` is canonical).

Close the P2 implementation gates before declaring Epic 21 ready for dev.
