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

export const giftPlanId = z.union([z.literal("pro_monthly"), z.literal("max_monthly")]);
export type GiftPlanId = z.infer<typeof giftPlanId>;

export const giftCheckoutRequest = z.object({
	plan_id: giftPlanId,
	duration_months: z.union([z.literal(1), z.literal(3), z.literal(6), z.literal(12)]),
});

export const giftCheckoutResponse = z.object({
	checkout_url: z.string(),
	admin_approval_mode: z.boolean().default(false),
});

export const redeemGiftRequest = z.object({
	code: z.string().min(1),
});

export const redeemGiftResponse = z.object({
	new_expiry: z.string(),
	plan_id: z.string(),
});

export const requestGiftRequest = z.object({
	plan_id: giftPlanId,
	duration_months: z.union([z.literal(1), z.literal(3), z.literal(6), z.literal(12)]),
});

export const requestGiftResponse = z.object({
	request_id: z.string(),
	message: z.string(),
});

// Admin gift request schemas
export const giftRequestItem = z.object({
	id: z.string(),
	user_id: z.string(),
	user_email: z.string(),
	plan_id: z.string(),
	duration_months: z.number(),
	status: z.string(),
	gift_code_id: z.string().nullable(),
	gift_code: z.string().nullable(),
	created_at: z.string(),
	updated_at: z.string().nullable(),
});

export const giftRequestListResponse = z.object({
	items: z.array(giftRequestItem),
	count: z.number(),
});

export const giftRequestApproveResponse = z.object({
	request_id: z.string(),
	gift_code_id: z.string(),
	gift_code: z.string(),
	plan_id: z.string(),
	duration_months: z.number(),
});

export type GiftRequestItem = z.infer<typeof giftRequestItem>;
export type GiftRequestListResponse = z.infer<typeof giftRequestListResponse>;
export type GiftRequestApproveResponse = z.infer<typeof giftRequestApproveResponse>;

export type CreateTokenTopupRequest = z.infer<typeof createTokenTopupRequest>;
export type CreateTokenTopupResponse = z.infer<typeof createTokenTopupResponse>;
export type BillingPortalResponse = z.infer<typeof billingPortalResponse>;
export type StripeStatusResponse = z.infer<typeof stripeStatusResponse>;
export type GiftCheckoutRequest = z.infer<typeof giftCheckoutRequest>;
export type GiftCheckoutResponse = z.infer<typeof giftCheckoutResponse>;
export type RedeemGiftRequest = z.infer<typeof redeemGiftRequest>;
export type RedeemGiftResponse = z.infer<typeof redeemGiftResponse>;
export type RequestGiftRequest = z.infer<typeof requestGiftRequest>;
export type RequestGiftResponse = z.infer<typeof requestGiftResponse>;
