import { z } from "zod";

export const createTokenTopupRequest = z.object({
	amount_usd: z.number().positive(),
	search_space_id: z.number().int().min(1),
});

export const createTokenTopupResponse = z.object({
	checkout_url: z.string(),
	admin_approval_mode: z.boolean().default(false),
});

export const billingPortalResponse = z.object({
	url: z.string(),
});

export const stripeStatusResponse = z.object({
	stripe_enabled: z.boolean(),
});

export type CreateTokenTopupRequest = z.infer<typeof createTokenTopupRequest>;
export type CreateTokenTopupResponse = z.infer<typeof createTokenTopupResponse>;
export type BillingPortalResponse = z.infer<typeof billingPortalResponse>;
export type StripeStatusResponse = z.infer<typeof stripeStatusResponse>;
