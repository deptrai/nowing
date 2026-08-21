---
title: "AD-28.2 — Data Export / OKF Bundle for Workspace Memory"
status: ADOPTED
date: 2026-08-21
owner: Architecture
binds: FR-95, AR-11, INV-28.4
---

# AD-28.2 — Data Export / OKF Bundle for Workspace Memory

## Context

Epic 28.1 yêu cầu người dùng xuất workspace memory, research threads và citations ra định dạng di động để backup, migrate hoặc rời nền tảng. Nowing đã có OKF bundle format từ document/report export (`app/services/okf/`).

## Decision

Export dùng **OKF làm canonical bundle**, JSON/CSV là **derived views**.

### Bundle structure

```
nowing-export-{workspace_id}-{timestamp}.okf/
├── manifest.json
├── memories/
│   ├── memories.json          # full Memory rows, redacted if user chooses
│   ├── memory_versions.json   # version history
│   └── memory_relations.json  # relation edges
├── research_threads/
│   ├── threads.json
│   └── thread_messages.json   # if user opts in
├── citations/
│   └── citations.csv          # source_type, source_run_id, source_id, citation
└── documents/                 # optional, only if documents also selected
    └── ...
```

### Async streaming

- Dưới 10k rows: đồng bộ, trả `StreamingResponse` ZIP.
- Trên 10k rows: bất đồng bộ, tạo `ExportJob` row, Celery task stream từng batch 1.000 rows, upload part ZIP vào object storage, trả download URL khi xong.

### Redaction & scope

- Export bao gồm **embeddings** nếu `include_embeddings=true`.
- `CSV/JSON human-readable` mặc định **redact** `api_keys`, `oauth_tokens`, `embeddings`.
- Provenance fields (`source_run_id`, `source_uuid`, `source_capability`, `source_input`) được giữ nguyên để re-link sau import.
- Scope strict theo `workspace_id`; không bao giờ export multi-workspace trong một bundle.

### Import fast-follow

- OKF bundle thiết kế để **có thể import**; import là fast-follow (Story 28.x) giảm lock-in fear.
- Bundle version `manifest.okf_version` giúp parser tương lai.

## Consequences

- **Positive:** Đồng nhất với existing OKF infrastructure; không tạo format mới.
- **Positive:** Provenance giữ được, đảm bảo citations tái link.
- **Negative:** Embedding file lớn; cần streaming + part ZIP.
- **Risk:** Import chưa làm; marketing cần ghi rõ "export first, import later".
