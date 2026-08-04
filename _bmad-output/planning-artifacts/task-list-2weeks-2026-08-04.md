# Task list — 2 tuần (bdsai pilot BĐS)

> **Nguyên tắc phân loại:** 2 tuần pilot tập trung **cầu + validation**. Công việc non-code làm tay trong 2 tuần. Công việc code được chuẩn bị tài liệu đầy đủ (BMAD story/spec) để dev sau, nhưng chỉ triển khai **thin slice** nếu pilot xanh.

---

## A. NON-CODE — Tuần này (ưu tiên số 1)

### Ngày 0 — Chuẩn bị pilot
- [ ] **A1.** Chốt hook Deal-Radar + 3 biến thể (đã có)
- [ ] **A2.** Quay demo 60s "AI Deal-Radar" cho môi giới
- [ ] **A3.** Import tracker CSV vào Google Sheets
- [ ] **A4.** Lập danh sách ≥30 môi giới Bình Thạnh 3-4 tỷ (FB group / Chợ Tốt / Zalo / TikTok)
- [ ] **A5.** Tạo tài khoản Zalo burner + group Zalo private cho pilot
- [ ] **A6.** Viết/chạy script zca-js: gửi tin vào group Zalo (test gửi 1 tin)
- [ ] **A7.** Gắn 5 sự kiện đo: signup, tool_used, filter_created, alert_sent, return

### Tuần 1 (Ngày 1-7) — Tuyển + kích hoạt
- [ ] **A8.** Ngày 1: nhắn 10-15 môi giới (script mở đầu) → mục tiêu 3-5 rep
- [ ] **A9.** Ngày 2: onboard người rep vào group + tạo Deal-Radar filter đầu cho họ; nhắn 10-15 người mới
- [ ] **A10.** Ngày 3: follow-up người chưa rep; phỏng vấn nhanh 2-3 người đã dùng
- [ ] **A11.** Ngày 4: vá 1-2 điểm ma sát onboarding; tiếp tục nhắn
- [ ] **A12.** Ngày 5: bật seed aggregator (tóm tắt facts + nguồn + link) để group có tin khớp gửi vào
- [ ] **A13.** Ngày 6: chạm mốc 30 người thử; ghi ai kích hoạt
- [ ] **A14.** Ngày 7: review tuần 1 — đếm kích hoạt (mục tiêu 15-20), 3 phỏng vấn sâu

### Tuần 2 (Ngày 8-14) — Retention + match + tín hiệu giá
- [ ] **A15.** Ngày 8: nhắn từng người tuần 1 một lý do cụ thể để quay lại
- [ ] **A16.** Ngày 9: gửi ≥1 match thật vào group (Deal-Radar → alert + link)
- [ ] **A17.** Ngày 10: hỏi 5 môi giới "sẽ trả tiền không?" (chỉ hỏi, chưa thu)
- [ ] **A18.** Ngày 11: vá điểm ma sát retention; tạo thêm 1 match
- [ ] **A19.** Ngày 12: nhờ 2-3 người hài lòng giới thiệu 1 đồng nghiệp
- [ ] **A20.** Ngày 13: tổng hợp số (retention tuần 2, match, WTP) vào tracker
- [ ] **A21.** Ngày 14: GATE go/no-go + viết retro 1 trang

### Song song (không chặn pilot)
- [ ] **A22.** Gửi 3 câu hỏi cho luật sư: dùng code crawler kế thừa thương mại · ToS/robots 3 sàn khi aggregate · PDPD khi lưu tin trong workspace
- [ ] **A23.** Hỏi thử 1-2 portal về licensed feed / đối tác referral

---

## B. CODE — Chuẩn bị tài liệu BMAD (story/spec), KHÔNG code to trong 2 tuần

> Các công việc dưới đây cần chạy qua đủ quy trình BMAD: `bmad-create-epics-and-stories` → `bmad-create-story` → `bmad-spec` → `bmad-ux` (nếu cần UI) → `bmad-architecture` (nếu cần AD mới).  
> **Không viết code trước khi có story file được review.**

