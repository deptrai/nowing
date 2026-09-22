---
story_key: 37-2-vietnam-cultural-honorific-and-relationship-tone-engine
status: done
baseline_commit: 07168015421f222c195db73daac46e5000241cc1
epic: 37
priority: P0
target_codebase: nowing_backend
architectural_invariants: [AD-116]
---

# Story 37.2: Vietnam Cultural Honorific & Relationship Tone Engine

**Status:** `ready-for-dev`  
**Epic:** Epic 37: Nowing Revenue Engine — Unified Outbound Workstation  
**Priority:** P0  
**Target Codebase:** `nowing_backend`  
**Architectural Alignment:** Extends `app/services/sequencer/services/executor.py`, `app/services/sequencer/dispatch.py`, and `app/services/sequencer/inbound.py`.

## Story

As a B2B Sales Representative,  
I want the sequencer and auto-reply agent to dynamically select native Vietnamese honorific pronouns (Anh/Chị/Em/Quý đối tác) based on prospect seniority and estimated age,  
So that cold outreach and automated replies sound respectful, professional, and indistinguishable from an experienced local sales rep.

## Acceptance Criteria

- **AC-1 (Deterministic Honorific Resolution):** `VietnamHonorificResolver` infers age differential (from birth year in CCCD/MST or graduation year) and title seniority per AD-116 (0ms latency, $0 token cost), mapping to addressing pairs (`Anh - Em`, `Chị - Em`, `Quý đối tác - Chúng tôi`).
- **AC-2 (Prompt Context Injection):** Injects resolved honorific variables into LLM generation context under the `{salutation}` token for sequence steps and two-way auto-replies.
- **AC-3 (Anti-Translation Quality Gate & Foreign Fallback):** Rejects robotic direct translations (such as "Bạn/Tôi"); defaults to standard English business honorifics (`Dear Mr./Ms. [Lastname]`) for foreign prospects/international domains, and neutral professional phrasing (`Quý anh/chị` or `Quý đối tác`) when demographics are ambiguous.
- **AC-4 (Decree 91 Curfew Enforcement):** Message dispatch strictly halts between 21:00 and 08:00 ICT per Decree 91/2020/NĐ-CP.

## Review Triage Log

**2026-09-22 — 3 layers (blind-hunter / edge-case-hunter / verification-gap), ~30 findings sau dedup.**

| Finding | Verdict | Route | Evidence |
|---|---|---|---|
| `session.get(Lead, scalar)` — Lead PK composite `(id, workspace_id)` → raise → except swallow → inbound honorific no-op | high | patch | tuple lookup; `_FakeSession.get` che mất trong test |
| `_decrypt_field` trả raw khi decrypt fail → ciphertext vào salutation | medium | patch | return `None` — field skipped (dispatch + inbound + auto_reply) |
| `_defer_step_for_curfew` set `status=scheduled` không CAS → ghi đè `unsubscribed` nếu opt-out giữa claim→defer | medium | patch | CAS `update()` guard version + status; rowcount=0 → skip |
| `is_zns_sending_window_open` vẫn 21:30 vs curfew 21:00 — 2 gate cùng Decree 91 lệch nhau | medium | patch | zns_client dùng `is_dispatch_curfew`; pinned test update 20:59/21:00 |
| Curfew check chỉ trước dispatch — step bắt đầu 20:59:59 gửi qua 21:00 | low | patch | re-check trong per-channel loop |
| `_is_foreign`: VN name không diacritics + gmail.com → "Dear Mr./Ms." | medium | patch | free-mail hosts không phải foreign signal; +`vietnamese`/`vi`/`việt` |
| `ROBOTIC_PRONOUN_RE`: "ban"/"toi" không diacritics lọt; "theo/với/cho tôi" bị reject nhầm | medium | patch | NFD-strip trước match + mở rộng lookbehind allowlist |
| Robotic-gate `return ""` trước `record_token_usage` → rejected calls không bị bill | low | patch | record trước, gate sau |
| Chat-key fallback thiếu consent/is_valid; Lead lookup arbitrary; email/sms không lookup | medium | patch | filters + `order_by created_at desc` + email/phone lookups |
| `_infer_birth_year` scan year trong MST — org tax code không encode birth year → coincidental match | medium | patch | bỏ mst/tax_id scan (deviation từ AC-1 text: MST thực tế không chứa birth year) |
| `_collect` precedence ngược docstring (lead thắng contact qua setdefault) | low | patch | assign thay setdefault: contact > lead > profile |
| `sender_gender` chỉ nhận "female" → "f"/"nữ" silent map "Anh" | low | patch | `_normalize_gender` synonyms |
| `zalo_data` non-dict `.items()` crash + nested `{salutation}` không interpolate | medium | patch | isinstance guard + `interpolate_template_data` recursive |
| `event_metadata["honorific"]` chứa decrypted name (PII at rest) + không ai đọc | medium | patch | chỉ giữ pronouns/tone/reason — drop name/salutation |
| 2 integration tests call `_handle_send_step` không patch curfew → flaky 21:00-08:00 | medium | patch | patch `is_dispatch_curfew` trong 2 tests |
| Test gaps: robotic-gate path, honorific→prompt injection, ZNS interpolated template_data, deferral window assert | medium | patch | +14 unit tests |
| Sender identity global env (workspace-level consultant demographics) | low | defer | product feature — per-workspace sender profile |
| Auto-reply path không gate curfew | — | defer | replies-to-inbound ≠ unsolicited marketing; documented trong docstring |
| `event_type="skipped"` cho deferral inflates skip metrics | false | reject | subtype `curfew_decree91` đủ distinguish; convention `_skip_step` |
| `_first_scalar` AsyncMock-tolerance helper trong prod code | false | reject | defensive helper, không harm |

**Verification post-patch:** ruff clean; 81/81 tests pass (34 honorifics + 20 sequencer + 6 auto-reply + 4 multi-channel + 8 zns + patched integration tests).
