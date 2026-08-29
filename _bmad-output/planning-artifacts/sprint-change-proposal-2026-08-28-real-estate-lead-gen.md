# Sprint Change Proposal — Real Estate Lead Gen Reality-Correction (2026-08-28)

**Workflow:** `bmad-correct-course` (batch mode)
**Project:** Nowing
**Date:** 2026-08-28
**Author:** Browser Pilot / Devin Agent
**Status:** ✅ **ADOPTED** (PO Luisphan, 2026-08-28)

**Trigger:** Live browser E2E validation of the real-estate broker persona (10 lots/houses to sell) exposed 5 product gaps in `multi_source_lead_gen` flow. The flow technically executes, but the returned data does not match the seller-broker intent and outreach is blocked.

**Artifacts bị ảnh hưởng:**
- `_bmad-output/planning-artifacts/prds/prd-Nowing-2026-07-22/prd.md` (§4.10 Lead Gen Intelligence)
- `_bmad-output/planning-artifacts/epics.md` (Epic 21 stories)
- `_bmad-output/planning-artifacts/ux-designs/user-flow-gen-leads-2026-08-27.md`
- `_bmad-output/implementation-artifacts/sprint-status.yaml`
- (thứ cấp) `README.md`, `docs/`, agent system prompts

---

## 1. Issue Summary

Live Playwright MCP run với persona **sales môi giới đất ở TP.HCM, ký gửi 10 lô cần bán** đã xác minh:

| Prompt | Kết quả kỹ thuật | Kết quả nghiệp vụ |
|---|---|---|
| *"Tìm 10 khách hàng tiềm năng mua nhà đất ở TP.HCM, tôi có 10 lô ký gửi cần bán"* | `multi_source_lead_gen` chạy, 10 leads BĐS, Right Dock auto-open, SSE stream xong, 0 console errors | Trả về **tin đăng bán** (sellers), không phải **người mua**. Cột phone `—`, Zalo/ZNS disable. |
| *"Tôi cần bán 10 lô đất ký gửi ở quận 7, hãy tìm 10 người mua tiềm năng có số điện thoại để liên hệ"* | Tương tự, 10 leads BĐS | Chat agent vẫn gọi là "khách hàng tiềm năng" / "nguồn khách tiềm năng", dễ gây hiểu nhầm. |

**5 lỗi sản phẩm được xác nhận:**

1. **Intent bị hiểu nhầm:** `multi_source_lead_gen` không phân biệt "tôi cần bán / tìm khách mua" vs "tôi cần mua". Nó luôn scrape tin đăng bán.
2. **Không có số điện thoại:** BĐS adapters hiện chạy với `resolve_phones=False` để tránh timeout, khiến `Phone` column = `—`.
3. **Chat framing sai:** Agent gọi listings là "khách hàng tiềm năng" trong khi dữ liệu là nguồn cung / bên bán.
4. **Thiếu affordance mở khóa SĐT:** UI chỉ có "Xem sơ đồ liên kết doanh nghiệp" enable; phone/Zalo/ZNS bị disable.
5. **Composer disabled sau stream:** Nút `Send message` đôi khi vẫn disabled khi Slate value được set bằng JS (observed mid-test).

**Bằng chứng:**
- `_bmad/memory/test-e2e-browser/sessions/real-estate-sales-pilot-01.png`
- `_bmad/memory/test-e2e-browser/sessions/real-estate-sales-pilot-02.png`
- `_bmad/memory/test-e2e-browser/sessions/2026-08-27.md`

---

## 2. Impact Analysis

### 2.1 Epic Impact

| Epic | Trạng thái | Ảnh hưởng |
|---|---|---|
| **Epic 21 — Lead Gen Intelligence & Social Graph** | `[IN-PROGRESS]` | **Trực tiếp.** Các story 21.15, 21.3, 21.16, 21.19, 21.20 cần AC bổ sung hoặc reopen. |
| **Epic 10 — Connector & Scraper Expansion (Vietnam BĐS)** | `[IN-PROGRESS]` | **Trực tiếp.** `batdongsan`, `chotot`, `muaban_bds` cần phone-resolution strategy rõ ràng. |
| **Epic 6 — Automations (Playbook Reuse)** | `[DONE]` với gap | **Gián tiếp.** Playbook BĐS cần parameter hóa intent mua/bán (Story 6.6/6.7) sau khi pilot. |
| **Epic 27 — Web Builder / Presentation** | `[IN-PROGRESS]` | Không ảnh hưởng. |

### 2.2 Story Impact

