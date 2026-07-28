---
id: m80wbo
title: Memory migration FR-36 là ship-gate của nowing
layer: project
category: convention
status: active
tags:
  - prd
  - memory
  - ship-gate
createdAt: '2026-07-28T13:40:23.103Z'
updatedAt: '2026-07-28T13:40:23.103Z'
---

PRD Nowing: FR-36 Memory Migration + NFR-8 Recall-quality eval gate là 2 điều kiện TRƯỚC-SHIP. Migration 177-179 tạo bảng memory, 178 DROP memory_md/shared_memory_md. Cần backfill legacy memory trước khi apply 178. nowing_evals cần tồn tại cho NFR-8.
