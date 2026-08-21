# Epic 24 Context: Enterprise Lead Conversion, Automated Multi-Channel Outreach & Team CRM Ecosystem

## Goal

Xây dựng hệ thống CRM pipeline đa ghế cho sales/agency, tự động gán lead bằng Round-Robin, theo dõi timeline tương tác, và dùng chung ví credit workspace với hạn mức chi tiêu cho từng thành viên. Epic cũng bao gồm multi-channel outreach (Email/Zalo/Telegram), lead enrichment (MST/phone), Chrome clipper, playbook marketplace, và AI auto-reply.

## Stories

- Story 24.1: Multi-Channel Drip Outreach Campaign Engine (done)
- Story 24.2: Waterfall Phone & B2B Tax Code (MST) Corporate Verification Engine (ready-for-dev)
- Story 24.3: Multi-Seat Team CRM Pipeline & Shared Workspace Credit Pooling (in-progress)
- Story 24.4: Nowing Lead Clipper — Chrome Extension (ready-for-dev)
- Story 24.5: Vertical Playbook Marketplace & Community Workflow Templates (ready-for-dev)
- Story 24.6: Two-Way AI Outreach Auto-Reply Agent (ready-for-dev)
- Story 24.7: Multi-Channel Drip Outreach Campaign Engine (Zalo ZNS + Telegram + Email Cadence) (backlog)

## Requirements & Constraints

- Team credit pooling phải atomic với `SELECT ... FOR UPDATE` trên `Workspace.credit_micros_balance`.
- Per-seat spend cap kiểm tra qua `workspace_memberships.monthly_spend_cap_micros` bằng atomic SQL update.
- CRM pipeline dùng Composite PK `(id, workspace_id)`; RLS fail-closed; `FORCE ROW LEVEL SECURITY`.
- Kanban board đồng bộ real-time qua Zero-cache; drag-and-drop có OCC version trả 409 khi conflict.
- Lead assignment Round-Robin phân bố đều cho active member `is_accepting_leads=True` và `current_leads < capacity`.
- Quiet hours 08:00–21:30 Asia/Ho_Chi_Minh; DNC fail-closed; ZNS template phải approved.

## Technical Decisions

- `LeadAssignmentService` dùng Redis cursor cho Round-Robin fairness multi-worker.
- `WorkspaceCreditService` là gate cho per-seat spend cap, gọi trước `wallet_credit.apply_debit`.
- Tables `lead_pipeline_stages`, `lead_assignments`, `lead_activity_logs` publish vào `zero_publication`.
- Frontend Kanban dùng `@dnd-kit/core` + Zero query subscriptions.

## UX & Interaction Patterns

- `/dashboard/[workspace_id]/leads/pipeline` — Kanban board 5 cột.
- Flyout Detail Drawer hiển thị chronological interaction timeline.
- Workspace Settings — `MemberSpendCapDialog` để cấu hình per-seat cap/capacity.

## Cross-Story Dependencies

- 24.2/24.4/25.2 cung cấp `tax_id`, `company_status`, `GlobalDncRecord`, `AuditEvent`, `CreditTransaction`.
- 25.1 cung cấp `ImpersonationGuardMiddleware` và admin CORS regex.
- 25.3..25.6 liên quan đến workspace credit/audit.