| Story | Thay đổi cần thiết |
|---|---|
| **21.15 Unified Multi-Source AI Lead Generation Orchestrator** | Thêm AC về intent disambiguation (buy vs sell) và adapter routing logic. |
| **21.3 Vietnam Phone & Contact Waterfall Engine** | Reopen: cần re-enable phone resolution với adaptive timeout / circuit breaker, hoặc per-contact unlock. |
| **21.19 Lead Source Adapter Live Data Integration** | Cập nhật AC về `resolve_phones` và `VerifiedContact` creation. |
| **21.20 Extend Multi-Source Lead Gen Adapters** | Bổ sung `resolve_phones` strategy cho `MuabanBdsLeadAdapter`. |
| **21.16 Nowing Split-View Canvas** | Thêm AC về nút "Mở khóa SĐT" / "Xem chi tiết" trên `NowingLeadMatrix`. |
| **21.4 Outbound Prospecting Automation** | Cần lead có phone để sequence hoạt động — phụ thuộc 21.3. |

### 2.3 Artifact Conflicts

- **PRD §4.10 (Lead Gen Intelligence):** FR-63..FR-69 và FR-85 mô tả lead gen nhưng chưa phân biệt buyer/seller intent. Cần bổ sung `FR-85.1` — *Intent Disambiguation for Buy vs Sell*.
- **PRD §4.10:** FR-65 ghi phone waterfall done, nhưng thực tế BĐS adapter tắt `resolve_phones` do timeout. Cần cải chính scope.
- **UX Flow `user-flow-gen-leads-2026-08-27.md`:** Mô tả "Click 1 lead → LeadDetailFlyoutDrawer → PhoneCopyPill → ZaloOutreachButton", nhưng hiện tại không có data để unlock. Cần thêm edge case "No phone → show Unlock action".
- **Architecture:** `LeadGenOrchestrator.decompose_query` chưa có intent tag `buy`/`sell`. `LeadSourceAdapterRegistry.resolve_adapters_for_intent` cần xử lý seller-intent.

### 2.4 Technical Impact

- **Backend:** `app/lead_intelligence/services/lead_gen_orchestrator.py`, adapters (`batdongsan.py`, `chotot.py`, `muaban_bds.py`), scraper `resolve_phones` flag, `LeadBatchService`, chat tool prompt.
- **Frontend:** `components/leads/NowingLeadMatrix.tsx`, `components/leads/PhoneCopyPill.tsx`, `components/leads/zalo-outreach-button.tsx`, Slate composer (`Send message` disabled state).
- **Tests:** `tests/leads/broker-smoke.spec.ts` cần cập nhật để assert phone/existence thay vì chỉ count.

---

## 3. Recommended Approach

**Chọn: Direct Adjustment (Option 1) — amend AC của story hiện có, không tạo story mới.**

Không cần rollback hay thay đổi MVP. Các lỗi này là **gaps trong implementation** của Epic 21/Epic 10, không phải strategic pivot. Tuy nhiên, nếu không fix thì use case BĐS seller-broker **không usable**.

**Phân kỳ thực hiện:**

| Phase | Nội dung | Story | Ưu tiên |
|---|---|---|---|
| **P0 — Hotfix (1–2 ngày)** | Re-enable `resolve_phones` với circuit breaker; fix `StringDataRightTruncation` already done; thêm phone unlock UI. | 21.3 amend, 21.16 amend | P0 |
| **P1 — Intent + chat framing (2–3 ngày)** | Thêm `intent: buy|sell|neutral` trong `decompose_query`; seller-intent gọi XActions social (Facebook groups "cần mua") hoặc trả về listing với framing rõ ràng. | 21.15 amend | P1 |
| **P2 — Composer disabled (1 ngày)** | Kiểm tra Slate composer state sau stream. | 21.16 amend | P2 |

**Rationale:**
- Phone là **gateway** cho toàn bộ outbound (Zalo, ZNS, sequence). Không phone thì Epic 21.4/21.6 vô dụng.
- Intent disambiguation là **differentiator** cho BĐS broker — giúp người bán tìm người mua thay vì chỉ xem đối thủ.
- Chat framing rẻ nhưng ảnh hưởng trust lớn.

---

## 4. Detailed Change Proposals

### 4.1 PRD — §4.10 Lead Gen Intelligence

#### FR-85.1 MỚI — Intent Disambiguation for Buy vs Sell

**Section:** §4.10, sau FR-85

