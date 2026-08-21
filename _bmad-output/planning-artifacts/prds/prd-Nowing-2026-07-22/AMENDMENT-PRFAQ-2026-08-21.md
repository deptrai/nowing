---
title: "Amendment — PRFAQ-Derived FRs 2026-08-21"
prd: "prd-Nowing-2026-07-22/prd.md"
amendment_date: 2026-08-21
status: ADOPTED
source: "_bmad-output/planning-artifacts/prfaq-Nowing.md"
---

# Phụ lục bổ sung yêu cầu từ PRFAQ — 2026-08-21

## Tóm tắt

`prd-Nowing-2026-07-22/prd.md` được cập nhật lần cuối ngày 2026-08-10. Sau đó, `prfaq-Nowing.md` (2026-08-21) đặt ra 5 câu hỏi/ý tưởng chính (Q1/Q4/Q5/Q6/Q7/IQ5/IQ6/IQ7/IQ9) dẫn đến 5 requirement mới: **FR-95..FR-99**, **AR-11..AR-15**, **NFR-2/NFR-3 (mở rộng)**, **RS-11..RS-13** và **UX-DR-PRFAQ-1..4**. Phụ lục này bổ sung chúng vào PRD như một amendment chính thức để `epics.md`, `sprint-status.yaml` và implementation artifacts có cùng nguồn chân lý.

## 1. Functional Requirements mới (FR-95..FR-99)

| FR | Tên | Epic / Story | Mô tả ngắn | Trạng thái |
|---|---|---|---|---|
| **FR-95** | Data Export & Portability | E28.1 | Export workspace memory/research threads/citations ra JSON/CSV trên OKF bundle (self-host/cloud). | `backlog` |
| **FR-96** | Encryption-at-Rest & Key Management | E28.2 | Tiered encryption: content + PII/metadata v1, embedding v2 (defer benchmark); BYOK/managed key; cloud-only. | `backlog` |
| **FR-97** | ToS / Legal Review & Retention Policy | E28.3 | Review ToS nguồn scrape, source risk tier, retention schedule, right-to-delete workflow trước cloud GA. | `backlog` |
| **FR-98** | Self-Host OSS Onboarding <10 phút | E28.4 | `docker compose up`, local LLM/embedding, README + install script, offline-first aha-moment. | `backlog` |
| **FR-99** | Recall Precision / Noise Gate | E3.18 | Chốt ngưỡng precision/noise trên `nowing_evals` trước khi scale; `nowing_recall` không trả hallucination. | `backlog` |

### 1.1 FR-95 — Data Export & Portability

**As a** cloud or self-host user,
**I want** to export my workspace memory, research threads and citations to a portable format,
**So that** I can back up, migrate, or leave without lock-in.

**Acceptance Criteria:**
- Given a workspace with memory, when `POST /workspaces/{id}/memories/export` is called, then a ZIP/OKF bundle is returned containing `memories.json`, `research_threads.json`, `citations.csv`, and `manifest.json`.
- Given an export request, when the workspace has >10k rows, then the export runs async and returns a download URL.
- Given a self-host instance, when export is run, then no network call to cloud is required.

### 1.2 FR-96 — Encryption-at-Rest & Key Management

**As a** cloud user,
**I want** my memory content, PII and metadata encrypted at rest with a key I control or one managed by Nowing,
**So that** a database breach does not expose plaintext research data.

**Acceptance Criteria:**
- Given a cloud workspace, when memory rows are written, then `content`, `metadata` PII fields, and `source_input` are encrypted using AES-256-GCM before persistence.
- Given a BYOK setup, when `ENCRYPTION_KEY_PROVIDER=byok` and a key is provided, then all new writes use the user-supplied key; rotation is supported via `re-encrypt` admin command.
- Given embedding vectors, when v1 is implemented, then embeddings remain in native float[] to preserve HNSW search; v2 encryption is gated behind `EMBEDDING_ENCRYPTION_ENABLED` and benchmarked before default.

### 1.3 FR-97 — ToS / Legal Review & Retention Policy

**As a** cloud operator,
**I want** a reviewed ToS, source risk tier, and retention policy before GA,
**So that** Nowing complies with GDPR/Vietnam Decree 356 and platform ToS (Reddit, YouTube, TikTok, Amazon).

