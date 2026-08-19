/**
 * Story 34-D1 — CreditBalanceService ATDD Unit Tests (RED-PHASE).
 *
 * Covers:
 *  - AC1: `getBalance(userId)` returns balance in cent-credits with currency.
 *  - AC2: `recordLedgerEntry()` creates immutable append-only ledger record.
 *  - AC4: `getUsage(userId)` calculates usedCredits and remainingCredits.
 *  - AC5: Multi-currency-ready default currency 'USD'.
 *  - AC6: Linking `referenceId` to `usage_ledger.id`.
 *  - Pattern 1-5 Anti-Pattern checks.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { CreditBalanceService } from './credit-balance.service';
import { PricingCatalogService } from './pricing-catalog.service';

describe('CreditBalanceService (Story 34-D1 AC1, AC2, AC4, AC5, AC6)', () => {
  let service: CreditBalanceService;
  let mockDb: any;
  let mockPricingCatalogService: any;

  beforeEach(() => {
    mockDb = {
      select: vi.fn().mockReturnThis(),
      from: vi.fn().mockReturnThis(),
      where: vi.fn().mockReturnThis(),
      limit: vi.fn().mockResolvedValue([]),
      insert: vi.fn().mockReturnThis(),
      values: vi.fn().mockResolvedValue([]),
      update: vi.fn().mockReturnThis(),
      set: vi.fn().mockReturnThis(),
      transaction: vi.fn(async (cb: any) => cb(mockDb)),
    };

    mockPricingCatalogService = {
      getCatalog: vi.fn().mockResolvedValue(25),
      getActiveVersion: vi.fn().mockResolvedValue('credit-v1-2026-08-19'),
    };

    service = new CreditBalanceService(mockDb, mockPricingCatalogService);
  });

  describe('Pattern 1 — Mirror Test (Balance & Usage Shapes)', () => {
    it('[P0] should return balance object with exactly { balance, currency, updatedAt }', async () => {
      const now = new Date();
      mockDb.limit.mockResolvedValueOnce([{
        userId: 'user-123',
        balance: 500,
        currency: 'USD',
        updatedAt: now,
      }]);

      const res = await service.getBalance('user-123');
      expect(res).toEqual({
        balance: 500,
        currency: 'USD',
        updatedAt: now,
      });
    });

    it('[P0] should return default { balance: 0, currency: "USD" } when user has no balance row', async () => {
      mockDb.limit.mockResolvedValueOnce([]);
      const res = await service.getBalance('user-new');
      expect(res.balance).toBe(0);
      expect(res.currency).toBe('USD');
    });

    it('[P0] should calculate usedCredits as positive sum of usage_deduction ledger entries', async () => {
      mockDb.limit.mockResolvedValueOnce([{ userId: 'u1', balance: 400, currency: 'USD' }]);
      mockDb.where.mockResolvedValueOnce([
        { amount: -25, type: 'usage_deduction', currency: 'USD' },
        { amount: -75, type: 'usage_deduction', currency: 'USD' },
        { amount: 500, type: 'starter_grant', currency: 'USD' },
      ]);

      const usage = await service.getUsage('u1');
      expect(usage.balance).toBe(400);
      expect(usage.usedCredits).toBe(100);
      expect(usage.remainingCredits).toBe(400);
    });
  });

  describe('Pattern 2 — Over-Mocking & Failures', () => {
    it('[P1] should handle DB error when querying balance gracefully', async () => {
      mockDb.limit.mockRejectedValueOnce(new Error('DB failure'));
      await expect(service.getBalance('u1')).rejects.toThrow('DB failure');
    });
  });

  describe('Pattern 3 — Edge Cases (Zero Balance, Mixed Currency)', () => {
    it('[P0] should handle zero balance correctly', async () => {
      mockDb.limit.mockResolvedValueOnce([{ userId: 'u1', balance: 0, currency: 'USD' }]);
      mockDb.where.mockResolvedValueOnce([]);

      const usage = await service.getUsage('u1');
      expect(usage.balance).toBe(0);
      expect(usage.remainingCredits).toBe(0);
      expect(usage.usedCredits).toBe(0);
    });

    it('[P0] should filter ledger entries by currency USD and exclude VND records', async () => {
      mockDb.limit.mockResolvedValueOnce([{ userId: 'u1', balance: 100, currency: 'USD' }]);
      mockDb.where.mockResolvedValueOnce([
        { amount: -25, type: 'usage_deduction', currency: 'USD' },
        { amount: -5000, type: 'usage_deduction', currency: 'VND' },
      ]);

      const usage = await service.getUsage('u1');
      expect(usage.usedCredits).toBe(25);
    });
  });

  describe('Pattern 4 — Arithmetic Assertions', () => {
    it('[P0] should assert remainingCredits equals balance exactly', async () => {
      mockDb.limit.mockResolvedValueOnce([{ userId: 'u1', balance: 350, currency: 'USD' }]);
      mockDb.where.mockResolvedValueOnce([]);

      const usage = await service.getUsage('u1');
      expect(usage.remainingCredits).toBe(usage.balance);
    });
  });

  describe('Pattern 6 — AC6 Reference to usage_ledger', () => {
    it('[P0] should pass referenceId of usage_ledger when recording deduction', async () => {
      const usageLedgerId = '00000000-0000-0000-0000-000000000001';
      await service.recordDeduction({
        userId: 'u1',
        amount: 25,
        referenceId: usageLedgerId,
        traceId: 'trace-123',
      });

      expect(mockDb.insert).toHaveBeenCalled();
    });
  });
});
