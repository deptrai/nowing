import type { PromoCodeClaimResponse } from "@/contracts/types/promo-code.types";
import { baseApiService } from "./base-api.service";

class PromoCodeApiService {
	claimPromoCode = async (code: string): Promise<PromoCodeClaimResponse> => {
		return baseApiService.post<PromoCodeClaimResponse>(
			"/api/v1/credits/promo-code/claim",
			undefined,
			{ body: JSON.stringify({ code }) }
		);
	};
}

export const promoCodeApiService = new PromoCodeApiService();
