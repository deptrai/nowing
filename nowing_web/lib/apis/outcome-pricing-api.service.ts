import type {
	PricingPlanRead,
	PricingPlanUpdate,
	ServiceBreakdownResponse,
} from "@/contracts/types/outcome-pricing.types";
import { baseApiService } from "./base-api.service";

class OutcomePricingApiService {
	getPricingPlan = async (workspaceId: number): Promise<PricingPlanRead> => {
		return baseApiService.get<PricingPlanRead>(`/api/v1/workspaces/${workspaceId}/pricing-plan`);
	};

	updatePricingPlan = async (
		workspaceId: number,
		payload: PricingPlanUpdate
	): Promise<PricingPlanRead> => {
		return baseApiService.put<PricingPlanRead>(
			`/api/v1/workspaces/${workspaceId}/pricing-plan`,
			undefined,
			{ body: payload }
		);
	};

	getServiceBreakdown = async (
		workspaceId: number,
		startDate?: string,
		endDate?: string
	): Promise<ServiceBreakdownResponse> => {
		const qs = new URLSearchParams();
		if (startDate) qs.set("start_date", startDate);
		if (endDate) qs.set("end_date", endDate);
		const query = qs.toString();
		return baseApiService.get<ServiceBreakdownResponse>(
			`/api/v1/workspaces/${workspaceId}/usage/service-breakdown${query ? `?${query}` : ""}`
		);
	};
}

export const outcomePricingApiService = new OutcomePricingApiService();
