# UX Spec — Epic 26 Mission Control & Two-Tier Phone Unlock

**Project:** Nowing
**Date:** 2026-08-20
**Scope:** `MissionControlWidget`, `PhoneUnlockPill`, `SmartUnlockPopover` trong Split Canvas / Lead Intelligence view
**Owner:** Sally — UX Designer
**Mục tiêu:** tối ưu trải nghiệm tìm lead tự động và mở khóa SĐT, đảm bảo **minh bạch chi phí, tránh mất tiền oan, vẫn hiệu quả**.

---

## 1. Tổng quan

Epic 26 mang hai bề mặt người dùng chính vừa được browser-test:

1. **Mission Control (Glass Box):** hiển thị tiến trình DSH mission 4 bước — Crawl → Reasoning → Extraction → Ingestion, token velocity, reasoning CoT, và deliverable download.
2. **Two-Tier Phone Unlock:** lead matrix hiển thị SĐT bị mask; click mở Smart Confirmation Popover với chi phí 1.5 credits, tùy chọn `1-Click Fast Unlock`, và undo.

Spec này định nghĩa chi tiết interaction, visual, microcopy, accessibility và acceptance criteria để cải thiện UX dựa trên quan sát từ test thực tế.

---

## 2. Design Principles

| # | Nguyên tắc | Ý nghĩa |
|---|---|---|
| P1 | **Cost transparency** | User luôn thấy chi phí bằng cả credits **và** tiền thật trước khi bị trừ. |
| P2 | **Anti-fat-finger** | Không có hành động trừ tiền chỉ bằng một click đơn, trừ khi user đã bật fast unlock một cách chủ đích. |
| P3 | **Undo by default** | Mỗi hành động tốn tiền phải có đường hoàn tác rõ ràng trong khoảng thời gian hợp lý. |
| P4 | **Glass box, not black box** | Mission Control cho user thấy mission đang làm gì, ở bước nào, tốn bao nhiêu, và kết quả là gì. |
| P5 | **Progressive disclosure** | Thông tin kỹ thuật (CoT) có thể mở rộng, nhưng trạng thái và chi phí phải hiển thị ngay. |

---

## 3. Personas & Scenarios

### 3.1. Personas

- **Chị Mai — Sales Manager:** muốn so sánh 20 công ty AI Agent, tải Excel, sau đó mở SĐT của lead tiềm năng. Cô ấy không rành kỹ thuật, rất nhạy cảm với “click mất tiền”.
- **Anh Đức — SDR:** mở nhiều SĐT liên tiếp trong một session. Cần tốc độ, nhưng không muốn vô tình kích hoạt fast unlock.

### 3.2. Scenarios

1. **Wide research + download:** Chị Mai tạo mission `“20 công ty AI Agent tại TP.HCM”`, mode `wide`. Widget hiển thị 4 bước, file xlsx xuất hiện ở cuối. Cô click tải, nhận toast xác nhận.
2. **First phone unlock:** Chị Mai thấy `0901***567`, click pill, popover hiện chi phí `1.5 credits ≈ $0.0015`. Cô đọc xong mới click `Mở khóa SĐT`.
3. **Fast unlock session:** Anh Đức mở 10 SĐT trong 15 phút. Anh tích `1-Click Fast Unlock`, sau đó chỉ cần click pill là mở. Cuối session, tự động tắt.
4. **Undo accidental unlock:** Chị Mai click nhầm, toast hiện `Hoàn tác` trong 30s. Cô click, credits hoàn trả.

---

## 4. Component Spec

### 4.1. MissionControlWidget

**Vị trí:** right panel trong Split Canvas (`/dashboard/:workspace/new-chat?mode=leads`) hoặc panel phụ trong Lead Intelligence view.

#### 4.1.1. Header

| Element | Current | Proposed |
|---|---|---|
| Title | `DSH Mission Control` | `Trợ lý tìm lead` |
| Subtitle | `Glass Box tiến trình tìm lead` | Query hiện tại, ví dụ `“20 công ty AI Agent tại TP.HCM”` |
| Phase badge | `terminal` / `crawl` / `extraction` | Map sang tiếng Việt: `Đang chạy`, `Hoàn thành`, `Lỗi`, `Đang trích xuất` |
| Elapsed | `12m 34s` | Giữ nguyên, icon `Clock` |
| Cancel button | disabled, tooltip `Hủy nhiệm vụ (chưa hỗ trợ)` | Ẩn hoặc thay bằng `…` menu chứa “Hủy” với tooltip giải thích deferred |

