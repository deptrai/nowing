# UX Contract — Canonical Entity: Search, Review & Resolution `[DROPPED 2026-08-08]`

> **DROPPED per SCP 2026-08-08.** Epic 13 (`canonical_entities` table, multi-domain indexing, unified search) was removed from Nowing. Canonical entity UX now lives in `chainlens-research`. For the Nowing-side UX, see `ux-contract-ecosystem-search.md` and `ux-contract-private-data-provider.md`. This contract is retained for reference only.

**Ngày:** 2026-08-06
**Phạm vi:** UX cho 4 surfaces của Epic 13 — search results, admin review queue, entity detail & history, conflict resolution.
**Bám vào:** FR-48 · FR-46 · AD-27 · AD-28 · Story 13.1 · Story 13.2 · Story 13.3
**Loại tài liệu:** *contract* — định nghĩa trạng thái UI phải biểu diễn được, không định layout/màu.

---

## 1. Bài toán UX

Epic 13 tạo "canonical entity" — golden record merge từ nhiều nguồn scrape. User thấy unified search results thay vì duplicates. Admin cần review conflicts khi merge không tự động resolve được.

Hệ quả UX:
- Search results phân biệt rõ **canonical entity** (merged) và **document** (raw) — user không bị confused tại sao 3 listings giống nhau → 1 result.
- Admin cần queue để review conflicts — không thể auto-resolve mọi case (price mismatch >20%, location conflict).
- User cần xem nguồn gốc entity (từ đâu, bao nhiêu nguồn, confidence) để quyết định tin hay không.
- Revert merge phải rõ ràng consequences — user không mất data ngoài ý muốn.

---

## 2. Contract — các trạng thái UI bắt buộc

### 2A. Canonical Entity Search Results (Story 13.3)

| # | Trạng thái | Bắt buộc |
|---|-----------|----------|
| A1 | **Distinguish merged vs raw** — Canonical entity card có visual badge "Merged from N sources" khác document card | ✅ |
| A2 | **Source count indicator** — Hiển thị số nguồn với favicon/domain của mỗi nguồn | ✅ |
| A3 | **Expand sources** — Click "View N sources" → inline expand hiển thị source list | ✅ |
| A4 | **Confidence indicator** — Subtle indicator (green/yellow/red dot) khi confidence < 0.9 | ✅ |
| A5 | **Canonical data preview** — Card hiển thị canonical values (merged price, normalized location) | ✅ |

### 2B. Admin Review Queue (Story 13.2)

| # | Trạng thái | Bắt buộc |
|---|-----------|----------|
| B1 | **Queue location** — Dedicated page `/dashboard/[workspace_id]/canonical-review` | ✅ |
| B2 | **Conflict list** — Danh sách conflicts cần review, sort by confidence (lowest first) | ✅ |
| B3 | **Conflict card** — Hiển thị: conflict type, source A value, source B value, suggested resolution | ✅ |
| B4 | **Resolution actions** — [Use A] [Use B] [Use Suggested] [Edit Manually] [Ignore] | ✅ |
| B5 | **Bulk actions** — Select multiple → "Approve all suggested" (confidence >0.7 only) | ✅ |
| B6 | **Empty state** — "No conflicts to review — all entities auto-merged successfully" | ✅ |
| B7 | **Degraded indicator** — Banner khi source fail (degraded=true) | ✅ |

### 2C. Entity Detail & Source History (Story 13.2)

| # | Trạng thái | Bắt buộc |
|---|-----------|----------|
| C1 | **Detail trigger** — Click vào canonical entity → mở detail drawer/slide-over | ✅ |
| C2 | **Canonical data view** — Hiển thị merged data + source count + last updated | ✅ |
| C3 | **Source list** — Liệt kê tất cả nguồn (domain, title, posted date, detail URL) | ✅ |
| C4 | **Merge history timeline** — Vertical timeline mỗi merge event | ✅ |
| C5 | **Revert action** — Revert button (↶) trên mỗi history item + confirmation dialog | ✅ |
| C6 | **Revert confirmation** — Dialog hiển thị consequences (sources unlinked, entity may split) | ✅ |

### 2D. Conflict Resolution Panel (Story 13.2)

| # | Trạng thái | Bắt buộc |
|---|-----------|----------|
| D1 | **Side-by-side comparison** — 2 columns (Source A vs Source B) với diff highlighting | ✅ |
| D2 | **Inline edit** — Click value → text input → save | ✅ |
| D3 | **Strategy buttons** — "Use Source A" / "Use Source B" / "Use Median" / "Custom" | ✅ |
| D4 | **Save resolution** — Conflict moves to "Resolved" tab with timestamp + resolver | ✅ |
| D5 | **Resolved tab** — Separate tab showing recently resolved (last 7 days) | ✅ |

---

## 3. Ràng buộc kỹ thuật UX

- **Search result card** — Canonical entity card tái dùng `SearchResultCard` với prop `variant="canonical"`.
- **Admin route** — Route `/dashboard/[workspace_id]/canonical-review` yêu cầu role Editor+ (AD-9).
- **Detail drawer** — Tái dùng SlideOver pattern từ existing document detail.
- **Real-time updates** — Review queue dùng Zero sync (AD-5) để new conflicts appear real-time.
- **Accessibility** — Conflict cards keyboard navigable, diff highlighting không rely on color alone.
- **i18n** — Conflict type labels localize (price/location/status → tiếng Việt).

---

## 4. User Flows

### Flow 1: User searches and sees canonical results
1. User search "căn hộ Thủ Đức"
2. Results show: canonical entity cards (merged) + document cards (raw)
3. Canonical card có badge "3 sources" + confidence dot
4. User click "View 3 sources" → inline expand
5. User click vào canonical entity → detail drawer opens
6. User thấy merged data + source list + history

### Flow 2: Admin reviews conflict
1. Admin vào `/dashboard/[workspace_id]/canonical-review`
2. Thấy conflict list (sorted by confidence, lowest first)
3. Click vào price conflict card
4. Side-by-side comparison: Source A (3.5 tỷ) vs Source B (4.2 tỷ)
5. Admin click "Use Median" → suggested 3.85 tỷ
6. Admin save → conflict moves to Resolved tab
7. User search results update (confidence → high)

### Flow 3: Admin reverts merge
1. Admin vào entity detail → history timeline
2. Click revert (↶) trên history item
3. Confirmation dialog: "Revert to state before 2026-08-01?"
4. Admin confirm → entity splits back, sources unlinked
5. New conflicts may appear → admin notified

---

## 5. Truy vết

- Chặn: Story 13.2 (FR-48), Story 13.3 (FR-46)
- Phụ thuộc: AD-27 (fingerprint convention), AD-9 (RBAC Editor+)
- Reuses: `ux-contract-admin-global-model-config` (admin UI patterns)
- Reuses: `ux-contract-chat-benchmark` (search quality)

---

## 6. Open Questions

1. **Real-time notification** — Admin có cần notification khi conflict mới appear hay queue refresh đủ?
2. **Auto-resolve threshold** — Confidence > 0.9 auto-merge, nhưng threshold này có nằm trong workspace settings để user tune không?
3. **Revert scope** — Revert single conflict hay entire entity state?
4. **Storage growth** — MergeHistory snapshots có retention policy không? (Gợi ý: 90 ngày, sau đó compress to summary)
