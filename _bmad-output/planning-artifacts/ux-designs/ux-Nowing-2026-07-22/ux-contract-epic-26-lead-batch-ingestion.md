# UX Contract — Epic 26 Lead Batch Ingestion & ChainLens Pipeline

**Ngày:** 2026-08-17
**Phạm vi:** UX cho batch lead ingestion, stateless ChainLens chunk ingestion, PII vault, contact unlock, và PII opt-out (Story 26.1 · AD-101–AD-110).
**Bám vào:** FR-84 · FR-85 · FR-89 · FR-92 · AD-105 · AD-110 · NFR-9 (State A async for research)
**Loại tài liệu:** *contract* — định nghĩa trạng thái UI phải biểu diễn được.

---

## 1. Bài toán UX

DSH sidecar hoặc ChainLens crawler đẩy hàng trăm lead/chunk vào Nowing. Workspace user cần:
1. Thấy lead mới xuất hiện real-time trên lead matrix/Kanban mà không reload trang.
2. Biết liên hệ nào bị blacklist hoặc đã verified.
3. Mở khóa liên hệ với cost rõ ràng (1.5 credits) và audit.
4. Thực hiện opt-out PII đúng quy định Decree 13/PDPD.

## 2. Contract — các trạng thái UI bắt buộc

| # | Trạng thái | Bắt buộc |
|---|---|---|
| L1 | **Batch ingestion in-progress** — hiển thị progress cho `dsh-worker` task: `queued → running → completed/failed`, số lead received/ingested/skipped | ✅ |
| L2 | **Lead matrix real-time update** — khi `leads` table thay đổi qua `zero_publication`, row xuất hiện/cập nhật trên Kanban trong < 1s mà không reload | ✅ |
| L3 | **Masked contact display** — mặc định phone/email hiển thị dạng `0908 *** 456` / `luan.***@gmail.com` cho đến khi unlock | ✅ |
| L4 | **Two-Tier Unlock** — Tier 1: click "Unlock" → confirm debit 1.5 credits → Tier 2: hiển thị plaintext phone/email; ghi `pii_access_audit_logs` | ✅ |
| L5 | **Insufficient balance state** — nếu `User.credit_micros_balance < 1_500`, disable unlock và hiển thị "Add credits" CTA | ✅ |
| L6 | **Blacklisted lead row** — lead trong `global_dnc_records`/`workspace_dnc_records` hiển thị badge `Suppressed`, không có nút unlock, không lộ PII | ✅ |
| L7 | **Opt-out / blacklist form** — user/workspace owner có thể submit PII để suppress; sau submit hiển thị `Processing → Suppressed → Refund 15% max` | ✅ |
| L8 | **ChainLens chunk status** — hiển thị `ingest_job` status (`ok`/`partial`/`noop`), số chunks received/ingested, `noop_source_ids` nếu có | ✅ |
| L9 | **Async research deliverable (NFR-9 State A)** — khi chunk ingestion xong, user nhận notification/research deliverable, không chờ sync response | ✅ |

## 3. Ràng buộc kỹ thuật UX

- `leads` table được publish qua `zero_publication` với PII-safe column list (AD-104).
- `chunks` table **không** publish qua `zero_publication`; chunk status lấy từ `chainlens_ingest_jobs` qua REST query hoặc notification.
- Contact unlock gọi `POST /api/v1/workspaces/:workspace_id/leads/:lead_id/contacts/:contact_id/unlock` và cập nhật `verified_contacts.is_unlocked` real-time qua Zero.
- Unlock debit `wallet_credit.apply_debit` + `BillingEvent`; UI phải chờ response thành công mới reveal PII.
- PII opt-out gọi endpoint mới (tạo trong Story 26.2 hoặc task tiếp theo) để thêm HMAC vào DNC table + `is_unlocked = FALSE` + refund.

## 4. Truy vết

- Chặn: Story 26.1
- Phụ thuộc: AD-101 (ChainLens → Nowing), AD-104 (Zero-Cache CDC), AD-105 (PII vault), AD-110 (opt-out/refund), AD-109 (batch endpoint)
- Cần story con: 26.2 Lead Matrix/Kanban UI update, 26.3 Contact Unlock UI, 26.4 PII Opt-Out UI (hoặc gộp vào epic UI khác).