**Rationale:** User không cần biết `DSH` hay `terminal`. Cần nói rõ mission đang làm gì.

#### 4.1.2. Progress bar

- Progress bar với gradient `indigo → emerald`.
- Khi `status === 'running'`, thêm `animate-pulse` hoặc `animate-stripes` để user thấy đang tiến triển.
- Hiển thị `%` bên phải label.

#### 4.1.3. 4-Step Stepper

| Step | Icon | Label | Active state |
|---|---|---|---|
| 0 | Search | `Crawl` | bg emerald/10, border emerald/40 |
| 1 | Cpu | `Reasoning` | bg emerald/10, border emerald/40 |
| 2 | Network | `Extraction` | bg emerald/10, border emerald/40 |
| 3 | Database | `Ingestion` | bg emerald/10, border emerald/40 |

- Step hiện tại có `ring-1 ring-emerald-500/50`.
- Step chưa tới giữ `bg-muted/40, border-border`.
- Step lỗi chuyển sang màu đỏ, icon `AlertCircle`.

#### 4.1.4. Token velocity panel

**Layout:** 3 cột.

| Cột | Label | Value | Format |
|---|---|---|---|
| 1 | `Tốc độ xử lý` | `tokens_per_second` | `{n} tokens/sec` |
| 2 | `Tổng tokens` | `tokens_total` | `{n}` |
| 3 | `Chi phí đã dùng` | `cost_credits` + `cost_micros` | `1.2 credits ≈ $0.0012` |

**Mở rộng (P2):**
- Nếu có `mission.budget_micros`, thêm progress bar nhỏ: `Đã dùng 12% ngân sách tháng`.
- Nếu `status === 'running'` và `cost_credits > 0`, hiển thị `Ước tính còn: {remainingCredits} credits` dựa trên token velocity.

#### 4.1.5. Deliverables section (`Kết quả xuất ra`)

**Current state:**

```tsx
<a href={href} download data-testid={`mission-control-download-${d.filename}`} ...>
  <Download />
  <span>{d.filename}</span>
  <span>{formatBytes(d.size)}</span>
  {d.include_pii && <span>(PII)</span>}
</a>
```

**Proposed state:**

Mỗi deliverable là một card nhỏ:

```
┌─────────────────────────────────────┐
│ [📊] wide_research_output.xlsx      │
│     3 nguồn · 3 khía cạnh · 6.5 KB  │
│     [Tải xuống]  [⚠️ Chứa PII]      │
└─────────────────────────────────────┘
```

**Rules:**
- Luôn hiển thị icon theo loại file: `FileSpreadsheet` (xlsx), `FileText` (json/csv), `FileImage` (pdf/png).
- Hiển thị metadata ngắn: `3 nguồn · 3 khía cạnh · 6.5 KB`.
- `include_pii === true` → badge màu amber với tooltip: `“File này chứa thông tin liên hệ. Hãy xử lý theo quy định bảo mật.”`
- Nút `Tải xuống` là primary button màu emerald, có icon `Download`.
- Sau khi click, hiện Sonner toast: `“Đã tải xuống {filename}”`.
- Nếu download thất bại, toast error và đề nghị thử lại.

#### 4.1.6. Reasoning (CoT) section

- Button `Lý luận (CoT)` giữ nguyên, nhưng mặc định **mở rộng subtask hiện tại** thay vì thu gọn tất cả.
- Mỗi subtask card gồm:
  - `title` + `status` badge (success/pending/error).
  - `tokens_used` · `cost_credits` credits.
  - `reasoning_content` line-clamp-3, có thể mở rộng.

---

### 4.2. SmartUnlockPopover

**Current implementation:** <ref_snippet file="/Users/luisphan/Documents/GitHub/nowing/nowing_web/components/leads/SmartUnlockPopover.tsx" lines="52-111" />

#### 4.2.1. Popover layout

```
┌─────────────────────────────────────┐
│ Xác nhận mở khóa SĐT                │
│ ┌─────────────────────────────────┐ │
│ │     0901***567                  │ │
│ │     1.5 credits ≈ $0.0015       │ │
│ └─────────────────────────────────┘ │
│                                     │
│ [ ] 1-Click Fast Unlock (15 phút)   │
│     Bỏ qua hộp thoại này trong      │
│     15 phút tới.                    │
│                                     │
│              [Hủy] [Mở khóa SĐT]    │
└─────────────────────────────────────┘
```

