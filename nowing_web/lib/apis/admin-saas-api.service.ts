"use client";

import { z } from "zod";
import { type PlanDefinition, planDefinition } from "@/contracts/types/workspace.types";
import { baseApiService } from "./base-api.service";

export interface CreatePlanPayload {
	plan_tier: string;
	max_documents?: number | null;
	max_members?: number | null;
	max_runs?: number | null;
	max_storage_bytes?: number | null;
	max_memory_count?: number | null;
	max_memory_bytes?: number | null;
	max_monthly_credits?: number | null;
	max_sources?: number | null;
	support_level?: string | null;
	price_micros?: number | null;
	currency?: string;
	run_period_hours?: number;
}

export interface UpdatePlanPayload {
	max_documents?: number | null;
	max_members?: number | null;
	max_runs?: number | null;
	max_storage_bytes?: number | null;
	max_memory_count?: number | null;
	max_memory_bytes?: number | null;
	max_monthly_credits?: number | null;
	max_sources?: number | null;
	support_level?: string | null;
	price_micros?: number | null;
	currency?: string;
	run_period_hours?: number;
}

class AdminSaasApiService {
	listPlans = async (): Promise<PlanDefinition[]> => {
		return baseApiService.get("/api/v1/admin/saas/plans", z.array(planDefinition));
	};

	getPlan = async (planTier: string): Promise<PlanDefinition> => {
		return baseApiService.get(
			`/api/v1/admin/saas/plans/${encodeURIComponent(planTier)}`,
			planDefinition
		);
	};

	createPlan = async (payload: CreatePlanPayload): Promise<PlanDefinition> => {
		return baseApiService.post("/api/v1/admin/saas/plans", planDefinition, {
			body: payload,
		});
	};

	updatePlan = async (planTier: string, payload: UpdatePlanPayload): Promise<PlanDefinition> => {
		return baseApiService.put(
			`/api/v1/admin/saas/plans/${encodeURIComponent(planTier)}`,
			planDefinition,
			{
				body: payload,
			}
		);
	};

	deletePlan = async (planTier: string): Promise<{ message: string }> => {
		return baseApiService.delete(
			`/api/v1/admin/saas/plans/${encodeURIComponent(planTier)}`,
			z.object({ message: z.string() })
		);
	};
}

export const adminSaasApiService = new AdminSaasApiService();
