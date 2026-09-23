import {
	type CreateTopupIntentRequest,
	type PricingTiersResponse,
	pricingTiersResponse,
	type TopupIntent,
	topupIntent,
} from "@/contracts/types/vietqr.types";
import { baseApiService } from "./base-api.service";

class VietqrApiService {
	getPricingTiers = async (): Promise<PricingTiersResponse> => {
		return baseApiService.get("/api/v1/vietqr/pricing-tiers", pricingTiersResponse);
	};

	createTopupIntent = async (request: CreateTopupIntentRequest): Promise<TopupIntent> => {
		return baseApiService.post("/api/v1/vietqr/topup-intents", topupIntent, {
			body: request,
		});
	};

	getTopupIntent = async (intentId: string): Promise<TopupIntent> => {
		return baseApiService.get(`/api/v1/vietqr/topup-intents/${intentId}`, topupIntent);
	};
}

export const vietqrApiService = new VietqrApiService();
