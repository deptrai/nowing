# Architecture Validation Report — Nowing

**Date:** 2026-08-11
**Skill:** `bmad-architecture` (Validate intent)
**Artifact:** `ARCHITECTURE-SPINE.md` in `architecture-Nowing-2026-07-22/`
**Status:** ⚠️ **CONDITIONAL PASS / FAIL with conditions**
**offer_to_update:** true

---

## Executive Verdict

`ARCHITECTURE-SPINE.md` is a strong architecture contract for the brownfield core (E1–E11) but **has material gaps in the Epic 21 lead-intelligence ADs** and in the **Stack section version drift**. The new ADs reuse existing infrastructure (AD-3, AD-8, AD-10, AD-11, AD-33) in spirit, but literal implementation conflicts exist in data types, table boundaries, and source-of-truth ownership.

**Do not build Epic 21 against the current spine until these conflicts are resolved.**

---

## 1. Lint Findings

`lint_spine.py` found **27 findings**:

- **9 HIGH**
  - AD-17, AD-18, AD-19, AD-20 are missing the required `Rule` field.
  - AD-29, AD-30, AD-31, AD-32, AD-33 are non-monotonic (id order jumps after AD-35).
- **18 LOW**
  - Template placeholders remain (`{id}`, `{run_id}`, `{keyword}`, `{workspace_id}`) in Stack and AD sections.

### Action
1. Add explicit `Rule:` bullet to AD-17/18/19/20.
2. Renumber or explain AD-29–AD-33 ordering; do not renumber existing stable ADs unless all references are updated.
3. Replace placeholder tokens with concrete examples or remove them.

---

## 2. Reviewer 1 — Reality-Check

**Verdict:** ⚠️ **CONDITIONAL PASS**

**Top findings:**
1. **Stack version drift:** PostgreSQL 15+ vs docker `pg17`; Redis 7+ vs `redis:8-alpine`; FastAPI "latest stable" vs `pyproject.toml` `>=0.115.8`.
2. **"Latest" ambiguity:** 12 stack entries use "latest" without specific version ranges.
3. **Client stack inconsistency:** Browser extension uses React 18.2.0 and Node `>=18 <23`; desktop/web use React 19 / Node 20+.
4. **Excellent reality-checking in AD-16.1, AD-19, AD-20, and AD-DEFER cleanup.**
5. **Future ADs not code-verified:** AD-22/AD-23 and AD-36–AD-42 lack code evidence.

Full review: <ref_file file="/Users/luisphan/Documents/GitHub/nowing/_bmad-output/planning-artifacts/architecture/architecture-Nowing-2026-07-22/reviews/review-reality-check.md" />

---

## 3. Reviewer 2 — Adversarial

**Verdict:** 🔴 **FAIL with conditions**

**Top findings:**
1. **AD-39 cannot literally reuse Epic 6 Automation / E11.1 Notifications.** `Automation.trigger_type` has no `lead_enrollment`; action registry has no `send_email`/`wait`; `PlanStep` lacks `wait_duration`/`condition`/`channel`; `RunService` has no time-based wait; `TokenUsage.run_id` is UUID but `AutomationRun.id` is `int`; E11.1 has no `email_reply` channel.
2. **AD-25 collides with AD-11.1 on `Memory.source_input`.** One says immutable raw snapshot for re-validation; the other demands redaction before embedding/storage. Two teams will redact different copies.
3. **New Epic 21 tables bypass `client_id` boundary (AD-31).** `Lead`, `SignalEvent`, `VerifiedContact`, `Sequence`, `CrmConnection`, `OutcomeEvent`, etc. are defined without `client_id`, opening cross-vertical-client leakage.
4. **AD-36 / AD-38 / AD-42 overload `TokenUsage` / `User.credit_micros_balance`.** `TokenUsage` is typed as per-LLM-turn with UUID `run_id`; new ADs put `contact_enrichment`, `lead_scoring`, `outcome_*` events into it while `AutomationRun.id` is `int`.
5. **AD-33 / AD-37 / AD-39 have three-way ambiguity on signal-driven sequences.** `AlertRule` channels only `in_app`/`telegram`; no `capability_id` mapping for signal types; no `email_reply` channel or trigger type exists.

Full review: <ref_file file="/Users/luisphan/Documents/GitHub/nowing/_bmad-output/planning-artifacts/architecture/architecture-Nowing-2026-07-22/reviews/review-adversarial.md" />

---

## 4. Synthesized Critical Issues

| # | Issue | Severity | Owner AD(s) | Why it blocks Epic 21 |
|---|---|---|---|---|
| 1 | `TokenUsage` and `AutomationRun` id / type mismatch | **Critical** | AD-8, AD-10, AD-39, AD-42 | Cannot cost or attribute sequence/outcome events to existing wallet/ledger without schema change. |
| 2 | `Memory.source_input` redaction vs. immutability | **Critical** | AD-11.1, AD-25 | One team stores PII; another breaks re-validation. |
| 3 | `client_id` missing on new lead-gen tables | **High** | AD-31, AD-36–AD-42 | Vertical client isolation (public agent-chat) is undefined for lead data. |
| 4 | `Automation` / `AlertRule` cannot support sales sequences and signal triggers as written | **High** | AD-33, AD-37, AD-39 | Requires new action types, channels, trigger types, or a separate `Sequence` engine. |
| 5 | Stack version drift | **Medium** | Stack section | Mismatch between docs and `pyproject.toml` / `docker-compose`. |
| 6 | AD-17/18/19/20 missing `Rule` field; AD-29–33 non-monotonic | **Medium** | Spine structure | Fails `lint_spine.py`; may confuse readers and downstream code generation. |

