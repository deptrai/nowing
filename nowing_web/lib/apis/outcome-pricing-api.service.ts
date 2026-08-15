import type {
	OutcomeEventRead,
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
			payload
		);
	};

	recordMeetingBooked = async (
		workspaceId: number,
		payload: {
			lead_id: string;
			attribution?: string;
			metadata?: Record<string, unknown>;
		}
	): Promise<OutcomeEventRead> => {
		return baseApiService.post<OutcomeEventRead>(
			`/api/v1/workspaces/${workspaceId}/outcomes/meeting-booked`,
			payload
		);
	};

	getServiceBreakdown = async (
		workspaceId: number,
		startDate?: string,
		endDate?: string
	): Promise<ServiceBreakdownResponse> => {
		const params = new URLSearchParams({
			workspace_id: String(workspaceId),
		});
		if (startDate) params.set("start_date", startDate);
		if (endDate) params.set("end_date", endDate);

		return baseApiService.get<ServiceBreakdownResponse>(
			`/api/v1/usage/service-breakdown?${params.toString()}`
		);
	};
}

export const outcomePricingApiService = new OutcomePricingApiService();
