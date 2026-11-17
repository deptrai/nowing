# Epic 41 Context: Websets Integration

<!-- Generated from planning artifacts. Regenerate with compile-epic-context if planning docs change. -->

## Goal

Biến Nowing thành consumer chính thức của ChainLens Websets (Epic 57) — khởi tạo dataset build bất đồng bộ qua `POST /v1/websets` (giao phó toàn bộ discovery qua Medirus, criteria verification và web enrichment cho ChainLens), tiếp nhận webhook `webset.idle` khi pipeline hoàn tất để tự động import các thực thể `verified`/`ready` vào Lead pipeline của Nowing, đồng thời thực thi cơ chế soft-lock và debit credit theo từng lead thành công mà không phải scrape, enrich hay xây dựng giao diện dataset dashboard nội bộ.

## Stories

- Story 41.1: Websets API Client & Idle Webhook Handler
- Story 41.2: Websets→Lead Mapper, Billing Gate & Source Badge

## Requirements & Constraints

- **ChainLens Websets Outbound Client (Story 41.1):**
  - **Auth & Connectivity:** Gọi ChainLens REST surface với header `Authorization: Bearer <CHAINLENS_API_KEY>`, áp dụng timeout/circuit-breaker conventions từ Story 40.5 (fail-fast, trả typed `degraded` khi ChainLens 5xx/unreachable, tuyệt đối không treo request).
  - **Tạo Webset (`POST /v1/websets`):** Payload gồm:
    - `source`: `{type: 'web' | 'medirus', platform?: string, action?: string}`.
    - `columns`: mảng cột với key định dạng `^[a-z0-9_]{1,64}$`, kiểu dữ liệu thuộc `{text, number, date, options, email, phone, url}`.
    - `criteria`: `{prompt: string (≤ 10_000 chars), rules: array (≤ 50 rules), operators: ['eq', 'gt', 'gte', 'lt', 'lte', 'contains']}`.
    - `metadata.webhookUrl`: URL callback của Nowing với token bí mật nhúng sẵn: `{BACKEND_URL}/api/v1/webhooks/chainlens/webset-idle?t=<per_webset_secret>`.
  - **Lấy Metadata (`GET /v1/websets/:id`):** Chỉ trả metadata và thống kê tiến độ, không trả dữ liệu dòng entity.
  - **Drain Items (`GET /v1/websets/:id/items`):** Phân trang bằng keyset cursor (`limit ≤ 100`, lọc `status=ready,verified`), lặp drain đến khi `nextCursor` vắng mặt.
  - **Entity Status Lifecycle:** `pending_verification`, `rejected`, `verified`, `enriching`, `ready`, `failed`, `quota_exceeded`. Chỉ chấp nhận import thực thể có trạng thái `ready` hoặc `verified`; bỏ qua các trạng thái còn lại.
- **Inbound Idle Webhook (`POST /api/v1/webhooks/chainlens/webset-idle`):**
  - Gắn vào router `app/routes/chainlens_webhooks.py` (prefix `/api/v1/webhooks/chainlens`).
  - **Webhook Payload (`webset.idle`):** Plain JSON body `{event: 'webset.idle', id: string, websetId: string, runId: string, stats: object, costDollars: number, completedAt: string}`, đi kèm header `User-Agent: ChainLens-Webhook/1.0`.
  - **Authentication:** Do ChainLens gửi plain JSON không kèm signature header (khác với monitor HMAC webhook), Nowing xác thực bằng token `t` trong query param đối chiếu constant-time với secret lưu trong DB; trả về HTTP 2xx dưới 1s, từ chối 401 nếu thiếu/sai token.
  - **Idempotency:** ChainLens retry 3 lần (2s, 8s, 32s); Nowing dedup qua delivery UUID `id` (Redis/DB) để tránh kích hoạt Celery import task trùng lặp.
- **Lead Mapping & Persistence (Story 41.2):**
  - Thực thể `ready` với `enrichments` (`Record<colKey, {value, status, groundingUrl}>`) được ánh xạ vào schema `Lead`: gán `source = 'websets'`, `source_url` từ entity/grounding URL, điền thông tin công ty/liên hệ từ các cột tương ứng, lưu các cột chưa ánh xạ vào `metadata.websets`.
  - Dedup và bulk ingest thông qua `LeadBatchService.ingest_batch` với `value_hmac` sắp xếp theo thứ tự `ORDER BY value_hmac ASC` để bảo đảm zero deadlock. Idempotent theo cặp `(websetId, entityId)` ngăn nhân bản lead hoặc trừ phí lặp lại.
