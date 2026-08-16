import type {
	PromoCodeClaimRequest,
	PromoCodeClaimResponse,
} from "@/contracts/types/promo-code.types";
import { baseApiService } from "./base-api.service";

class PromoCodeApiService {
	claimPromoCode = async (code: string): Promise<PromoCodeClaimResponse> => {
		return baseApiService.post<PromoCodeClaimResponse>("/api/v1/credits/promo-code/claim", {
			code,
		} as PromoCodeClaimRequest);
	};
}

export const promoCodeApiService = new PromoCodeApiService();