---

## 5. Open Questions

1. Should Epic 21 be built as a **separate bounded context** with its own tables and a bridge to `Memory` / `TokenUsage`, or as an extension of existing Automation/Memory schema?
2. Should sales sequences be a new `Sequence` model that references `Automation` optionally, or must every sequence literally map to an `Automation` row?
3. Where is the single source of truth for lead/contact data: `Lead` table, `Memory`, or `chainlens-research` chunks?
4. How does `client_id` apply to new tables? Is it required on every lead-gen table, or is lead data workspace-scoped only?
5. Should `TokenUsage` be split into `TokenUsage` (LLM) and `BillingEvent` (business events), or should the schema be widened?

---

## 6. Recommendations

### Before Epic 21 dev starts:
1. **Resolve AD-39 vs. Epic 6 Automation.** Either (a) extend `Automation` schema with `lead_enrollment`, `send_email`, `wait` action types, time-based waits, and `email_reply` notification channel; or (b) admit `Sequence` is a new bounded context that *uses* `RunService`/Celery but not `Automation` schema literally.
2. **Clarify AD-25 + AD-11.1 data flow.** Define the canonical mutation path: `Run.output_text` (raw, short-term audit) → `redact_pii` → `Memory.content`/`Chunk[]` (redacted) → `Memory.source_input` (raw snapshot) for re-validation. State which copy is redacted and which is immutable.
3. **Add `client_id` decision.** Extend AD-31 to include `Lead`, `SignalEvent`, `VerifiedContact`, `EnrichmentRequest`, `Sequence*`, `CrmConnection`, `OutcomeEvent`, `PricingPlan` or explicitly scope them workspace-only.
4. **Decide billing-event model.** Either rename/extend `TokenUsage` to `BillingEvent` with polymorphic columns, or create `OutcomeEvent` as the canonical ledger and link it to wallet debit.
5. **Fix lint issues** and **update Stack versions**.

### Immediate low-risk fixes:
- Update PostgreSQL `15+` → `17+`, Redis `7+` → `8+`, FastAPI "latest" → pinned `>=0.140,<0.142` or match `pyproject.toml`.
- Replace "latest" with specific version ranges for non-Obsidian stack items.
- Document React 18 / Node `>=18 <23` exception for browser extension.

---

## 7. Validation Outcome

The architecture spine is **fit for the brownfield core and in-flight epics (E1–E12, E14–E18, E20)** after lint fixes and version updates.

It is **not yet fit for Epic 21 implementation** until the above cross-AD conflicts are resolved.

---

## 8. Re-validation after fixes (same day)

All critical conflicts were addressed in a follow-up edit pass:

| Issue | Fix | Status |
|---|---|---|
| AD-17/18/19/20 missing `Rule` | Added explicit `Rule` field to each AD | ✅ |
| AD-29–AD-33 non-monotonic | Moved AD-34/AD-35 after AD-33 | ✅ |
| Stack version drift + "latest" | Pinned actual versions from package files and Docker Compose | ✅ |
| AD-25 vs AD-11.1 redaction | Defined `source_input` as raw recipe, `Memory.content`/`Chunk[]` as redacted | ✅ |
| AD-39 vs `Automation`/`AutomationRun` | `Sequence` is a new bounded context with its own tables; only scheduler/Celery/notification reused | ✅ |
| Epic 21 `client_id` | AD-31 lists all tables; AD-36–AD-42 models include `client_id` and UUID `id` | ✅ |
| `TokenUsage` overload | Introduced `BillingEvent` for non-LLM business events; `TokenUsage` stays LLM-only | ✅ |
| AD-33/AD-37/AD-39 signal ambiguity | `AlertRule.capability_id`, `sequence_enrollment` channel, `target`; signal types map to capabilities with `emits_signals=true` | ✅ |
| AD-22/AD-23 unverified | Marked `[PROPOSED 2026-08-11 — code not verified]`, then verified code and promoted to `[ADOPTED 2026-08-11]` | ✅ |

`lint_spine.py` re-run: **0 findings**.

Cross-AD adversarial re-check: **all 5 top conflicts RESOLVED**.

**Updated overall status:** ✅ **FIT for implementation** — Epic 21 can now be built against the spine, subject to remaining governance gates (legal/ToS, email setup, vendor POC).

---

## 9. Final `bmad-architecture` validation

- **Lint:** `lint_spine.py` — **0 findings** ✅
- **Reality-check review:** **CONDITIONAL PASS** ✅
  - Stack versions pinned to actual `pyproject.toml` / `package.json` / `docker-compose` (minor MCP server `>=1.26.0` vs `>=1.25.0` is compatible).
  - AD-17/18/19/20 all have `Rule` fields.
  - AD IDs monotonic.
  - Epic 21 ADs internally consistent; `client_id`, `BillingEvent`, `Sequence` bounded context all consistent.
- **Adversarial review:** **PASS** ✅
  - AD-25 vs AD-11.1, AD-39 vs `Automation`, `client_id` boundaries, `TokenUsage` vs `BillingEvent`, AD-33/37/39 signal flow all consistent.
  - UX contracts and `epics.md` aligned.
  - Only remaining conflict was **AD-22/AD-23 status mismatch** → resolved by verifying code: 300 unit tests passed, status promoted to `ADOPTED`.

**Final overall status:** ✅ **FIT for implementation** — all critical conflicts resolved, lint clean, cross-AD and UX consistency verified.