```
FR-85.1 Lead Intent Disambiguation (Buy / Sell / Research)
When a user submits a natural-language lead query, Nowing MUST classify the user's role/intent:
- `buy` → user wants to purchase/rent (return listings from sellers).
- `sell` → user has inventory and wants buyer demand (return buyer-demand signals or competitor listings with option to extract seller phones).
- `neutral` / `research` → generic market scan.

The classification MUST be used by `LeadGenOrchestrator` to:
1. Select appropriate adapters (e.g., seller-intent should search social buyer-demand signals, not scrape more seller listings).
2. Generate honest chat framing (e.g., "Đây là 10 tin đăng bán tương tự — bạn muốn tìm người mua, lấy SĐT chủ tin, hay phân tích giá?").
```

**Rationale:** Ngăn hiểu nhầm nguồn cung vs nguồn cầu.

### 4.2 Epics — Epic 21 (NO new stories; amend existing)

> **Decision:** All 5 gaps fit into existing Epic 21 stories. No new story IDs needed; we only append/amend Acceptance Criteria.

#### Story 21.15 — Thêm Acceptance Criteria

**Section:** Story 21.15 Acceptance Criteria

```
NEW (21.15.6):
Given a chat prompt containing seller intent (e.g., "tôi cần bán", "tìm khách mua", "ký gửi"),
When LeadGenOrchestrator.decompose_query runs,
Then it MUST return `intent="sell"` and the adapter selection MUST prioritize buyer-demand sources (social/alert groups) or return listings with a seller-framed summary.

NEW (21.15.7):
Given a chat prompt containing buyer intent (e.g., "tôi cần mua", "tìm nhà"),
When LeadGenOrchestrator.decompose_query runs,
Then it MUST return `intent="buy"` and the adapter selection MUST return seller listings.
```

**Rationale:** Bắt buộc intent routing.

#### Story 21.3 — Reopen / Amend Scope

**Section:** Story 21.3 Acceptance Criteria (bổ sung)

```
NEW (21.3.5):
Given a BĐS listing scraped by batdongsan/chotot/muaban_bds adapter,
When phone resolution is enabled,
Then the adapter MUST attempt phone extraction with a per-adapter timeout (90s default, circuit breaker on repeated timeout) and persist any resolved phone into `VerifiedContact`.

NEW (21.3.6):
Given phone resolution fails or is disabled for a listing,
When the row is rendered in NowingLeadMatrix,
Then the UI MUST show an explicit "Mở khóa SĐT" / "Unlock phone" action that debits 1.5 credits on click and retries resolution.
```

**Rationale:** `resolve_phones=False` đang giết outbound flow.

#### Story 21.16 — Thêm UI AC

**Section:** Story 21.16 Acceptance Criteria

```
NEW (21.16.5):
Given a lead row in NowingLeadMatrix without a phone,
When rendered,
Then it MUST display a primary action "Mở khóa SĐT" ( Unlock phone ) in the Hành động column, not only the disabled Zalo/ZNS buttons.

NEW (21.16.6):
Given the user clicks "Mở khóa SĐT",
When the phone is successfully resolved,
Then the row MUST update in-place (Zero sync) to show the masked phone and enable Zalo/ZNS buttons.

NEW (21.16.7):
Given the agent stream has completed,
When the user focuses the Slate editor,
Then the Send message button MUST be enabled and reactive to editor value changes.

NEW (21.16.8):
Given the editor value is set programmatically (e.g., from a suggested action),
When the value changes,
Then the submit button MUST update its disabled state reactively.
```

**Rationale:** Hiện UI không có cách nào để user biết phone bị khóa và phải trả phí; composer disabled bug cũng thuộc về Split-View chat surface.

#### Story 21.15 — Bổ sung Chat Framing AC

**Section:** Story 21.15 Acceptance Criteria (cuối)

```
NEW (21.15.8):
Given multi_source_lead_gen returns BĐS listings (seller-side data),
When the agent responds in chat,
Then it MUST NOT call them "khách hàng tiềm năng" or "nguồn khách tiềm năng" unless the source is verified buyer-demand.

NEW (21.15.9):
Given the user intent is "sell" (e.g., user has inventory to sell),
When the agent returns BĐS listings,
Then it MUST frame them as "tin đăng bán tương tự / đối thủ cạnh tranh" and offer 1-click follow-up actions:
  (a) Tìm người mua,
  (b) Lấy SĐT chủ tin,
  (c) Phân tích giá.
```

**Rationale:** Xây dựng trust và giảm hiểu nhầm.

### 4.3 UX — `user-flow-gen-leads-2026-08-27.md`

**Section:** 3. UI Flow — Hành động trên lead

THÊM sub-flow:

```
T1 --> A1 --> D1
D1 --> P1 (if phone exists)
D1 --> U1 ["Mở khóa SĐT" button]
U1 --> P2 [Debit 1.5 credits]
P2 --> P1 (if success)
P2 --> E1 ["Không lấy được SĐT — hoàn credit"]
```

