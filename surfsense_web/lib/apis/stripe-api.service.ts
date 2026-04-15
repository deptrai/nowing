import {
	type BillingPortalResponse,
	billingPortalResponse,
	type CreateTokenTopupRequest,
	type CreateTokenTopupResponse,
	createTokenTopupResponse,
	type StripeStatusResponse,
	stripeStatusResponse,
} from "@/contracts/types/stripe.types";
import { baseApiService } from "./base-api.service";

class StripeApiService {
	createTokenTopupCheckout = async (
		request: CreateTokenTopupRequest
	): Promise<CreateTokenTopupResponse> => {
		return baseApiService.post(
			"/api/v1/stripe/create-token-topup-checkout",
			createTokenTopupResponse,
			{
				body: request,
			}
		);
	};

	getBillingPortal = async (): Promise<BillingPortalResponse> => {
		return baseApiService.get("/api/v1/stripe/billing-portal", billingPortalResponse);
	};

	getStatus = async (): Promise<StripeStatusResponse> => {
		return baseApiService.get("/api/v1/stripe/status", stripeStatusResponse);
	};
}

export const stripeApiService = new StripeApiService();