- **Billing Gate:** Soft-lock credit trước khi import và thực hiện debit theo số lượng lead import thành công ở mức 1.5 credits/lead (kế thừa Epic 40). Khi số dư không đủ, ngắt import và đánh dấu `quota_exceeded` trên campaign. Trường `costDollars` từ ChainLens chỉ dùng ghi nhận telemetry nội bộ.

## Technical Decisions

- **Table `webset_campaigns`:** Tạo bảng qua Alembic migration để liên kết webhook với campaign: gồm `webset_id` (VARCHAR/UUID, UNIQUE indexed bắt buộc vì webhook payload chỉ mang `websetId`), `campaign_id`, `workspace_id`, `webhook_secret`, `stats` (JSONB), `last_delivery_id`, và `imported_count`.
- **Webhook Token Auth vs HMAC:** ChainLens `webset.idle` delivery (`apps/worker/src/lib/webhook-delivery.service.ts`) chưa hỗ trợ HMAC signing như pulse monitor webhooks. Giải pháp chuẩn là token bí mật ngẫu nhiên mã hóa an toàn trên từng webset nhúng vào URL query (`?t=...`), đối chiếu constant-time phía Nowing.
- **LeadSourceAdapter Pattern:** Triển khai `WebsetsAdapter` tại `app/lead_intelligence/adapters/websets.py` và đăng ký vào `LeadSourceAdapterRegistry` (mô hình Story 21.15). Phương thức `execute()` tạo webset từ xa, lưu bản ghi `webset_campaigns` và trả về `status='pending'` ngay lập tức.
- **Tái sử dụng `BACKEND_URL`:** Khai thác biến môi trường sẵn có từ `app/config/urls.py` (`https://api.nowing.net` trên prod) để dựng URL webhook gửi sang ChainLens, không thêm biến môi trường mới.
- **Deduplication qua `value_hmac`:** Ingestion lead tuân thủ quy chuẩn AD-109 / Epic 23 với khóa `value_hmac` (SHA256 danh tính lead/công ty/liên hệ) kèm `ON CONFLICT (workspace_id, value_hmac)` để tránh trùng lead trên toàn workspace.
- **Async Pending Semantics:** Khác với nguồn cào đồng bộ, webset build là tiến trình kéo dài; trạng thái `pending` của campaign là luồng vận hành bình thường, không coi là lỗi hay `degraded`.

## UX & Interaction Patterns

- **Bộ lọc nguồn Lead Matrix:** Thêm lựa chọn `websets` vào mảng chip `SOURCE_FILTERS` và bổ sung nhánh lọc tương ứng trong predicate tại `nowing_web/components/leads/NowingLeadMatrix.tsx`.
- **Huy hiệu nguồn (Lead Badge):** Hiển thị badge/tag định danh nguồn `websets` trên các bảng Lead Matrix và Split-Canvas cho lead được import.
- **Hiển thị trạng thái Pending:** `PlanSummaryCard` hiển thị phân bổ nguồn websets ở trạng thái `status='pending'` với giao diện xử lý tiến trình (badge kèm hiệu ứng spinner/pulse như "Đang xây dataset qua ChainLens…"), phân biệt rõ ràng với trạng thái cảnh báo `degraded`.
- **Phạm vi giao diện:** Không phát triển UI quản lý hay builder dataset trong Nowing; toàn bộ tác vụ tạo/sửa tiêu chí dataset thuộc về ChainLens dashboard.

## Cross-Story Dependencies

- **41.2 phụ thuộc 41.1:** Tác vụ ánh xạ lead, trừ credit và hiển thị badge (Story 41.2) đòi hỏi hoàn thiện bảng `webset_campaigns`, adapter khởi tạo webset, và webhook endpoint tiếp nhận sự kiện `webset.idle` kèm Celery import task từ Story 41.1.
- **Phụ thuộc Upstream:** ChainLens REST surface `/v1/websets` và bộ xử lý `webset-run.processor.ts` (Epic 57) đã sẵn sàng trên môi trường staging/production.
