---
id: nkp6st
title: 8-11-admin-ui-global-llm-model-config
status: todo
priority: medium
labels:
  - epic-8
  - backlog
createdAt: '2026-07-28T10:28:33.547Z'
updatedAt: '2026-07-28T13:32:42.748Z'
timeSpent: 0
parent: pqriro
spec: planning/nowing-epics
order: 10
---
# 8-11-admin-ui-global-llm-model-config

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
MỚI 2026-07-26 — FR-41. Global model config hiện chỉ sửa qua YAML/.env (GLOBAL_LLM_CONFIG_B64) + restart backend, không UI, không hot-reload. Cần khái niệm platform-admin mới (tái dùng User.is_superuser đã có, chưa gate gì); mở write cho Connection/Model scope=GLOBAL cho riêng path admin; mở rộng materialize_global_model_catalog() merge thêm nguồn DB; hot-reload qua refresh_global_model_catalog() (seam đã có). Model file-backed (YAML/env) giữ read-only qua UI.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
<!-- AC:END -->

