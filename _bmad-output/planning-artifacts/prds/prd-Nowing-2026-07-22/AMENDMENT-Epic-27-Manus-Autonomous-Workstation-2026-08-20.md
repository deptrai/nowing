# PRD Amendment — Epic 27 Manus-like Autonomous Workstation

**PRD:** `prd-Nowing-2026-07-22/prd.md`  
**Amendment date:** 2026-08-20  
**Author:** Devin / Manus-Nowing feature audit  
**Status:** Ratified

## 1. Change summary

Architecture spine (2026-08-20, approved) xác định `nowing` là **Autonomous Workstation sở hữu 25 phân hệ tính năng Manus.im**. Trong đó, **Epic 27** — Full-Stack Web App Builder, Instant Hosting & Creative Studio — là một cột mốc sản phẩm hạng nhất, không phải out-of-PRD backlog. Amendment này đưa hai FR của Epic 27 vào PRD canonical.

## 2. New Functional Requirements

### FR-93: Full-Stack Web App Builder & Instant Hosting

- **Where added:** `prd.md` §4.10.
- **Epic:** Epic 27 — Story 27.1
- **Architecture decisions:** `AD-113` (Full-Stack Web App Builder & Traefik Instant Hosting), `AD-114` (Design View Mark Tool).
- **Acceptance criteria:** generate Next.js + Tailwind from prompt, deploy to `*.apps.nowing.net`, support custom CNAME.

### FR-94: Design View Mark Tool & Presentation Studio

- **Where added:** `prd.md` §4.10.
- **Epic:** Epic 27 — Story 27.2
- **Architecture decisions:** `AD-114`, `AD-112` (Python data science sandbox for output), `AD-115` (mail/scheduled tasks for deliverables).
- **Acceptance criteria:** visual Mark Tool for AST mutation, PPTX/Marp export, speaker diarization for meeting minutes.

## 3. Out-of-PRD scope adjustment

- `epics.md` vẫn giữ FR-70–FR-92 là out-of-PRD implementation backlog (Telegram, lead-gen extensions, infrastructure).
- FR-93/FR-94 là **in-PRD**, coverage được thể hiện qua Epic 27 và `sprint-status.yaml`.

## 4. Status after amendment

- `prd-Nowing-2026-07-22/prd.md` bao gồm 72 FR (thêm FR-93, FR-94).
- `epics.md` được cập nhật để phản ánh FR-93/94 thuộc Epic 27.
- `sprint-status.yaml` nâng `epic-27`, `27-1`, `27-2` lên `ready-for-dev`.
- Implementation Readiness Closeout được bổ sung ghi chú: Epic 27 đã in-PRD, readiness `READY`.
