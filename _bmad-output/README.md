# Nowing — Planning & Implementation Artifacts

Hồ sơ quyết định (BMad artifacts) của Nowing: PRD, epics, architecture spine, brief, sprint-change proposal, readiness report, story file, ATDD checklist, UX contract.

## ⚠️ Vì sao repo NÀY tách khỏi repo code

**Repo code `deptrai/nowing` dự kiến sẽ PUBLIC** (quyết định `D5`; story `9-1a` là tiền đề). Nếu để các artifact này trong repo đó, tới lúc public sẽ công khai luôn ba nhóm nội dung **không nên công khai**:

1. **Đơn vị kinh tế** — cost per call, tỉ lệ under-meter, cost basis cho pricing. Công bố cái này là đưa unit economics cho đối thủ và đưa giá vốn cho khách, **trước khi** chốt giá. Cổng `9-2` nói rõ: không chốt pricing trước khi có số đo thật.
2. **Tài liệu của team khác** — `oq7-answers-to-chainlens-*.md` chứa câu hỏi nội bộ của team ChainLens **và đường dẫn file nội bộ của ChainLens**. ChainLens là **closed-source** (`D5`, `AD-16`). Công khai đường dẫn + nội tại của nó là làm lộ nó.
3. **Bản tự liệt kê lỗi** — readiness report ghi rõ các lỗi thương mại đang tồn tại. Công bố đúng vào lúc đi public là tự ghi bàn vào lưới mình.

Một phần artifact thì công khai lại **tốt** (epics, architecture spine, PRD features — roadmap mở là tài sản PLG). Nhưng cách đúng là **curate một tập public có chủ đích sau**, không phải để nó lọt ra như hệ quả phụ của `.gitignore`.

**Chọn ranh giới repo thay vì allowlist trong `.gitignore`** vì allowlist trong một repo sắp public là bẫy thường trú: chỉ cần một file mới rơi sai tầng là nó ship. Ranh giới repo không lộ do vô ý được.

## Quan hệ với repo code

- Repo code: `deptrai/nowing` — `.gitignore:33` có `_bmad-output/`, **giữ nguyên như vậy**.
- Thư mục này nằm *trong* cây làm việc của repo code nhưng là **repo git độc lập**. Repo code ignore nó nên không có xung đột.
- `implementation-artifacts/sprint-status.yaml` trước đây bị force-add vào repo code ⇒ nó là **file duy nhất trong 69 file** từng được version, khiến git history của repo code cho thấy story đổi trạng thái mà **không có lý do kèm theo**. Repo này sửa điều đó: mọi thứ giải thích cho `sprint-status.yaml` giờ nằm cùng chỗ với nó.

## Cấu trúc

```
planning-artifacts/        PRD · epics · architecture spine · brief · SCP · readiness report · UX contract
implementation-artifacts/  sprint-status.yaml · story file · deferred-work · merge-to-prod checklist
test-artifacts/            ATDD checklist · test design · framework validation
```

Output công cụ (mutation testing `.sqlite`/`.jsonl`, ~8,1 MB) bị ignore — xem `.gitignore`.

## Nguồn chân lý

- **Tiến độ story:** `implementation-artifacts/sprint-status.yaml`
- **Bất biến kiến trúc:** `planning-artifacts/architecture/architecture-Nowing-2026-07-22/ARCHITECTURE-SPINE.md` (`AD-1`…`AD-18`)
- **Yêu cầu:** `planning-artifacts/prds/prd-Nowing-2026-07-22/prd.md` (FR-1…FR-40, NFR-1a…NFR-9)
