# UX Contract — Async Deep Research (progress-first)

**Ngày:** 2026-07-25
**Phạm vi:** **CHỈ** hạng mục UX đang **chặn** story `9-3`. Hai hạng mục UX còn lại được **hoãn tường minh** — xem §6.
**Bám vào:** NFR-9 State A · `AD-17` · `AD-18` · FR-38 · readiness U-1 / U-2 / U-3
**Loại tài liệu:** *contract*, không phải design spec. Nó định nghĩa **UI phải biểu diễn được những trạng thái nào**, không định nghĩa layout/màu/typography.

---

## 1. Vì sao chỉ có một file trong folder này

Readiness report 2026-07-25 ghi `ux-designs/` = **0 file** trong khi có **5 client surface** → `[WARNING]`. Ba hạng mục UI bị nêu tên:

| Hạng mục | Chặn gì | Xử lý |
|---|---|---|
| **Async deep-research progress-first** | Story `9-3` | ✅ **File này** |
| UI memory browser / research timeline | — (không ở launch gate) | ⏸️ Hoãn, §6 |
| Usage dashboard | — (`8-3` = done) | ⏸️ Hoãn, §6 |

Viết một UX suite đầy đủ lúc này là làm sai thứ tự: chỉ hạng mục đầu có story đang chờ nó. Hai hạng mục sau **có trigger rõ ràng** để mở lại (§6), không phải bị bỏ quên.

---

## 2. Bài toán: thao tác tới 300s trong một sản phẩm chat

`CHAINLENS_TIMEOUT` = **300s**. Agent door hiện **SYNC** (`app/capabilities/core/access/agent.py`) ⇒ deep research **chặn** lượt chat tới 5 phút. Đó là lý do NFR-9 State A bắt buộc async.

Hệ quả UX: **không được có khoảng trống câm.** Một spinner 5 phút không phân biệt được với "sản phẩm treo".

## 3. ⚠️ Cải chính U-3 — engine CÓ emit progress; lỗi ở parser Nowing

Readiness U-3 ghi *"engine chỉ emit 2 progress event (starting/done) ⇒ UX progress-first không có gì hiển thị"*. **Không đúng**, và đây là cải chính quan trọng vì nó quyết định UX này có khả thi hay không.

- ChainLens **có** emit progress: `apps/api/src/search/api.ts:414`, `:1298`, `:221`, `:1299`.
- Nowing `_parse_sse` chỉ dispatch `error` / `done` / `block` / `updateBlock`, và block chỉ đọc `text` + `source`. Nó **bỏ 6 loại event**: `progress`, `insufficientEvidence`, `partial`, `synthesizing`, `heartbeat`, `noop`.
- ⇒ **Có sẵn nguyên liệu để hiển thị.** Việc cần làm là sửa parser (`9-1b`), không phải xin engine emit thêm.
- Đây cũng là lý do **OQ-7 Q4 đã RÚT** — không phải việc của ChainLens.

## 4. Contract — các trạng thái UI **bắt buộc** biểu diễn được

Nguồn: `run_event_bus` SSE (`GET .../runs/{run_id}/events`, `rest.py:493`) + ring buffer 500 event.

| # | Trạng thái | Nguồn event | Bắt buộc |
|---|---|---|---|
| S1 | **Đã nhận, đang chạy** — có `run_id`, chat turn **đã kết thúc** | 202 + `X-Run-Id` (`rest.py:312`) | ✅ |
| S2 | **Đang tiến triển** — hiển thị việc engine đang làm | `progress` | ✅ |
| S3 | **Đang tổng hợp** — đã crawl xong, đang viết | `synthesizing` | ✅ |
| S4 | **Kết quả một phần** — có nội dung nhưng chưa xong | `partial` | ✅ |
| S5 | **Không đủ bằng chứng** — engine chạy xong nhưng không kết luận được | `insufficientEvidence` | ✅ |
| S6 | **Còn sống** — không có tiến triển mới nhưng chưa chết | `heartbeat` | ✅ |
| S7 | **Xong** | `done` / `run.finished` | ✅ |
| S8 | **Lỗi / hết giờ** | `error`, `CHAINLENS_TIMEOUT` | ✅ |
| S9 | **Engine không khả dụng → đã degrade sang hybrid search nội bộ** | FR-38 | ✅ |
| S10 | **Đã huỷ** | `POST .../runs/{id}/cancel` (`rest.py:559`) | ✅ |

