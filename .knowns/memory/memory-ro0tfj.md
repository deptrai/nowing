---
id: ro0tfj
title: Xác nhận frontend deploy source và tag
layer: project
category: convention
status: active
tags:
  - frontend
  - deploy
  - dokploy
createdAt: '2026-07-28T13:40:23.272Z'
updatedAt: '2026-07-28T13:40:23.272Z'
---

Frontend nowing vừa khai sourceType=github (repo deptrai/nowing, branch production, path /nowing_web) vừa có dockerImage=ghcr.io/deptrai/nowing-web:develop. Hai nguồn khác nhau, tag develop chứ không phải production. Cần hỏi rõ trước khi deploy frontend.
