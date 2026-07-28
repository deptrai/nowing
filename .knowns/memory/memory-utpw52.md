---
id: utpw52
title: Auto-extract và document retention đã có trong code
layer: project
category: convention
status: active
tags:
  - memory
  - database
  - migration
createdAt: '2026-07-28T13:40:23.193Z'
updatedAt: '2026-07-28T13:40:23.193Z'
---

Code verified: auto-extract default ON (migration 179), document retention (migration 176), dedupe primitive cosine<0.08, memory write route active. Tuy nhiên 175-179 chưa deploy production, prod chỉ đến alembic 174. memory_md rỗng nên không mất dữ liệu hiện tại.
