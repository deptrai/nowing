export interface VietQrBankItem {
	bin: string;
	name: string;
	short_name: string;
	code: string;
}

export interface PartnerProfileResponse {
	id: string;
	user_id: string;
	referral_code: string;
	referral_url: string;
	partner_type: string;
	status: string;
	commission_rate: number;
	balance_micros: number;
	balance_usd: number;
	balance_vnd: number;
	hold_balance_micros?: number;
	hold_balance_usd?: number;
	hold_balance_vnd?: number;
	total_earned_micros: number;
	total_earned_usd: number;
	total_earned_vnd: number;
	total_paid_micros: number;
	payout_method: string;
	payout_details: Record<string, unknown>;
	total_clicks: number;
	total_referrals: number;
	active_paying_referrals: number;
	created_at: string;
	updated_at: string;
}

export interface PartnerApplyRequest {
	referral_code: string;
	partner_type?: string;
	payout_method?: string;
	payout_details?: Record<string, unknown>;
}

export interface PartnerPayoutSettingsUpdate {
	payout_method: string;
	payout_details: Record<string, unknown>;
}

export interface PartnerReferralItem {
	id: string;
	referred_user_id: string;
	masked_email: string;
	attribution_source: string;
	landing_page: string;
	total_spent_micros: number;
	total_commission_micros: number;
	created_at: string;
}

export interface PartnerReferralsListResponse {
	referrals: PartnerReferralItem[];
	total_count: number;
}

export interface PartnerCommissionItem {
	id: string;
	referral_id: string;
	credit_purchase_id: string;
	source_amount_micros: number;
	source_amount_usd: number;
	commission_micros: number;
	commission_usd: number;
	commission_vnd: number;
	commission_rate: number;
	currency: string;
	status: string;
	created_at: string;
}

export interface PartnerCommissionsListResponse {
	commissions: PartnerCommissionItem[];
	total_count: number;
	total_commission_micros: number;
}

export interface PartnerPayoutRequest {
	amount_micros: number;
	payout_method: string;
	payout_details?: Record<string, unknown>;
}

export interface PartnerPayoutItem {
	id: string;
	amount_micros: number;
	amount_usd: number;
	amount_vnd: number;
	tax_deducted_micros?: number;
	tax_deducted_vnd?: number;
	net_amount_micros?: number;
	net_amount_vnd?: number;
	tax_code?: string | null;
	payout_method: string;
	payout_details: Record<string, unknown>;
	status: string;
	tx_reference?: string | null;
	napas_ref?: string | null;
	hmac_audit_hash?: string | null;
	requested_at: string;
	processed_at?: string | null;
	created_at: string;
}

export interface PartnerPayoutsListResponse {
	payouts: PartnerPayoutItem[];
	total_count: number;
}
