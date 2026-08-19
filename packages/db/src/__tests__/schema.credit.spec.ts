/**
 * Story 34-D1 — Credit schema + pricing catalog (Pay-As-You-Go Foundation).
 *
 * Acceptance Test Scaffolds (RED-PHASE):
 *  - AC1: `credit_balances` table with user_id PK, balance (cent-credits), currency (default 'USD'), updated_at.
 *  - AC2: `credit_ledger` table with id (UUID), user_id, type, amount, currency, catalog_version, reference_id, trace_id, created_at.
 *  - AC3: `price_catalog` table with version, mode, cent_credits, created_at (composite PK version+mode).
 *  - AC5: Multi-currency-ready columns (`currency`, `catalog_version`).
 *  - AC6: `credit_ledger.reference_id` link to `usage_ledger.id`.
 *
 * RED PHASE: Tests assert table definitions and column contracts before implementation.
 */
import { describe, it, expect } from 'vitest';
import { getTableColumns } from 'drizzle-orm';
import * as schema from '../schema';

describe('Story 34-D1 — Credit Schema (AC1, AC2, AC3, AC5, AC6)', () => {
  describe('AC1 — credit_balances table definition', () => {
    it('[P0] should export credit_balances table from schema', () => {
      expect((schema as any).creditBalances).toBeDefined();
    });

    it('[P0] should have user_id as primary key column', () => {
      const cols = getTableColumns((schema as any).creditBalances);
      expect(cols.userId).toBeDefined();
      expect(cols.userId.primary).toBe(true);
      expect(cols.userId.notNull).toBe(true);
    });

    it('[P0] should have balance as integer cent-credits notNull with default 0', () => {
      const cols = getTableColumns((schema as any).creditBalances);
      expect(cols.balance).toBeDefined();
      expect(cols.balance.dataType).toBe('number');
      expect(cols.balance.columnType).toBe('PgInteger');
      expect(cols.balance.notNull).toBe(true);
    });

    it('[P0] should have currency column defaulting to USD', () => {
      const cols = getTableColumns((schema as any).creditBalances);
      expect(cols.currency).toBeDefined();
      expect(cols.currency.columnType).toBe('PgText');
      expect(cols.currency.notNull).toBe(true);
      expect(cols.currency.default).toBe('USD');
    });

    it('[P1] should have updated_at timestamp column', () => {
      const cols = getTableColumns((schema as any).creditBalances);
      expect(cols.updatedAt).toBeDefined();
      expect(cols.updatedAt.columnType).toBe('PgTimestamp');
      expect(cols.updatedAt.notNull).toBe(true);
    });
  });

  describe('AC2 — credit_ledger table definition', () => {
    it('[P0] should export credit_ledger table from schema', () => {
      expect((schema as any).creditLedger).toBeDefined();
    });

    it('[P0] should have id as UUID primary key', () => {
      const cols = getTableColumns((schema as any).creditLedger);
      expect(cols.id).toBeDefined();
      expect(cols.id.columnType).toBe('PgUUID');
      expect(cols.id.primary).toBe(true);
    });

    it('[P0] should have user_id column notNull', () => {
      const cols = getTableColumns((schema as any).creditLedger);
      expect(cols.userId).toBeDefined();
      expect(cols.userId.notNull).toBe(true);
    });

    it('[P0] should have type column for transaction categorization', () => {
      const cols = getTableColumns((schema as any).creditLedger);
      expect(cols.type).toBeDefined();
      expect(cols.type.notNull).toBe(true);
    });

    it('[P0] should have amount as signed integer cent-credits', () => {
      const cols = getTableColumns((schema as any).creditLedger);
      expect(cols.amount).toBeDefined();
      expect(cols.amount.columnType).toBe('PgInteger');
      expect(cols.amount.notNull).toBe(true);
    });

    it('[P0] should have currency column defaulting to USD (AC5 multi-currency)', () => {
      const cols = getTableColumns((schema as any).creditLedger);
      expect(cols.currency).toBeDefined();
      expect(cols.currency.columnType).toBe('PgText');
      expect(cols.currency.notNull).toBe(true);
      expect(cols.currency.default).toBe('USD');
    });

    it('[P0] should have catalog_version column notNull (AC5)', () => {
      const cols = getTableColumns((schema as any).creditLedger);
      expect(cols.catalogVersion).toBeDefined();
      expect(cols.catalogVersion.columnType).toBe('PgText');
      expect(cols.catalogVersion.notNull).toBe(true);
    });

    it('[P1] should have nullable reference_id and trace_id columns (AC6)', () => {
      const cols = getTableColumns((schema as any).creditLedger);
      expect(cols.referenceId).toBeDefined();
      expect(cols.referenceId.notNull).toBe(false);
      expect(cols.traceId).toBeDefined();
      expect(cols.traceId.notNull).toBe(false);
    });

    it('[P1] should have created_at timestamp column with default now', () => {
      const cols = getTableColumns((schema as any).creditLedger);
      expect(cols.createdAt).toBeDefined();
      expect(cols.createdAt.columnType).toBe('PgTimestamp');
      expect(cols.createdAt.notNull).toBe(true);
    });
  });

  describe('AC3 — price_catalog table definition', () => {
    it('[P0] should export price_catalog table from schema', () => {
      expect((schema as any).priceCatalog).toBeDefined();
    });

    it('[P0] should have version, mode, cent_credits, and created_at columns', () => {
      const cols = getTableColumns((schema as any).priceCatalog);
      expect(cols.version).toBeDefined();
      expect(cols.version.columnType).toBe('PgText');
      expect(cols.version.notNull).toBe(true);

      expect(cols.mode).toBeDefined();
      expect(cols.mode.columnType).toBe('PgText');
      expect(cols.mode.notNull).toBe(true);

      expect(cols.centCredits).toBeDefined();
      expect(cols.centCredits.columnType).toBe('PgInteger');
      expect(cols.centCredits.notNull).toBe(true);

      expect(cols.createdAt).toBeDefined();
      expect(cols.createdAt.columnType).toBe('PgTimestamp');
      expect(cols.createdAt.notNull).toBe(true);
    });
  });
});
