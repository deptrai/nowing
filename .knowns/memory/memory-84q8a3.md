---
id: 84q8a3
title: 'Thứ tự chẩn đoán: nội bộ trước, ngoài DNS sau'
layer: project
category: convention
status: active
tags:
  - debug
  - ops
  - dokploy
  - convention
createdAt: '2026-07-28T13:40:22.933Z'
updatedAt: '2026-07-28T13:40:22.933Z'
---

Luôn curl nội bộ trước (container còn sống không), rồi mới curl ngoài qua DNS (đường vào có thông không). Thứ tự này tách bạch lỗi app và lỗi routing.
