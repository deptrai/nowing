# Sprint Change Proposal / ADR — Làm rõ DSH: không tích hợp `deepseek-harness` repo trước Closed Beta (2026-08-19)

**Workflow:** `bmad-correct-course`  
**Dự án:** Nowing  
**Ngày lập:** 19/08/2026  
**Chủ trì:** Devin Research Agent (kỹ thuật)  
**Phê duyệt bởi:** Luisphan (PO)  
**Trạng thái:** 🟢 **PROPOSED — AWAITING PO RATIFICATION**  

---

## 1. Bối Cảnh & Vấn Đề Kích Hoạt

Tên `DSH` / `Harness` / `DeepSeek Harness` xuất hiện trong nhiều tài liệu kiến trúc gần đây:

- `ARCHITECTURE-SPINE.md` (2026-08-17): `Agent Orchestration Plane (Harness + dsh Sidecar)`.
- `.memlog.md`: `AD-102 [ADOPTED]: DeepSeek Harness (dsh) is deployed as a decoupled Sidecar container...`
- `sprint-change-proposal-2026-08-17-unified-nowing-chainlens-dsh.md`: `Harness + DeepSeek Harness (dsh): Đóng vai trò Sidecar Autonomous Mission Orchestrator...`

Tuy nhiên, research kỹ thuật (file `technical-deepseek-harness-nowing-chainlens-dsh-research-2026-08-19.md`) cho thấy:

- `github.com/deepseek-ai/deepseek-harness` là một repo **TypeScript/Node.js/Cordis** thật, đang ở **developer preview**.
- Không có dependency nào trong `nowing` hoặc `chainlens-research` trỏ tới repo này (`package.json`, `pyproject.toml`, `requirements.txt`, `Dockerfile` = 0 hit).
- Story 26.2 (`dsh-worker Sidecar Container, Redis Streams & Task Resumption`) đang implement sidecar hoàn toàn bằng **Python** trong `nowing_backend`, dùng Redis Streams + FastAPI REST.

**Vấn đề:** Có sự nhập nhằng giữa tên gọi trong kiến trúc và dependency thực tế. Điều này có thể dẫn đến:
1. Hiểu nhầm rằng closed beta phụ thuộc vào việc tích hợp repo `deepseek-harness`.
2. Lãng phí thời gian đánh giá/viết adapter cho một runtime preview trong giai đoạn quan trọng.
3. Rủi ro PII khi đưa session log của `dsh` vào trước khi đã thiết kế PII boundary.

## 2. Quyết Định Đề Xuất

### D1 — `DSH` trong kiến trúc Nowing là **tên nội bộ** của sidecar, không phải repo `github.com/deepseek-ai/deepseek-harness`

`DSH` = **Domain-Specific Sidecar Harness** (hoặc tên thay thế do PO chốt). Nó là sidecar Python thực hiện các mission 1–8h, không phải runtime `deepseek-harness`.

### D2 — **Không tích hợp** repo `deepseek-harness` trước closed beta

Lý do:
- Preview API/plugin/bundle có thể thay đổi.
- Thêm runtime Node.js/Cordis = tăng ops surface, Docker image mới, secret surface mới.
- PII/session log của `dsh` cần thiết kế lọc trước khi sử dụng.
- Python `dsh-worker` hiện tại đã đáp ứng AD-102, AD-106, AD-107, AD-108 và đang chạy qua evals.

### D3 — Mượn **pattern** từ `Harness` (Supervisor-Specialist, fan-out/fan-in, checkpoint/resumption) nhưng không mượn **runtime**

AD-106 vẫn giữ nguyên: áp dụng mẫu thiết kế Agent Team. Implementation là Python sidecar với FastAPI capabilities + Redis Streams.

### D4 — Mở một **post-beta research/pilot** để đánh giá `deepseek-harness` cho self-host/local IDE experience

Không dùng làm runtime chính cho cloud sidecar trừ khi pilot thành công và có ADR riêng.

## 3. Artifact Impact

| Artifact | Thay đổi | Người làm |
|---|---|---|
| `ARCHITECTURE-SPINE.md` | Sửa mô tả `DSH` / `Harness` thành tên nội bộ; thêm footnote phân biệt với `deepseek-harness` repo | Devin |
| `.memlog.md` | Sửa AD-102 entry để ghi `DSH` là sidecar Python; gợi ý post-beta pilot | Devin |
| `sprint-change-proposal-2026-08-17-unified-nowing-chainlens-dsh.md` | Không sửa (lịch sử), có thể thêm errata nếu cần | PO quyết |
| `technical-deepseek-harness-nowing-chainlens-dsh-research-2026-08-19.md` | Đã có; dùng làm reference | — |
| `dsh-self-host-pilot-plan-2026-08-19.md` | Tạo mới | Devin |

## 4. Rủi Ro & Mitigation

| Rủi ro | Mức độ | Mitigation |
|---|---|---|
| Team vẫn nghĩ DSH = repo DeepSeek Harness | High | Sửa docs + .memlog ngay; thông báo trong standup |
| Post-beta pilot bị quên | Medium | Tạo file pilot plan và đưa vào deferred-work/sprint-status |
| Tích hợp sau này vẫn rối | Medium | Đặt tên rõ ràng: `dsh-worker` (Python) vs `dsh-local-agent` (Node) |

## 5. Điều Kiện Phê Duyệt

- [ ] PO đồng ý với D1–D4.
- [ ] Architecture lead (Winston) xác nhận AD-102/AD-106 vẫn hợp lệ với Python sidecar.
- [ ] Thực hiện sửa `ARCHITECTURE-SPINE.md` + `.memlog.md` trong cùng PR.
- [ ] Không mở story mới liên quan `deepseek-harness` repo trong sprint hiện tại.

## 6. Next Steps

1. Sửa `ARCHITECTURE-SPINE.md` và `.memlog.md` theo D1.
2. Lưu pilot plan `dsh-self-host-pilot-plan-2026-08-19.md`.
3. Cập nhật `sprint-status.yaml` hoặc `deferred-work.md` với item "DSH self-host pilot post-beta".
