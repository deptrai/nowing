/**
 * Story 34-D1 — PricingCatalogService ATDD Unit Tests (RED-PHASE).
 *
 * Covers:
 *  - AC3: Versioned pricing catalog lookup (USD seed: speed=25, ask=70, reason=90, research=150, deep=240 cent-credits)
 *  - Pattern 1 (Mirror): Exact prices for seeded modes in version credit-v1-2026-08-19.
 *  - Pattern 2 (Over-mocking): Unknown mode handling, DB fallback.
 *  - Pattern 3 (Edge cases): Case normalization, version resolution.
 *  - Pattern 4 (Arithmetic): 1 cr = 100 cent-credits conversion.
 *  - Pattern 5 (Error message): Throws NotFoundException on invalid mode.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { NotFoundException } from '@nestjs/common';
import { PricingCatalogService } from './pricing-catalog.service';

describe('PricingCatalogService (Story 34-D1 AC3)', () => {
  let service: PricingCatalogService;
  let mockDb: any;

  const SEED_CATALOG_ROWS = [
    { version: 'credit-v1-2026-08-19', mode: 'speed', centCredits: 25, createdAt: new Date() },
    { version: 'credit-v1-2026-08-19', mode: 'ask', centCredits: 70, createdAt: new Date() },
    { version: 'credit-v1-2026-08-19', mode: 'reason', centCredits: 90, createdAt: new Date() },
    { version: 'credit-v1-2026-08-19', mode: 'research', centCredits: 150, createdAt: new Date() },
    { version: 'credit-v1-2026-08-19', mode: 'deep', centCredits: 240, createdAt: new Date() },
  ];

  beforeEach(() => {
    mockDb = {
      select: vi.fn().mockReturnThis(),
      from: vi.fn().mockReturnThis(),
      where: vi.fn().mockReturnThis(),
      orderBy: vi.fn().mockResolvedValue(SEED_CATALOG_ROWS),
    };

    service = new PricingCatalogService(mockDb);
  });

  describe('Pattern 1 — Mirror Test (Catalog Pricing Contract)', () => {
    it('[P0] should return exact cent-credits for speed mode (25 cent-credits)', async () => {
      const price = await service.getCatalog('speed');
      expect(price).toBe(25);
    });

    it('[P0] should return exact cent-credits for ask mode (70 cent-credits)', async () => {
      const price = await service.getCatalog('ask');
      expect(price).toBe(70);
    });

    it('[P0] should return exact cent-credits for reason mode (90 cent-credits)', async () => {
      const price = await service.getCatalog('reason');
      expect(price).toBe(90);
    });

    it('[P0] should return exact cent-credits for research mode (150 cent-credits)', async () => {
      const price = await service.getCatalog('research');
      expect(price).toBe(150);
    });

    it('[P0] should return exact cent-credits for deep mode (240 cent-credits)', async () => {
      const price = await service.getCatalog('deep');
      expect(price).toBe(240);
    });

    it('[P0] should return active catalog version as credit-v1-2026-08-19', async () => {
      const version = await service.getActiveVersion();
      expect(version).toBe('credit-v1-2026-08-19');
    });
  });

  describe('Pattern 2 — Over-Mocking & Fallbacks', () => {
    it('[P1] should fallback to hardcoded fallback catalog when DB query fails', async () => {
      mockDb.orderBy.mockRejectedValue(new Error('Connection lost'));
      const price = await service.getCatalog('speed');
      expect(price).toBe(25);
    });
  });

  describe('Pattern 3 — Edge Cases & Normalization', () => {
    it('[P1] should normalize uppercase and mixed-case mode strings', async () => {
      const price = await service.getCatalog('SPEED' as any);
      expect(price).toBe(25);
    });

    it('[P1] should alias deep-research and deep-reasoning to deep and reason', async () => {
      const deepPrice = await service.getCatalog('deep-research' as any);
      expect(deepPrice).toBe(240);

      const reasonPrice = await service.getCatalog('deep-reasoning' as any);
      expect(reasonPrice).toBe(90);
    });
  });

  describe('Pattern 4 — Arithmetic & Conversion', () => {
    it('[P0] should assert 1 credit equals exactly 100 cent-credits', async () => {
      expect(service.convertCentCreditsToCredits(25)).toBe(0.25);
      expect(service.convertCentCreditsToCredits(70)).toBe(0.7);
      expect(service.convertCentCreditsToCredits(90)).toBe(0.9);
      expect(service.convertCentCreditsToCredits(150)).toBe(1.5);
      expect(service.convertCentCreditsToCredits(240)).toBe(2.4);
    });

    it('[P0] should assert credits to cent-credits conversion integer precision', async () => {
      expect(service.convertCreditsToCentCredits(1.5)).toBe(150);
      expect(service.convertCreditsToCentCredits(0.25)).toBe(25);
    });
  });

  describe('Pattern 5 — Error Messages', () => {
    it('[P0] should throw NotFoundException when mode is not recognized', async () => {
      await expect(service.getCatalog('invalid-mode' as any)).rejects.toThrow(NotFoundException);
      await expect(service.getCatalog('invalid-mode' as any)).rejects.toThrow(/invalid-mode/);
    });
  });
});
