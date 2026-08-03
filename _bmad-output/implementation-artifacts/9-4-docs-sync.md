---
story_key: 9-4-docs-sync
epic: 9 — Deep Research đáng tin cậy: không vỡ, không treo, tính phí đúng
priority: P1
requirements: FR-38; AD-15; AD-16; AR-10
status: done
---

# Story 9.4: Docs sync quan hệ Nowing↔engine

## Story

Với tư cách người duy trì repo,
tôi muốn README, docs, `.env.example` nói rõ **Nowing = sản phẩm / ChainLens = engine được host**, và license đúng 3 tầng,
để người dùng self-host không nhầm, luật sư không phàn nàn, và OSS/PLG narrative không bị bóp méo.

## Thay đổi đã làm

### `README.md`
- Title: `Nowing: AI Research Workspace with Open-Source Core + Hosted Deep-Research Engine`.
- Description: nhấn "open-source core" + "hosted deep-research engine (ChainLens)".
- Note block: thêm dòng "The hosted deep-research engine uses an optional cloud API key."
- Why agents need Nowing: bullet 4 thành "Open-source core, self-hostable ... The deep-research engine is a hosted, metered service."
- Comparison table:
  - Pricing: thêm "deep-research engine billed at actual per-call cost".
  - Self Hostable: thêm "deep-research engine is cloud-only in Phase 1".
  - Open Source: thành "Open-source core (Apache 2.0); hosted deep-research engine (BSL 1.1)".
- Các đoạn "open-source product", "open source" unqualified đã được sửa thành "open-source core" / "its core is open source".

### `docs/index.md`
- Tổng quan: thay "open-source NotebookLM alternative" thành "nền tảng nghiên cứu AI với core mã nguồn mở và deep-research engine được host (ChainLens)".
- Thêm **License nhanh**: Apache 2.0 / BSL 1.1 / engine được host, không bán lẻ, không bundled.

### `docs/project-overview.md`
- Executive Summary: cập nhật tương tự `docs/index.md`.
- Thêm section **Lưu ý về license và deep-research engine**: 3 bullet phân biệt core, crawler engine, và hosted deep-research engine.

### `.env.example`
- `docker/.env.example` và `nowing_backend/.env.example`: cập nhật comment `CHAINLENS_API_KEY` rõ ràng là "hosted deep-research engine (cloud-only in self-host Phase 1)".

## Kiểm chứng

- `grep -n "open source\|open-source" README.md` còn 7 matches, tất cả đều có qualifier `core` / `product with an open-source core` / `its core is open source`.
- `README.md` không còn dòng "Yes" cho Open Source row; thay bằng "Open-source core (Apache 2.0); hosted deep-research engine (BSL 1.1)".
- `docs/index.md` và `docs/project-overview.md` nêu rõ 3 tầng license.

## Tác dụng này chưa làm

- README translations (`README.es.md`, `README.pt-BR.md`, `README.hi.md`, `README.zh-CN.md`) chưa cập nhật — có thể sync sau hoặc dùng ghi chú "For latest license/positioning, see README.md".
