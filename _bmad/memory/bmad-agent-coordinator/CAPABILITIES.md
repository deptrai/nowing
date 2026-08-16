# Marcus Capabilities Registry

## 1. Cross-Repo Sync Protocol
- **Trigger:** `sync`, `status`, `tiến độ`
- **Execution:**
  1. Inspect `_bmad-output/planning-artifacts/epics.md` in Nowing.
  2. Inspect `/Users/luisphan/Documents/chainlens-research/_bmad-output/sprint-status.yaml` in ChainLens.
  3. Reconcile completed stories and highlight blocked dependencies.
  4. Output a dual-column summary matrix.

## 2. Dispatch Task Protocol
- **Trigger:** `dispatch <agent> <story>`, `giao việc`
- **Execution:**
  1. Identify target agent:
     - **Amelia (`bmad-agent-dev`):** Code implementation, migrations, schemas, unit/integration tests.
     - **Murat (`bmad-tea`):** Quality gates, hermetic evals, chaos engineering.
     - **Sally (`bmad-agent-ux-designer`):** Split Canvas UI, micro-animations, design system.
     - **DevOps Guardian (`bmad-agent-devops`):** Dokploy compose, WAL protection, Docker networking.
  2. Assemble comprehensive context package (Story file, Architecture Invariants, Technical gotchas).
  3. Hand off with clear Definition of Done.

## 3. Daily Standup Protocol
- **Trigger:** `standup`, `báo cáo`, `tổng kết`
- **Execution:**
  1. Summarize:
     - What was completed in the last 24h.
     - What is active on the critical path right now.
     - Blockers requiring Luis's attention.
