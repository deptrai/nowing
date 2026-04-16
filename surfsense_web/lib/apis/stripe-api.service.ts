import {
	type BillingPortalResponse,
	billingPortalResponse,
	type CreateTokenTopupRequest,
	type CreateTokenTopupResponse,
	createTokenTopupResponse,
	type GiftCheckoutResponse,
	giftCheckoutResponse,
	type GiftPlanId,
	type RedeemGiftResponse,
	redeemGiftResponse,
	type RequestGiftResponse,
	requestGiftResponse,
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

	createGiftCheckout = async (
		planId: GiftPlanId,
		durationMonths: 1 | 3 | 6 | 12
	): Promise<GiftCheckoutResponse> => {
		return baseApiService.post("/api/v1/stripe/create-gift-checkout", giftCheckoutResponse, {
			body: { plan_id: planId, duration_months: durationMonths },
		});
	};

	redeemGiftCode = async (code: string): Promise<RedeemGiftResponse> => {
		return baseApiService.post("/api/v1/stripe/redeem-gift", redeemGiftResponse, {
			body: { code },
		});
	};

	requestGift = async (
		planId: GiftPlanId,
		durationMonths: 1 | 3 | 6 | 12
	): Promise<RequestGiftResponse> => {
		return baseApiService.post("/api/v1/stripe/request-gift", requestGiftResponse, {
			body: { plan_id: planId, duration_months: durationMonths },
		});
	};

	getBillingPortal = async (): Promise<BillingPortalResponse> => {
		return baseApiService.get("/api/v1/stripe/billing-portal", billingPortalResponse);
	};

	getStatus = async (): Promise<StripeStatusResponse> => {
		return baseApiService.get("/api/v1/stripe/status", stripeStatusResponse);
	};
}

export const stripeApiService = new StripeApiService();