### Ba rule không được vi phạm

**R1 — S5, S8, S9 phải PHÂN BIỆT ĐƯỢC với nhau trong UI.**
Hiện tại code **không** phân biệt được: `executor.py:192-198` chỉ raise `CHAINLENS_TIMEOUT`, và heuristic suy đoán là
`if not answer and not sources: if saw_done → insufficient_evidence else → timeout`.
Đây là **suy đoán, sai được**. UI **không được** hiển thị "không tìm thấy gì" khi thực tế là engine chết — hai thứ này dẫn tới hai hành động khác nhau của người dùng (đổi câu hỏi vs. thử lại sau).

**R2 — S9 phải nói rõ nguồn kết quả.**
Với self-host, engine **luôn** không khả dụng (D5 Phase 1 cloud-only). Kết quả đến từ hybrid search nội bộ **phải được ghi nhãn tường minh**, không được trình bày như deep research. Đây là yêu cầu **mô hình kinh doanh**, không phải mỹ học — xem FR-38.

**R3 — Reconnect không được mất tiến trình.**
Ring buffer 500 event đã có. UI reload/mất mạng → tail lại và **replay**, không quay về S1.

## 5. Ràng buộc kỹ thuật UX phải tôn trọng

- **`runs` KHÔNG vào Zero publication** (`AD-5`, quyết định U-2). Delivery đi **SSE**. Không polling.
- **Bus hiện single-process.** Docstring `app/capabilities/core/events.py` tự ghi cần Redis pub/sub cho multi-worker. Nhiều replica → client tail ở replica A **không thấy** event của run ở replica B, **im lặng, không lỗi**. ⇒ Progress UI **không được bật trên môi trường nhiều replica** trước khi `9-3` xong phần Redis-backed bus.
- **Typed client đã có:** `nowing_web/lib/apis/scrapers-api.service.ts:68` (`?mode=async`), `contracts/types/scraper.types.ts:56` (response 202). **Không** viết client mới.
- Có `notifications` trong `ZERO_PUBLICATION` (`app/zero_publication.py:81-94`) ⇒ thông báo "research xong" đi được qua Zero, dù `runs` thì không.

## 6. Hoãn tường minh — hai hạng mục còn lại

Đây là **hoãn có chủ**, không phải bỏ sót. Ghi vào readiness report cùng lượt này.

| Hạng mục | Vì sao hoãn được | Trigger mở lại |
|---|---|---|
| **UI memory browser / research timeline** (PRD §6.2) | Không có story nào đang chờ. Và **cần chờ `3-14`**: chưa chốt chặn trên + top-k retrieval thì chưa biết browser hiển thị **cái gì** — toàn bộ N fact, hay chỉ top-k? Thiết kế trước `AD-18` là thiết kế trên nền chưa đông. | `3-14` done **và** `3-13` (FR-40) done → lúc đó memory mới có provenance thật để timeline có nghĩa |
| **Usage dashboard** | `8-3` đã `done`. Rủi ro thật không phải thiếu design mà là **số hiển thị đang sai**: `costDollars` chưa parse (grep = 0 hit) và metering under-meter **2.1–3.3×** (`CHAINLENS_QUERY_MICROS_PER_CALL = 5000` phẳng vs. target $0.0105 của mode `quality`). | `9-2` (FR-37) có số cost đo thật → khi đó mới biết dashboard cần sửa gì. Thiết kế lại trước `9-2` là vẽ trên số sai |

**Điểm chung:** cả hai đều **phụ thuộc quyết định kỹ thuật chưa chốt**. Vẽ UX bây giờ tạo ra artifact phải bỏ. Việc hoãn này **không** chặn launch gate nào.

---

## 7. Truy vết

- Chặn: story `9-3` (NFR-9 State A) · phụ thuộc parser fix ở `9-1b`
- Rule R2 phụ thuộc `9-1a` (FR-38 degradation — **tiền đề trước khi public repo**, D5)
- `AD-17` (async door sẵn có) · `AD-18` (bounded memory) · `AD-5` (Zero scope)
- Đóng readiness item 16; cải chính **U-3**
