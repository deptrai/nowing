import { z } from "zod";

// ---------------------------------------------------------------------------
// VietQR / Napas 24/7 dynamic top-up checkout (Story 37.7)
// All *_micros fields are integer micro-USD (1_000_000 == $1.00);
// 1 credit == 10_000 micros.
// ---------------------------------------------------------------------------

export const pricingTier = z.object({
	id: z.string(),
	name: z.string(),
	price_vnd: z.number(),
	credits: z.number(),
	credit_micros: z.number(),
	seats: z.number().nullable(),
	highlighted: z.boolean(),
});

export const pricingTiersResponse = z.object({
	tiers: z.array(pricingTier),
	vnd_per_usd: z.number(),
});

export const createTopupIntentRequest = z.object({
	workspace_id: z.number().int().min(1),
	tier_id: z.string().optional(),
	amount_vnd: z.number().int().min(1).optional(),
});

export const topupIntentStatusEnum = z.enum(["pending", "completed", "failed", "expired"]);

export const topupIntent = z.object({
	intent_id: z.uuid(),
	status: topupIntentStatusEnum,
	amount_vnd: z.number(),
	credit_micros: z.number(),
	credits: z.number(),
	transfer_memo: z.string(),
	bank_bin: z.string(),
	bank_name: z.string(),
	bank_account_number: z.string(),
	bank_account_name: z.string(),
	qr_url: z.string(),
	expires_at: z.string(),
	created_at: z.string().nullable(),
});

export type PricingTier = z.infer<typeof pricingTier>;
export type PricingTiersResponse = z.infer<typeof pricingTiersResponse>;
export type CreateTopupIntentRequest = z.infer<typeof createTopupIntentRequest>;
export type TopupIntent = z.infer<typeof topupIntent>;
export type TopupIntentStatus = z.infer<typeof topupIntentStatusEnum>;