**Changes from current:**

| # | Current | Proposed | Rationale |
|---|---|---|---|
| 1 | Cost `1.5 credits` | `1.5 credits ≈ $0.0015` | P1: user thấy tiền thật. |
| 2 | Fast unlock TTL `30 phút` | `15 phút` | Giảm rủi ro user quên. |
| 3 | Checkbox label `1-Click Fast Unlock cho phiên này` | `1-Click Fast Unlock (15 phút)` + helper text `“Bỏ qua hộp thoại này trong 15 phút tới.”` | Rõ ràng phạm vi. |
| 4 | `Mở khóa SĐT` primary emerald | Giữ emerald, nhưng thêm `aria-describedby` trỏ đến cost | Accessibility. |

#### 4.2.2. Bulk unlock

- `isBulk === true`:
  - Title: `Xác nhận mở khóa {selectedCount} SĐT`
  - Cost: `{selectedCount * 1.5} credits ≈ ${selectedCount * 0.0015}`
  - Không cho phép bật fast unlock từ bulk popover (bulk luôn confirm).
  - Nút action: `Mở khóa SĐT hàng loạt`.

#### 4.2.3. Error / loading states

- `isLoading === true`: button hiện spinner, disabled; checkbox disabled.
- Lỗi 402 (Insufficient credits): thay thế nội dung popover bằng `“Không đủ credits. Nạp thêm để tiếp tục.”` + link `Nạp credits`.
- Lỗi 403 (DNC): `“Số điện thoại bị chặn bởi DNC. Không thể mở khóa.”`

---

### 4.3. PhoneUnlockPill

**Current implementation:** <ref_snippet file="/Users/luisphan/Documents/GitHub/nowing/nowing_web/components/leads/PhoneUnlockPill.tsx" lines="39-292" />

#### 4.3.1. Visual states

| State | Visual | Interaction |
|---|---|---|
| **Locked** | `bg-slate-100 text-slate-600 border-dashed border-slate-300`, icon `Lock` | Click mở SmartUnlockPopover hoặc fast unlock nếu active |
| **Unlocked** | `bg-emerald-500/10 text-emerald-700 border-emerald-500/20 border-solid`, icon `Phone` | Click copy SĐT |
| **Disabled (DNC / invalid)** | `bg-muted text-muted-foreground opacity-50 cursor-not-allowed`, icon `Ban` | Không click, tooltip lý do |
| **Shimmer (new from Zero)** | `text-emerald-600/80 animate-pulse` “Đang giải mã SĐT…” | Không click |
| **Flipping** | 150ms `rotateX` animation | Hiệu ứng khi unlock/relock |

**Rationale:** Hiện tại locked và unlocked đều dùng màu emerald, khó phân biệt. Locked nên trung tính hơn.

#### 4.3.2. Fast unlock behavior

- Fast unlock session lưu trong `sessionStorage` với key theo `workspaceId + userId`.
- TTL giảm từ `30 phút` xuống `15 phút`.
- Session **tự động expire** khi:
  - Quá 15 phút không tương tác với bất kỳ phone pill nào.
  - User rời khỏi `/dashboard/:workspace/new-chat?mode=leads` hoặc `/dashboard/:workspace/leads`.
  - User đăng xuất.

**Guard against accidental spend:**
- Khi fast unlock active, click pill không mở popover, nhưng vẫn hiện **inline spinner** 150ms trước khi gọi API.
- Sau fast unlock, hiện toast `“Đã mở khóa SĐT -1.5 credits”` với nút `Hoàn tác` trong **10s** (không chỉ 5s).

#### 4.3.3. Undo / relock

- Sau mỗi unlock (cả fast unlock), hiện Sonner toast với action `Hoàn tác`.
- Toast duration:
  - First unlock / single unlock: **30s**.
  - Fast unlock: **10s**.
- Click `Hoàn tác` gọi `relockContact`, pill quay về masked, credits hoàn trả.
- Nếu relock thất bại (ví dụ đã quá 24h SLA), hiển thị lỗi và contact support.

#### 4.3.4. Accessibility

- `aria-label` đầy đủ:
  - Locked: `“Số điện thoại bị ẩn. Click để mở khóa với chi phí 1.5 credits.”`
  - Unlocked: `“Số điện thoại đã mở khóa: {phone}. Click để copy.”`
  - Disabled: `“Không thể mở khóa số điện thoại này. {reason}.”`
