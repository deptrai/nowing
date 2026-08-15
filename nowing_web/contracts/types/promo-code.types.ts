export interface PromoCodeClaimRequest {
	code: string;
}

export interface PromoCodeClaimResponse {
	code: string;
	credit_micros_granted: number;
	new_balance_micros: number;
	message: string;
}
