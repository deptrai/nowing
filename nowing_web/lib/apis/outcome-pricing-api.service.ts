import type {
	OutcomeEventRead,
	OutcomeMeetingBookedPayload,
	OutcomeStatsRead,
	PricingPlanRead,
	PricingPlanUpdate,
} from "@/contracts/types/outcome-pricing.types";
import { baseApiService } from "./base-api.service";

class OutcomePricingApiService {
	getPricingPlan = async (workspaceId: number): Promise<PricingPlanRead> => {
		return baseApiService.get<PricingPlanRead>(
			`/api/v1/workspaces/${workspaceId}/pricing-plan`
		);
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
		payload: OutcomeMeetingBookedPayload
	): Promise<OutcomeEventRead> => {
		return baseApiService.post<OutcomeEventRead>(
			`/api/v1/workspaces/${workspaceId}/outcomes/meeting-booked`,
			payload
		);
	};

	getOutcomeStats = async (workspaceId: number): Promise<OutcomeStatsRead> => {
		return baseApiService.get<OutcomeStatsRead>(
			`/api/v1/workspaces/${workspaceId}/outcomes/stats`
		);
	};
}

export const outcomePricingApiService = new OutcomePricingApiService();