- Popover kích hoạt bằng keyboard: Enter/Space mở, Tab di chuyển, Esc đóng.
- Focus trap trong popover cho đến khi user confirm/cancel.

---

## 5. Interaction Flows

### 5.1. First phone unlock

```
User clicks masked phone pill
  ↓
SmartUnlockPopover opens
  ↓
User sees masked preview + cost (credits + $)
  ↓
User checks “1-Click Fast Unlock (15 phút)” (optional)
  ↓
User clicks “Mở khóa SĐT”
  ↓
API call /unlock
  ↓
Success: pill flips, displays real phone, toast with undo 30s
  ↓
Zalo/Call actions become enabled
```

### 5.2. Fast unlock session

```
User enabled fast unlock in previous popover
  ↓
Session stored (15 min TTL)
  ↓
User clicks another masked pill
  ↓
No popover; inline spinner 150ms
  ↓
API call /unlock
  ↓
Success: pill flips, toast with undo 10s
  ↓
Each click resets 15-min TTL
  ↓
After 15 min inactivity or leaving leads view → session expires
```

### 5.3. Undo flow

```
User unlocks phone
  ↓
Toast appears: “Đã mở khóa SĐT -1.5 credits [Hoàn tác]”
  ↓
Within 30s (single) / 10s (fast): user clicks “Hoàn tác”
  ↓
API call /relock
  ↓
Success: pill flips back to masked, toast “Đã hoàn tác +1.5 credits”
  ↓
Zalo/Call actions disabled again
```

### 5.4. Download deliverable

```
Mission reaches terminal/success
  ↓
Deliverable card appears in Mission Control
  ↓
User clicks “Tải xuống”
  ↓
Browser downloads file
  ↓
Sonner toast: “Đã tải xuống {filename} ({size})”
  ↓
If PII badge present, tooltip explains data sensitivity
```

---

## 6. Microcopy Table

| Context | Vietnamese | English fallback | Notes |
|---|---|---|---|
| Widget title | `Trợ lý tìm lead` | `Lead Research Assistant` | Thay `DSH Mission Control` |
| Widget subtitle | `“{query}”` | `“{query}”` | Hiển thị query rõ ràng |
| Phase `terminal` | `Hoàn thành` | `Completed` |  |
| Phase `running` | `Đang chạy` | `Running` |  |
| Phase `error` | `Lỗi` | `Error` |  |
| Cost display | `{credits} credits ≈ ${dollars}` | `{credits} credits ≈ ${dollars}` | Luôn có dollar equivalent |
| Popover title | `Xác nhận mở khóa SĐT` | `Confirm phone unlock` |  |
| Fast unlock checkbox | `1-Click Fast Unlock (15 phút)` | `1-Click Fast Unlock (15 min)` | Rõ phạm vi |
| Fast unlock helper | `Bỏ qua hộp thoại này trong 15 phút tới.` | `Skip this dialog for the next 15 minutes.` |  |
| Button primary | `Mở khóa SĐT` | `Unlock phone` |  |
| Button secondary | `Hủy` | `Cancel` |  |
| Toast success | `Đã mở khóa SĐT -{cost} credits` | `Phone unlocked -{cost} credits` | Có action Hoàn tác |
| Toast relock | `Đã hoàn tác mở khóa +{cost} credits` | `Unlock reverted +{cost} credits` |  |
| Download toast | `Đã tải xuống {filename} ({size})` | `Downloaded {filename} ({size})` |  |
| PII badge | `Chứa PII` | `Contains PII` | Tooltip giải thích |
| 402 error | `Không đủ credits` | `Insufficient credits` | Link nạp credits |
| 403 DNC | `Số điện thoại bị chặn bởi DNC` | `Phone blocked by DNC` |  |

---

## 7. Accessibility (a11y)

- **Focus management:** Khi popover mở, focus trap hoạt động; focus trả về trigger khi đóng.
- **Screen reader:** Popover có `role="dialog"` với `aria-labelledby` và `aria-describedby`.
- **Keyboard:**
  - `Tab` di chuyển qua checkbox, Hủy, Mở khóa.
  - `Enter` kích hoạt nút đang focus.
  - `Space` toggle checkbox.
  - `Esc` đóng popover (tương đương Hủy).
- **Color contrast:**
  - Cost text emerald-600 trên nền trắng đạt ≥ 4.5:1.
  - Disabled pill dùng text-muted-foreground, không dùng màu sắc duy nhất để truyền ý nghĩa.
- **Motion:** Flip animation 150ms; tôn trọng `prefers-reduced-motion`.

