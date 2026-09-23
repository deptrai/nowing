---
story_key: 37-5-sequencer-to-artifact-integration-1-click-mini-pitch-portal
status: done
baseline_commit: a4827213808e72bc40df02936b7bcd321f72c540
epic: 37
priority: P1
target_codebase: nowing_backend, nowing_web
architectural_invariants: [AD-119]
---

# Story 37.5: Sequencer-to-Artifact Integration (1-Click Mini-Pitch Portal Generator)

**Status:** `review`  
**Epic:** Epic 37: Nowing Revenue Engine — Unified Outbound Workstation  
**Priority:** P1  
**Target Codebase:** `nowing_backend`, `nowing_web`  
**Architectural Alignment:** Extends Web Builder (`app/services/web_builder/`, Epic 27.1), Next.js SSR (`nowing_web/`), and Visual Cadence Builder.

## Story

As an Outbound Campaign Manager,  
I want the sequencer to automatically trigger the Web Builder to generate personalized 1-click interactive mini-pitch portals for target prospects,  
So that our outreach emails and messages feature a tailored, branded interactive value proposition.

## Acceptance Criteria

- **AC-1 (Single Multi-Tenant SSR Invariant - AD-119):** Portals are served via a unified Next.js SSR route (`pitch.nowing.ai/[workspace_slug]/[lead_id]`) reading metadata dynamically from Postgres/Redis with Cloudflare edge caching (TTFB $< 100$ms). Deploying individual Dokploy Docker containers per lead is strictly prohibited.
- **AC-2 (Personalized Branded Presentation):** Combines prospect logo, company name, 30-second executive summary, interactive ROI calculator, and inline calendar booking CTA.
- **AC-3 (Stored XSS Sanitization):** All dynamic prospect fields (company name, notes, title) are strictly sanitized against Stored XSS via DOMPurify/escaping.
- **AC-4 (Decree 13 Opt-Out Compliance):** Portal footer must include a verified "Yêu cầu xóa thông tin của tôi / Opt-out" link compliant with Decree 13/2023/NĐ-CP.
- **AC-5 (Template Injection):** Injects generated portal URL into `{{pitch_portal_url}}` variable for cadence copy with idempotent caching to avoid duplicate builds.

## Review Triage Log

| # | Finding | Verdict | Route | Evidence |
|---|---|---|---|---|
| 1 | `company_name` fallback `or lead.company_name` trả raw unsanitized khi sanitize → `""` | medium | patch | fallback "Doanh nghiệp"; industry/location/workspace_name đã fallback an toàn |
| 2 | Cache blob không validate — non-dict/stale-version/malformed shape → Pydantic 500 ngoài try, poisoned 30 ngày | high | patch | `_cached_fields_valid`: dict + version match + PitchExecCard/PitchRoiDefaults re-validate → miss → rebuild+overwrite |
| 3 | `replace("{{","{")` global — mangle literal `{{`/`}}` trong template cũ | high | patch | scoped regex `\{\{\s*(\w+)\s*\}\}` → `{\1}`; literal braces giữ nguyên |
| 4 | `{ pitch_portal_url }` whitespace → detect được nhưng regex interpolate không match → token literal gửi prospect | medium | patch | interpolation regex thêm `\s*` trong braces |
| 5 | Opt-out không purge portal: cache `pitch_portal:{lead}` + `/meta` vẫn serve trang cá nhân 30 ngày | high | patch | delete cache key + meta 404 khi `consent_status=="withdrawn"` |
| 6 | Opt-out re-implement mất `process_opt_out` semantics: ws lock, refund, hmac-match purge (is_valid=False giữ PII), masked-vs-normalized DNC value | high | patch | delegate per-value vào `OptOutService.process_opt_out` + `seen` dedupe; decrypt-fail → DNC từ stored `phone_hmac`/`email_hmac`; anonymize mọi row |
| 7 | Hardcoded `nowing-secret-key-for-dnc-compliance-32` fallback | medium | patch | bỏ fallback — `DncComplianceService()` dùng `config.SECRET_KEY`, fail contained trong generic-ok route |
| 8 | Bulk unsubscribe không bump `version` → OCC miss → in-flight enrollment gửi thêm 1 message | medium | patch | `version=SequenceEnrollment.version + 1` |
| 9 | Opt-out audit IP = edge IP sau proxy | low | patch | đọc `x-forwarded-for`/`x-real-ip` first hop |
| 10 | `PitchRoiDefaults` thiếu `min ≤ default ≤ max` | low | patch | `model_validator` |
| 11 | Dead `workspace` param + wasted `session.get` mỗi cold build | low | patch | param removed, lookup gone |
| 12 | `resolve_workspace_portal_ref` theo `updated_at` → URL đổi khi republish app | medium | patch | `workspace_ref` pin trong cached blob; URL per-lead stable |
| 13 | Test gaps: send-step e2e URL-in-body, meta route generated fields, DNC hmac match `is_blocked` | high | patch | +13 tests (56 total): dispatch e2e, meta route `__wrapped__`, value_hmac == `hash_phone_hmac(normalized)` |
| 14 | `event_type="delivered"` cho non-send step | — | reject | pre-existing convention — `wait`/`condition` steps cùng ghi `delivered` + subtype (`enrollments.py:403,433`) |
| 15 | Opt-out CORS/same-origin trên `pitch.nowing.ai` | — | defer | domain chưa live (DNS deferred 37.6); hôm nay flow chạy qua `/pitch/...` trên main host — settle khi DNS cutover (add host vào `allowed_origins`) |
| 16 | Google favicon leak viewer IP + lead domain cho third party | — | defer | AC-2 bắt buộc prospect logo; backend-proxy favicon thêm public surface — settle khi đổi brand-fetch provider |
| 17 | Unpublish app → branded slug links đã gửi 404 vĩnh viễn | — | defer | link-permanence là design question (slug qua `status=="published"` gate AD-119); cache-pin ref (#12) giữ URL ổn định lúc generate |
| 18 | Story narrative nói "trigger the Web Builder" nhưng impl là deterministic template | — | defer | ACs không yêu cầu Web Builder engine; template deterministic là điều kiện cho idempotent cache — `ponytail:` comment ghi upgrade path LLM/web-builder |
