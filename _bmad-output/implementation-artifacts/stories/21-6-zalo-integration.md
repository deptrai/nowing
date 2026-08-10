# Story 21.6: Zalo Integration (Vietnam Market)

Status: ready-for-dev

## Story

As a Vietnamese salesperson,
I want to communicate with leads via Zalo,
Because 81% of Vietnamese professionals use Zalo as their primary messaging platform.

## Acceptance Criteria

- Given a Zalo OA connection, when configured, then outreach sequences can include Zalo messages
- Given a lead with Zalo contact, when outreach is triggered, then personalized Zalo messages are sent
- Given a Zalo reply, when received, then it's logged in the lead's activity timeline
- Given Zalo messaging, when sent, then it complies with Zalo business messaging policies and Decree 356

## Tasks / Subtasks

- [ ] Task 1: Zalo OA Connection
  - [ ] 1.1 Create `ZaloConnection` model (id, workspace_id, oa_id, access_token_encrypted)
  - [ ] 1.2 Zalo OA OAuth flow setup
  - [ ] 1.3 Token refresh mechanism
- [ ] Task 2: Zalo Messaging
  - [ ] 2.1 Send personalized Zalo messages via OA API
  - [ ] 2.2 Receive replies via webhook
  - [ ] 2.3 Log messages in lead activity timeline
- [ ] Task 3: Compliance
  - [ ] 3.1 Decree 356 consent management
  - [ ] 3.2 Unsubscribe/opt-out handling
  - [ ] 3.3 Rate limiting per Zalo OA policies

## Dev Notes

- **AD-41:** Zalo integration for Vietnam market
- **Prerequisite:** Zalo OA account setup (team action)
- **Source:** `app/gateway/zalo/` (reuse existing gateway pattern)

### References

- [Source: epics.md §FR-68]
- [Source: epic21-architecture-update.md §AD-41]

## Dev Agent Record

### Agent Model Used

{{agent_model_name_version}}

### File List

Created: 2026-08-10
