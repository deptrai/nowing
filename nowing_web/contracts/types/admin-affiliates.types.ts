export type PayoutStatus = "pending" | "processing" | "completed" | "rejected";
export type NameMatchStatus = "100% Match" | "Name Mismatch" | "Unverified";
export type RiskLevel = "low" | "mid" | "high";
export type PayoutRejectionReason = "name_mismatch" | "suspected_fraud_ring" | "invalid_account";

export interface AdminPayoutItem {
	id: string;
	partner_id: string;
	partner_name?: string | null;
	partner_email?: string | null;
	partner_code?: string | null;
	partner_tier: string;
	gross_amount_vnd: number;
	pit_tax_deduction_vnd: number;
	net_payout_amount_vnd: number;
	bank_bin?: string | null;
	bank_short_name?: string | null;
	account_number?: string | null;
	account_holder?: string | null;
	name_match_status: NameMatchStatus;
	risk_score: number;
	risk_level: RiskLevel;
	risk_reasons: string[];
	status: PayoutStatus;
	tx_reference?: string | null;
	created_at: string;
	processed_at?: string | null;
}

export interface AdminPayoutListResponse {
	items: AdminPayoutItem[];
	total: number;
	limit: number;
	offset: number;
}

export interface PayoutRiskResponse {
	payout_id: string;
	risk_score: number;
	risk_level: RiskLevel;
	reasons: string[];
	evaluated_at: string;
}

export interface PayoutApproveResponse {
	status: string;
	payout_id: string;
	tx_reference: string;
	amount_micros: number;
	net_amount_micros: number;
}

export interface PayoutRejectRequest {
	rejection_reason: PayoutRejectionReason;
	notes?: string;
}

export interface PayoutRejectResponse {
	status: string;
	payout_id: string;
	rejection_reason: string;
	rolled_back_balance_micros: number;
}
