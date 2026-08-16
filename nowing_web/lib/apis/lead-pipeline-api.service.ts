import { z } from "zod";
import {
	type LeadActivityLog,
	type LeadPipelineStage,
	type LeadStageTransitionResponse,
	leadActivityLogSchema,
	leadPipelineStageSchema,
	leadStageTransitionResponseSchema,
	type MemberSpendStatus,
	memberSpendStatusSchema,
} from "@/contracts/types/lead-pipeline.types";
import { baseApiService } from "./base-api.service";

const base = (workspaceId: number | string) => `/api/v1/workspaces/${workspaceId}/leads`;

class LeadPipelineApiService {
	listStages = async (workspaceId: number | string): Promise<LeadPipelineStage[]> => {
		return baseApiService.get(
			`${base(workspaceId)}/pipeline/stages`,
			z.array(leadPipelineStageSchema)
		);
	};

	transitionStage = async (
		workspaceId: number | string,
		leadId: string,
		stageId: string,
		expectedVersion: number,
		note?: string
	): Promise<LeadStageTransitionResponse> => {
		return baseApiService.patch(
			`${base(workspaceId)}/${leadId}/stage`,
			leadStageTransitionResponseSchema,
			{
				body: {
					stage_id: stageId,
					expected_version: expectedVersion,
					note,
				},
			}
		);
	};

	listActivities = async (
		workspaceId: number | string,
		leadId: string
	): Promise<LeadActivityLog[]> => {
		return baseApiService.get(
			`${base(workspaceId)}/${leadId}/activities`,
			z.array(leadActivityLogSchema)
		);
	};

	addActivity = async (
		workspaceId: number | string,
		leadId: string,
		activity: { activity_type: string; title: string; details?: Record<string, any> }
	): Promise<LeadActivityLog> => {
		return baseApiService.post(`${base(workspaceId)}/${leadId}/activities`, leadActivityLogSchema, {
			body: activity,
		});
	};

	assignLead = async (
		workspaceId: number | string,
		leadId: string,
		targetUserId: string,
		reason?: string
	): Promise<any> => {
		return baseApiService.post(`${base(workspaceId)}/${leadId}/assign`, z.any(), {
			body: { target_user_id: targetUserId, reason },
		});
	};

	batchAssignLeads = async (workspaceId: number | string, leadIds: string[]): Promise<any> => {
		return baseApiService.post(`${base(workspaceId)}/assign-batch`, z.any(), {
			body: { lead_ids: leadIds },
		});
	};

	getMySpendStatus = async (workspaceId: number | string): Promise<MemberSpendStatus> => {
		return baseApiService.get(`${base(workspaceId)}/members/spend-status`, memberSpendStatusSchema);
	};

	updateMemberSpendCap = async (
		workspaceId: number | string,
		targetUserId: string,
		monthlySpendCapMicros: number | null
	): Promise<void> => {
		await baseApiService.patch(`${base(workspaceId)}/members/${targetUserId}/spend-cap`, z.any(), {
			body: { monthly_spend_cap_micros: monthlySpendCapMicros },
		});
	};

	updateMemberLeadCapacity = async (
		workspaceId: number | string,
		targetUserId: string,
		isAcceptingLeads: boolean,
		leadCapacity: number
	): Promise<void> => {
		await baseApiService.patch(
			`${base(workspaceId)}/members/${targetUserId}/lead-capacity`,
			z.any(),
			{
				body: { is_accepting_leads: isAcceptingLeads, lead_capacity: leadCapacity },
			}
		);
	};
}

export const leadPipelineApiService = new LeadPipelineApiService();
