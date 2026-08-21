import { z } from "zod";
import type {
	AdminPayoutListResponse,
	PayoutApproveResponse,
	PayoutRejectRequest,
	PayoutRejectResponse,
	PayoutRiskResponse,
} from "@/contracts/types/admin-affiliates.types";
import { baseApiService } from "./base-api.service";

export const adminPayoutItemSchema = z.object({
	id: z.string(),
	partner_id: z.string(),
	partner_name: z.string().nullable().optional(),
	partner_email: z.string().nullable().optional(),
	partner_code: z.string().nullable().optional(),
	partner_tier: z.string().default("standard"),
	gross_amount_vnd: z.number(),
	pit_tax_deduction_vnd: z.number(),
	net_payout_amount_vnd: z.number(),
	bank_bin: z.string().nullable().optional(),
	bank_short_name: z.string().nullable().optional(),
	account_number: z.string().nullable().optional(),
	account_holder: z.string().nullable().optional(),
	name_match_status: z.enum(["100% Match", "Name Mismatch", "Unverified"]),
	risk_score: z.number(),
	risk_level: z.enum(["low", "mid", "high"]),
	risk_reasons: z.array(z.string()).default([]),
	status: z.enum(["pending", "processing", "completed", "rejected"]),
	tx_reference: z.string().nullable().optional(),
	created_at: z.string(),
	processed_at: z.string().nullable().optional(),
});

export const adminPayoutListResponseSchema = z.object({
	items: z.array(adminPayoutItemSchema),
	total: z.number(),
	limit: z.number(),
	offset: z.number(),
});

export const payoutRiskResponseSchema = z.object({
	payout_id: z.string(),
	risk_score: z.number(),
	risk_level: z.enum(["low", "mid", "high"]),
	reasons: z.array(z.string()),
	evaluated_at: z.string(),
});

export const payoutApproveResponseSchema = z.object({
	status: z.string(),
	payout_id: z.string(),
	tx_reference: z.string(),
	amount_micros: z.number(),
	net_amount_micros: z.number(),
});

export const payoutRejectResponseSchema = z.object({
	status: z.string(),
	payout_id: z.string(),
	rejection_reason: z.string(),
	rolled_back_balance_micros: z.number(),
});

class AdminAffiliatesApiService {
	private base = "/api/v1/admin/affiliates/payouts";

	listPayouts = async (params?: { status?: string; limit?: number; offset?: number }) => {
		const qs = new URLSearchParams();
		if (params?.status) qs.set("status", params.status);
		if (params?.limit) qs.set("limit", String(params.limit));
		if (params?.offset) qs.set("offset", String(params.offset));
		const query = qs.toString();
		return baseApiService.get<AdminPayoutListResponse>(
			`${this.base}${query ? `?${query}` : ""}`,
			adminPayoutListResponseSchema
		);
	};

	evaluateRisk = async (payoutId: string) => {
		return baseApiService.post<PayoutRiskResponse>(
			`${this.base}/${payoutId}/evaluate`,
			payoutRiskResponseSchema,
			{}
		);
	};

	approvePayout = async (payoutId: string) => {
		return baseApiService.post<PayoutApproveResponse>(
			`${this.base}/${payoutId}/approve`,
			payoutApproveResponseSchema,
			{}
		);
	};

	rejectPayout = async (payoutId: string, payload: PayoutRejectRequest) => {
		return baseApiService.post<PayoutRejectResponse>(
			`${this.base}/${payoutId}/reject`,
			payoutRejectResponseSchema,
			{ body: payload }
		);
	};
}

export const adminAffiliatesApiService = new AdminAffiliatesApiService();
export const AdminAffiliatesApi = adminAffiliatesApiService;