**Section:** 7. Edge cases

THÊM:
- **No phone, no unlock source:** lead row shows "Không có SĐT" instead of disabled buttons.
- **Seller intent:** UI suggests next actions "Tìm người mua" / "Phân tích giá".

### 4.4 Architecture — `LeadGenOrchestrator`

**Cập nhật AD-44 (Lead Source Adapter Contract):**
- Thêm `intent: Literal["buy", "sell", "neutral"]` vào `LeadGenInput`.
- `LeadSourceAdapterRegistry.resolve_adapters_for_intent(query, intent)` phải xử lý `intent="sell"` bằng cách ưu tiên social buyer-demand hoặc trả về listings + flag `source_kind="listing"`.

### 4.5 sprint-status.yaml

**Cập nhật:**
- Epic 21 status remains `in-progress`.
- Story 21.3: `done` → `in-progress` (amended scope).
- Story 21.15, 21.16, 21.19, 21.20: append `amended-2026-08-28` tag.

---

## 5. Implementation Handoff

### Scope classification

**Moderate** — cần PO + Developer phối hợp:
- Reopen/amend nhiều story đã done.
- Có UI change và prompt/system prompt change.
- Cần re-test `broker-smoke.spec.ts` và thêm test case seller-intent.

### Handoff recipients

| Vai trò | Trách nhiệm |
|---|---|
| **PO (Luisphan)** | Approve proposal, confirm intent taxonomy (mua/bán/neutral), xác nhận credit pricing cho unlock SĐT. |
| **Developer Agent** | Implement backend intent routing, re-enable phone resolution với circuit breaker, update UI, sửa chat prompt. |
| **UX (Sally)** | Cập nhật `user-flow-gen-leads-*.md`, thiết kế trạng thái "Mở khóa SĐT". |
| **QA / Browser Pilot** | Re-run Playwright broker-smoke + thêm seller-intent scenario; verify phone unlock E2E. |

### Success criteria

1. `broker-smoke.spec.ts` pass với 10 BĐS leads.
2. Prompt seller-intent trả về kết quả có framing rõ ràng (không gọi listings là "khách hàng").
3. Ít nhất 1 lead có thể unlock SĐT và Zalo/ZNS enable trong E2E.
4. 0 `StringDataRightTruncationError` khi persist leads.
5. Composer enable sau khi stream hoàn thành.

---

## 6. Checklist Status

| Checklist Section | Status |
|---|---|
| 1. Understand the Trigger and Context | ✅ Done — live E2E broker persona |
| 2. Epic Impact Assessment | ✅ Done — Epic 21, 10, 6 affected |
| 3. Artifact Conflict and Impact Analysis | ✅ Done — PRD, Epics, UX, Architecture |
| 4. Path Forward Evaluation | ✅ Done — Direct Adjustment, 3 phases |
| 5. Sprint Change Proposal Components | ✅ Done — see sections above |
| 6. Final Review and Handoff | ✅ Done — PO approved 2026-08-28 |

---

## 7. Artifacts Updated

- ✅ `_bmad-output/planning-artifacts/prds/prd-Nowing-2026-07-22/prd.md` — added FR-85 + updated FR index.
- ✅ `_bmad-output/planning-artifacts/epics.md` — amended AC for Story 21.3, 21.15, 21.16, 21.19, 21.20.
- ✅ `_bmad-output/planning-artifacts/ux-designs/user-flow-gen-leads-2026-08-27.md` — added unlock-phone sub-flow and seller-intent edge cases.
- ✅ `_bmad-output/implementation-artifacts/sprint-status.yaml` — 21-3/21-15/21-16 → `in-progress`; 21-19/21-20 tagged amended.

## 8. Handoff

**Scope classification:** Moderate — amend existing Epic 21 stories, no new stories.

**Routed to:** Developer Agent (P0 phone unlock → P1 intent/chat framing → P2 composer fix).

**Deliverables:**
- Updated `epics.md`, `sprint-status.yaml`, PRD §4.10, UX flow.
- Sprint Change Proposal (this document).
- Implementation sequence: P0 → P1 → P2.

**Success criteria:**
1. `broker-smoke.spec.ts` pass với 10 BĐS leads.
2. Prompt seller-intent trả về kết quả có framing rõ ràng.
3. Ít nhất 1 lead có thể unlock SĐT và Zalo/ZNS enable trong E2E.
4. 0 `StringDataRightTruncationError` khi persist leads.
5. Composer enable sau khi stream hoàn thành.
