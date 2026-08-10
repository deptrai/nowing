# Story 21.4: Outbound Prospecting Automation

Status: ready-for-dev

## Story

As a sales team,
I want to automate personalized outreach across channels,
So that I can scale outbound without sacrificing quality.

## Acceptance Criteria

- Given a lead list, when outreach is triggered, then personalized messages are generated using lead context + ICP + intent signals
- Given outreach sequences, when configured, then multi-channel sequences (email, LinkedIn, Zalo for VN) are supported
- Given a sequence step, when executed, then the system personalizes content, tracks delivery, and logs responses
- Given response detection, when a lead replies, then the sequence pauses and alerts the assigned rep

## Tasks / Subtasks

- [ ] Task 1: Sequence Builder (AC: 1, 2)
  - [ ] 1.1 Create `Sequence` model (id, workspace_id, name, trigger_type, status)
  - [ ] 1.2 Create `SequenceStep` model (id, sequence_id, step_order, channel, template, wait_duration, condition)
  - [ ] 1.3 Implement sequence builder UI in Data Panel
- [ ] Task 2: Multi-Channel Delivery (AC: 2)
  - [ ] 2.1 Email delivery (SMTP/SES)
  - [ ] 2.2 LinkedIn delivery (via API or automation)
  - [ ] 2.3 Zalo delivery (via Zalo OA API, Story 21.6)
- [ ] Task 3: Personalization Engine (AC: 1)
  - [ ] 3.1 AI-generated messages using lead context + ICP + signals
  - [ ] 3.2 Template variables (company name, role, recent signals)
  - [ ] 3.3 A/B testing support for message variants
- [ ] Task 4: Response Tracking (AC: 4)
  - [ ] 4.1 Email reply detection (webhook)
  - [ ] 4.2 LinkedIn reply detection
  - [ ] 4.3 Auto-pause sequence on reply
  - [ ] 4.4 Alert assigned rep via notification

## Dev Notes

- **AD-39:** Sequencer is multi-channel outreach engine
- **AD-33:** Reuse Automation scheduler for sequence timing
- **Source:** `app/automations/` for sequence engine pattern
- **Integration:** Uses enriched contact data from Story 21.3

### References

- [Source: epics.md §FR-66]
- [Source: epic21-architecture-update.md §AD-39]

## Dev Agent Record

### Agent Model Used

{{agent_model_name_version}}

### File List

Created: 2026-08-10
