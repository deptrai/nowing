/**
 * Story 34-D1 — V1UsageController ATDD Unit Tests (RED-PHASE).
 *
 * Covers:
 *  - AC4: `GET /v1/usage` returns `{ balance, usedCredits, remainingCredits, plan, queryUsage }`
 *  - Aggregation of `BillingService.getQueryUsage` + `CreditBalanceService.getUsage`
 *  - Patterns 1-5 Anti-Pattern checks.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { Test, TestingModule } from '@nestjs/testing';
import { V1UsageController } from './v1-usage.controller';
import { BillingService } from '../billing/billing.service';
import { CreditBalanceService } from '../billing/credit-balance.service';

describe('V1UsageController (Story 34-D1 AC4)', () => {
  let controller: V1UsageController;
  let mockBillingService: any;
  let mockCreditBalanceService: any;

  beforeEach(async () => {
    mockBillingService = {
      getQueryUsage: vi.fn().mockResolvedValue({
        used: 3,
        limit: 10,
        remaining: 7,
        plan: 'free',
      }),
    };

    mockCreditBalanceService = {
      getUsage: vi.fn().mockResolvedValue({
        balance: 500,
        usedCredits: 50,
        remainingCredits: 500,
      }),
    };

    const module: TestingModule = await Test.createTestingModule({
      controllers: [V1UsageController],
      providers: [
        { provide: BillingService, useValue: mockBillingService },
        { provide: CreditBalanceService, useValue: mockCreditBalanceService },
      ],
    }).compile();

    controller = module.get<V1UsageController>(V1UsageController);
  });

  describe('Pattern 1 — Mirror Test (Contract Shape)', () => {
    it('[P0] should return exactly { balance, usedCredits, remainingCredits, plan, queryUsage }', async () => {
      const res = await controller.getUsage({ id: 'user-123' });
      expect(res).toEqual({
        balance: 500,
        usedCredits: 50,
        remainingCredits: 500,
        plan: 'free',
        queryUsage: {
          used: 3,
          limit: 10,
          remaining: 7,
        },
      });
    });

    it('[P0] should call both BillingService and CreditBalanceService with user id', async () => {
      await controller.getUsage({ id: 'user-456' });
      expect(mockBillingService.getQueryUsage).toHaveBeenCalledWith('user-456');
      expect(mockCreditBalanceService.getUsage).toHaveBeenCalledWith('user-456');
    });
  });

  describe('Pattern 2 — Over-Mocking & Error Handling', () => {
    it('[P1] should propagate error if CreditBalanceService fails', async () => {
      mockCreditBalanceService.getUsage.mockRejectedValue(new Error('Credit DB unreachable'));
      await expect(controller.getUsage({ id: 'user-123' })).rejects.toThrow('Credit DB unreachable');
    });

    it('[P1] should propagate error if BillingService fails', async () => {
      mockBillingService.getQueryUsage.mockRejectedValue(new Error('Billing DB unreachable'));
      await expect(controller.getUsage({ id: 'user-123' })).rejects.toThrow('Billing DB unreachable');
    });
  });

  describe('Pattern 4 — Arithmetic Invariants', () => {
    it('[P0] should ensure remainingCredits strictly equals balance', async () => {
      mockCreditBalanceService.getUsage.mockResolvedValue({
        balance: 1250,
        usedCredits: 350,
        remainingCredits: 1250,
      });

      const res = await controller.getUsage({ id: 'user-123' });
      expect(res.remainingCredits).toBe(res.balance);
    });
  });
});
