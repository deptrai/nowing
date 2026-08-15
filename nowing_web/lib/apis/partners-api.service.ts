import { z } from "zod";
import type {
	PartnerApplyRequest,
	PartnerCommissionsListResponse,
	PartnerPayoutItem,
	PartnerPayoutRequest,
	PartnerPayoutSettingsUpdate,
	PartnerPayoutsListResponse,
	PartnerProfileResponse,
	PartnerReferralsListResponse,
	VietQrBankItem,
} from "@/contracts/types/partners.types";
import { baseApiService } from "./base-api.service";

const vietQrBankItemSchema = z.object({
	bin: z.string(),
	name: z.string(),
	short_name: z.string(),
	code: z.string(),
});

const vietQrBankListSchema = z.array(vietQrBankItemSchema);

const partnerProfileResponseSchema = z.object({
	id: z.string(),
	user_id: z.string(),
	referral_code: z.string(),
	referral_url: z.string(),
	partner_type: z.string(),
	status: z.string(),
	commission_rate: z.number(),
	balance_micros: z.number(),
	balance_usd: z.number(),
	balance_vnd: z.number(),
	total_earned_micros: z.number(),
	total_earned_usd: z.number(),
	total_earned_vnd: z.number(),
	total_paid_micros: z.number(),
	payout_method: z.string(),
	payout_details: z.record(z.string(), z.any()),
	total_clicks: z.number(),
	total_referrals: z.number(),
	active_paying_referrals: z.number(),
	created_at: z.string(),
	updated_at: z.string(),
});

const partnerReferralItemSchema = z.object({
	id: z.string(),
	referred_user_id: z.string(),
	masked_email: z.string(),
	attribution_source: z.string(),
	landing_page: z.string(),
	total_spent_micros: z.number(),
	total_commission_micros: z.number(),
	created_at: z.string(),
});

const partnerReferralsListSchema = z.object({
	referrals: z.array(partnerReferralItemSchema),
	total_count: z.number(),
});

const partnerCommissionItemSchema = z.object({
	id: z.string(),
	referral_id: z.string(),
	credit_purchase_id: z.string(),
	source_amount_micros: z.number(),
	source_amount_usd: z.number(),
	commission_micros: z.number(),
	commission_usd: z.number(),
	commission_vnd: z.number(),
	commission_rate: z.number(),
	currency: z.string(),
	status: z.string(),
	created_at: z.string(),
});

const partnerCommissionsListSchema = z.object({
	commissions: z.array(partnerCommissionItemSchema),
	total_count: z.number(),
	total_commission_micros: z.number(),
});

const partnerPayoutItemSchema = z.object({
	id: z.string(),
	amount_micros: z.number(),
	amount_usd: z.number(),
	amount_vnd: z.number(),
	payout_method: z.string(),
	payout_details: z.record(z.string(), z.any()),
	status: z.string(),
	tx_reference: z.string().nullable().optional(),
	requested_at: z.string(),
	processed_at: z.string().nullable().optional(),
	created_at: z.string(),
});

const partnerPayoutsListSchema = z.object({
	payouts: z.array(partnerPayoutItemSchema),
	total_count: z.number(),
});

class PartnersApiService {
	async getSupportedBanks(): Promise<VietQrBankItem[]> {
		return baseApiService.get("/partners/supported-banks", vietQrBankListSchema);
	}

	async apply(data: PartnerApplyRequest): Promise<PartnerProfileResponse> {
		return baseApiService.post("/partners/apply", partnerProfileResponseSchema, { body: data });
	}

	async getProfile(): Promise<PartnerProfileResponse> {
		return baseApiService.get("/partners/me", partnerProfileResponseSchema);
	}

	async updatePayoutSettings(data: PartnerPayoutSettingsUpdate): Promise<PartnerProfileResponse> {
		return baseApiService.put("/partners/payout-settings", partnerProfileResponseSchema, {
			body: data,
		});
	}

	async getReferrals(limit = 50, offset = 0): Promise<PartnerReferralsListResponse> {
		return baseApiService.get(
			`/partners/referrals?limit=${limit}&offset=${offset}`,
			partnerReferralsListSchema
		);
	}

	async getCommissions(limit = 50, offset = 0): Promise<PartnerCommissionsListResponse> {
		return baseApiService.get(
			`/partners/commissions?limit=${limit}&offset=${offset}`,
			partnerCommissionsListSchema
		);
	}

	async requestPayout(data: PartnerPayoutRequest): Promise<PartnerPayoutItem> {
		return baseApiService.post("/partners/payouts/request", partnerPayoutItemSchema, {
			body: data,
		});
	}

	async getPayouts(limit = 50, offset = 0): Promise<PartnerPayoutsListResponse> {
		return baseApiService.get(
			`/partners/payouts?limit=${limit}&offset=${offset}`,
			partnerPayoutsListSchema
		);
	}
}

export const partnersApiService = new PartnersApiService();