---

## 8. Analytics & Metrics

| Event | Trigger | Properties |
|---|---|---|
| `mission_control.impression` | Widget render | `phase`, `status`, `has_deliverable` |
| `mission_control.deliverable.download` | Click download | `filename`, `size`, `include_pii`, `mission_type` |
| `phone_unlock.popover.open` | Click locked pill | `lead_id`, `contact_id` (hash), `is_fast_unlock_active` |
| `phone_unlock.confirm` | Click “Mở khóa SĐT” | `fast_unlock_enabled`, `cost_credits` |
| `phone_unlock.fast.unlock` | Fast unlock click | `time_since_session_start` |
| `phone_unlock.undo` | Click “Hoàn tác” | `time_to_undo_ms` |
| `phone_unlock.error` | Unlock error | `status_code`, `reason` |

**Success metrics:**
- Tỷ lệ user mở popover rồi click Hủy (drop-off) < 30%.
- Tỷ lệ undo < 5% (cho thấy không có accidental unlock nhiều).
- Thời gian từ click pill đến unlock thành công < 2s.
- Tỷ lệ tải deliverable thành công > 95%.

---

## 9. Acceptance Criteria

### 9.1. Mission Control

- [ ] Widget title là `Trợ lý tìm lead` và hiển thị query mission.
- [ ] Phase badge dùng tiếng Việt user-friendly.
- [ ] Progress bar có animation khi mission đang chạy.
- [ ] Token velocity hiển thị cost bằng cả credits và dollar equivalent.
- [ ] Deliverable card hiển thị metadata (sources, topics, size) và badge PII khi cần.
- [ ] Sau download, Sonner toast xác nhận.
- [ ] CoT section mở rộng subtask hiện tại theo mặc định.

### 9.2. SmartUnlockPopover

- [ ] Popover hiển thị masked phone preview.
- [ ] Cost hiển thị `credits + dollar equivalent`.
- [ ] Fast unlock checkbox mặc định unchecked, label rõ TTL 15 phút.
- [ ] Bulk unlock luôn hiện popover và hiển thị tổng cost.
- [ ] Lỗi 402/403 hiển thị message phù hợp.
- [ ] Popover đóng khi click Esc hoặc Hủy.

### 9.3. PhoneUnlockPill

- [ ] Locked pill dùng màu trung tính, unlocked pill dùng màu emerald.
- [ ] Click locked pill mở popover (hoặc fast unlock nếu active).
- [ ] Fast unlock session TTL 15 phút, expire khi rời leads view.
- [ ] Flip animation 150ms khi unlock/relock.
- [ ] Toast success có nút Hoàn tác; single unlock 30s, fast unlock 10s.
- [ ] `aria-label` đầy đủ cho 3 states (locked/unlocked/disabled).

---

## 10. Out of Scope

- Real mission cancel (FR-38 deferred).
- Budget cap UI (liên quan Epic 8 `8-7-auto-extract-spend-budget-cap`).
- Deep research latency State A/B gate (NFR-9, cần Epic 43).
- Mobile redesign toàn bộ Split Canvas; spec này chỉ tối ưu widget & pill.
- Thay đổi backend unlock cost hoặc relock SLA.

---

## 11. Open Questions

1. **Currency display:** Dollar equivalent là USD, hay cần hiển thị VND cho market VN? Có cần localize theo user settings?
2. **Budget progress:** Có API trả về `workspace.credit_micros_balance` real-time cho widget không?
3. **PII deliverable:** Khi nào `include_pii` sẽ true? Có cần thêm bước xác nhận bổ sung trước khi tải file PII?
4. **Fast unlock scope:** Nên giữ ở mức workspace hay global user session? Hiện tại là `workspaceId + userId`.

---

## 12. References

- `MissionControlWidget.tsx` <ref_file file="/Users/luisphan/Documents/GitHub/nowing/nowing_web/components/leads/MissionControlWidget.tsx" />
- `PhoneUnlockPill.tsx` <ref_file file="/Users/luisphan/Documents/GitHub/nowing/nowing_web/components/leads/PhoneUnlockPill.tsx" />
- `SmartUnlockPopover.tsx` <ref_file file="/Users/luisphan/Documents/GitHub/nowing/nowing_web/components/leads/SmartUnlockPopover.tsx" />
- Epic 26.5 spec: `_bmad-output/implementation-artifacts/26-5-split-canvas-glass-box-mission-control-two-tier-phone-unlock-shimmer-influx.md`