| # | Công việc code | BMAD skill | Mục đích | Ưu tiên chuẩn bị | Trạng thái |
|---|---|---|---|---|---|
| **B1** | **Rebrand Long Thành → Bình Thạnh + bdsai.vn** | `bmad-create-story` | Đổi copy, metadata, SEO, logo cho đúng vision mới | P0 | ✅ Story 3.6 trong epics.md |
| **B2** | **Deal-Radar MVP** — filter bằng lời, alert vào Zalo group riêng | `bmad-create-story` → `bmad-spec` | Core tool cho môi giới, cần pilot | P0 | ✅ Story 5.1 + spec |
| **B3** | **Dashboard CRM layout mới** — sidebar workspace cho môi giới | `bmad-ux` → `bmad-create-story` | Chuyển dashboard từ marketplace sang CRM | P0 | ✅ Story 5.3 + UX spec |
| **B4** | **Lead management** — CRUD lead, trạng thái, gán listing | `bmad-create-story` | Quản lý người mua liên hệ | P1 | ✅ Story 5.2 + UX spec |
| **B5** | **AI viết tin đăng** trong form đăng tin | `bmad-create-story` → `bmad-spec` | Hook free mạnh nhất | P1 | ✅ Story 4.3 + UX spec |
| **B6** | **Nowing engine client** — contract API giữa bdsai và Nowing | `bmad-architecture` → `bmad-spec` | Tích hợp engine | P1 | ✅ Story 7.1 + spec + AD |
| **B7** | **Browser extension MVP** — lưu listing từ BDS/Chợ Tốt vào workspace | `bmad-create-story` → `bmad-spec` | Thay Xaction proxy, hợp pháp hơn | P2 | ✅ Story 7.2a + 7.2b + UX spec |
| **B8** | **Public marketplace tinh chỉnh** — listing card, AI summary buyer | `bmad-ux` → `bmad-create-story` | Trang rao vặt hoàn thiện | P2 | ✅ Story 3.6 |

### Tài liệu đã tạo

- **Epics + Stories:** `_bmad-output/planning-artifacts/epics.md`
- **Implementation Readiness Report:** `_bmad-output/planning-artifacts/implementation-readiness-report-2026-08-04.md`
- **PRD v3.0:** `_bmad-output/planning-artifacts/PRD-bdsai-vision-pivot-2026-08-04.md`
- **Sprint Plan 2 tuần:** `_bmad-output/planning-artifacts/sprint-plan-2weeks-2026-08-04.md`
- **UX spec CRM:** `_bmad-output/planning-artifacts/ux-designs/ux-bdsai-crm-2026-08-04/{DESIGN,EXPERIENCE}.md`
- **Architecture update:** `_bmad-output/planning-artifacts/architecture/ARCHITECTURE-SPINE-UPDATE-2026-08-04.md`
- **Spec Deal-Radar:** `_bmad-output/planning-artifacts/specs/spec-deal-radar-mvp-2026-08-04.md`
- **Spec Nowing Engine Client:** `_bmad-output/planning-artifacts/specs/spec-nowing-engine-client-2026-08-04.md`

---

## C. Wire kỹ thuật tối thiểu (chỉ nếu pilot bắt buộc cần)

> Phần này chỉ làm nếu non-code pilot KHÔNG chạy được do thiếu tool. Mặc định **KHÔNG code** trong 2 tuần.

- [ ] **C1.** Deal-Radar automation nhận filter mô tả bằng lời (verify đã chạy)
- [ ] **C2.** Aggregator: schema chỉ facts (giá/diện tích/quận), badge nguồn + link, KHÔNG SĐT, KHÔNG rehost ảnh
- [ ] **C3.** Kết nối: filter (Zalo) → Deal-Radar → alert + link → gửi vào group Zalo
- [ ] **C4.** Matching cơ bản: người mua đăng nhu cầu → gợi ý tin khớp (aggregated + first-party)

---

## D. KHÔNG làm 2 tuần này (guardrail)

- [ ] ❌ Re-architect toàn bộ hệ thống
- [ ] ❌ Mobile app / full CRM
- [ ] ❌ Thu phí
- [ ] ❌ Tài khoản ảo / đóng vai môi giới / scrape-viết-lại-giấu-nguồn
- [ ] ❌ Auto lấy số điện thoại / kho PII tập trung
- [ ] ❌ Xaction proxy auto-post Facebook/Batdongsan/Chợ Tốt (đã bỏ)

---

## E. Cổng Ngày 14

- [ ] GO nếu: ≥10 quay lại tuần 2 + ≥2 match thật + ≥3 nói sẽ trả tiền
- [ ] Không đạt → chỉnh hook/ngách, chạy lại 1 vòng (chưa xây gì lớn)

---

## F. Quy trình BMAD cho công việc code

1. **Bắt đầu bằng `bmad-create-epics-and-stories`** nếu cần tách epic mới (ví dụ: Epic B — Seller CRM).
2. **Tạo story cụ thể bằng `bmad-create-story <story-id>`** (ví dụ: `bdsai-deal-radar-mvp`).
3. **Nếu story phức tạp hoặc cần contract rõ:** `bmad-spec`.
4. **Nếu cần thiết kế UI:** `bmad-ux`.
5. **Nếu cần architecture decision mới:** `bmad-architecture`.
6. **Sau khi tài liệu xong mới dev:** dùng `bmad-dev-story` hoặc `bmad-quick-dev`.
