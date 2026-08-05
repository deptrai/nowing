# UX Contract — Sync & Offline Indicator

**Ngày:** 2026-08-05
**Phạm vi:** UX cho trạng thái sync (Zero cache, auth cookie cross-subdomain) và offline/degraded mode.
**Bám vào:** AD-4 (Redis) · AD-5 (Zero) · FR-38 (degradation) · AD-18 (memory bounds)
**Loại tài liệu:** *contract* — định nghĩa trạng thái UI phải biểu diễn được.

---

## 1. Bài toán UX

Nowing dùng Zero cache trên subdomain `zero.nowing.net`, backend trên `api.nowing.net`, frontend trên `nowing.net`. Auth cookie cross-subdomain bị mất → sync 401 → dashboard log out. Và deep-research có thể degrade khi engine không khả dụng.

Hệ quả UX:
- User cần biết khi nào đang offline, khi nào đang dùng kết quả từ local cache, khi nào deep-research degrade sang hybrid search.

## 2. Contract — các trạng thái UI bắt buộc

| # | Trạng thái | Bắt buộc |
|---|---|---|
| S1 | **Online** — kết nối backend/Zero bình thường | ✅ |
| S2 | **Syncing** — có thay đổi đang đẩy lên/lấy về từ Zero | ✅ |
| S3 | **Offline with local cache** — mất kết nối nhưng dữ liệu local vẫn đọc được; hiển thị "offline" + "last synced at" | ✅ |
| S4 | **Auth cookie domain error** — khi Zero trả 401 sau auth-retry, hiển thị "Sync session expired — please log in again" | ✅ |
| S5 | **Deep-research degraded** — khi engine unavailable, hiển thị kết quả từ hybrid search với nhãn "Results from workspace memory; deep research unavailable" | ✅ |
| S6 | **Partial result** — khi engine trả `partial`/`insufficientEvidence`, hiển thị rõ reason và action gợi ý (đổi câu hỏi / thử lại) | ✅ |

## 3. Ràng buộc kỹ thuật UX

- `COOKIE_DOMAIN=nowing.net` trong backend production để cookie auth cross-subdomain.
- Zero sync error phải được catch và hiển thị ở UI, không console log.
- Degraded state từ FR-38 phải phân biệt với lỗi 500.

## 4. Truy vết

- Chặn: story 9.1a (FR-38), story 9.3 (NFR-9)
- Phụ thuộc: `COOKIE_DOMAIN`, `zero.nowing.net`, `api.nowing.net`
