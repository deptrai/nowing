# ATDD Checklist: Story 25.1 Multi-Tenant User & Workspace Hub + Scoped Impersonation

## Background Context
- **Epic**: 25 (Superadmin & Platform Operations Control Plane)
- **Story**: 25.1
- **Invariants**: INV-25.1, INV-25.2, INV-25.8

## Red-Phase Test Scaffolds

### Backend Integration Tests (`nowing_backend/tests/integration/routes/test_admin_impersonation.py`)
- [ ] `test_admin_user_directory_ac1`: Superadmin user directory list, search, and pagination.
- [ ] `test_scoped_impersonation_jwt_generation_ac2`: Scoped Impersonation JWT generation (TTL 15m, claims `impersonated_by`, `target_user`, `is_impersonation=true`).
- [ ] `test_privilege_stripping_and_fail_closed_guards_ac3`: Privilege Stripping & Fail-Closed Guards.
- [ ] `test_dual_principal_audit_logging_ac4`: Dual-principal audit logging in `audit_events`.
- [ ] `test_non_superuser_and_pat_rejection_ac5`: Non-superuser and PAT token fail-closed rejection (HTTP 403).

### Frontend E2E Tests (`nowing_web/tests/admin/impersonation.spec.ts`)
- [ ] `AC-1: Render high-density user table`: Verify high-density user table rendering.
- [ ] `AC-2 & AC-4: Render sticky amber hazard banner during impersonation`: Verify Impersonate action click and sticky 40px amber banner rendering.
- [ ] `AC-4: 1-Click Exit Impersonation using button or Esc key`: Verify exit behavior.

## Sign-off
- **Architect/QA**: Murat
- **Status**: Scaffolded (Red Phase)