**Acceptance Criteria:**
- Given a source (Reddit/YouTube/TikTok/Amazon), when the legal review runs, then a `source_risk_tier` is assigned and documented.
- Given a workspace, when the retention policy is set, then memory older than the retention period is either soft-deleted or archived per workspace policy.
- Given a user request, when `DELETE /memories/{id}` is called, then a right-to-delete workflow removes the row, versions, and provenance within the SLA.

### 1.4 FR-98 — Self-Host OSS Onboarding <10 phút

**As a** developer evaluating Nowing,
**I want** to self-host the full stack in under 10 minutes,
**So that** I can trust the product and experience the research-memory aha moment without sales friction.

**Acceptance Criteria:**
- Given a fresh Linux/macOS machine with Docker, when `docker compose up` runs, then all services (Postgres, Redis, backend, web) start with default local LLM/embedding.
- Given a user without an API key, when the stack is up, then they can run one research/scrape command and see durable memory created.
- Given the README, when a dev follows it, then they can connect an MCP client and run `nowing_recall` within 10 minutes.

### 1.5 FR-99 — Recall Precision / Noise Gate

**As a** user of `nowing_recall`,
**I want** the system to reject low-precision / noisy memory before returning it,
**So that** I do not act on hallucinated or stale facts.

**Acceptance Criteria:**
- Given `nowing_evals` run, when recall precision falls below the ratified threshold, then the gate fails and blocks promotion.
- Given a noisy memory, when `nowing_recall` is called, then it is filtered or down-ranked and a `noise_flag` is logged.
- Given a human review, when false positives are annotated, then the threshold is updated and versioned.

## 2. Architecture Requirements mới (AR-11..AR-15)

| AR | Tên | Epic | Mô tả |
|---|---|---|---|
| **AR-11** | Data Export / Portability | E28 | OKF bundle, async job, offline self-host. |
| **AR-12** | Encryption-at-Rest + Key Management | E28 | Tiered encryption, BYOK, AD-28.1. |
| **AR-13** | ToS / Legal / Retention | E28 | Source risk tier, retention, right-to-delete. |
| **AR-14** | Self-Host Onboarding | E28 | Docker compose, local LLM/embedding, install script. |
| **AR-15** | Recall Precision Gate | E3 | `nowing_evals` precision/noise ratification. |

## 3. Non-Functional Requirements mở rộng

| NFR | Mở rộng |
|---|---|
| **NFR-2** | Security & Auth — bổ sung encryption-at-rest, key rotation, BYOK scope; xem FR-96. |
| **NFR-3** | Observability — bổ sung audit log cho export, encryption key usage, retention deletion, right-to-delete. |

## 4. Requirement Signals mới (RS-11..RS-13)

- **RS-11:** Legal/ToS + retention policy trước cloud GA.
- **RS-12:** Encryption-at-rest + key management cho cloud.
- **RS-13:** Self-host onboarding <10 phút / aha recall.

## 5. UX Design Requirements mới (UX-DR-PRFAQ-1..4)

| UX-DR | Tên | Epic | Mô tả | Ưu tiên |
|---|---|---|---|---|
| **UX-DR-PRFAQ-1** | Memory Browser / Research Timeline | E3 (post-MVP) | UI duyệt memory theo thread, source type, confidence, time; click-to-source citation. | post-MVP |
| **UX-DR-PRFAQ-2** | Self-Host Onboarding Flow | E28 | Landing + README dẫn `docker compose`, local/remote LLM, MCP client ≤10 phút. | fast-follow |
| **UX-DR-PRFAQ-3** | Memory Correction / Version History | E3 (post-MVP) | UI flag/update fact, xem version history & affected relations. | fast-follow |
| **UX-DR-PRFAQ-4** | Cost Control / Auto-Extract Budget Dashboard | E8.14 | Dashboard chi phí extract/embedding/recall per turn; cấu hình ngân sách & toggle auto-extract. | fast-follow |

## 6. Quan hệ với PRD chính

- `prd-Nowing-2026-07-22/prd.md` vẫn là nguồn chân lý cho scope lõi.
- Phụ lục này **bổ sung** các yêu cầu mới từ `prfaq-Nowing.md` (2026-08-21) và đã được phản ánh trong `epics.md`, `sprint-status.yaml`.
- Epic 28 mới được tạo: **"Self-Host Trust, Data Portability & Cloud GA Legal Readiness"**.
- Story 8.14 mới được thêm vào Epic 8: **"Cost & Auto-Extract Budget Dashboard"**.
- Story 3.18 được định nghĩa lại trong Epic 3: **"Recall Precision / Noise Gate Ratification"**.
