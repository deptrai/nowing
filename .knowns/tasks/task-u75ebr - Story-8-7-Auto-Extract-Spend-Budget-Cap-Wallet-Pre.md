---
id: u75ebr
title: 'Story 8.7: Auto-Extract Spend/Budget Cap, Wallet Pre-Check & Rate-Limit (New Gap)'
status: done
priority: high
labels:
  - bmad
  - bmad-key-8-7-auto-extract-spend-budget-cap
  - epic-8
createdAt: '2026-07-28T15:10:18.987Z'
updatedAt: '2026-07-28T15:20:16.116Z'
completedAt: '2026-07-28T15:10:18.987Z'
timeSpent: 0
parent: kaffa6
spec: stories/story-8-7-auto-extract-spend-budget-cap-wallet-pre-check-rate-limit-new-gap
---
# Story 8.7: Auto-Extract Spend/Budget Cap, Wallet Pre-Check & Rate-Limit (New Gap)

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
code review 2026-07-26 (3-layer adversarial): 2 decisions + 26 patches applied, 4 deferred, 2 dismissed. D1: wallet pre-check đọc số dư mà extraction KHÔNG BAO GIỜ trừ — confirmed nhưng là BY DESIGN (AD-8 loại memory khỏi debit surface; memory_create là observability record của 8.9; free-tier global cost là platform cost không đo có chủ ý; G4 chỉ yêu cầu cap+pre-check TỒN TẠI, containment là kill-switch) ⇒ sửa tài liệu chứ không sửa billing: boxed note trên AC-1, restate R1, sửa tiền đề Dev Note
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
<!-- AC:END -->

