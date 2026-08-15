import {
	type CompanyGraph,
	companyGraphSchema,
	type Lead,
	type LeadListResponse,
	type ListLeadsParams,
	leadListResponseSchema,
	leadSchema,
} from "@/contracts/types/leads.types";
import { baseApiService } from "./base-api.service";

const base = (workspaceId: number | string) => `/api/v1/workspaces/${workspaceId}`;

class LeadsApiService {
	listLeads = async (
		workspaceId: number | string,
		params: ListLeadsParams = {}
	): Promise<LeadListResponse> => {
		const qs = new URLSearchParams();
		if (params.source) qs.set("source", params.source);
		if (params.intent) qs.set("intent", params.intent);
		if (params.min_score !== undefined) qs.set("min_score", String(params.min_score));
		if (params.status) qs.set("status", params.status);
		if (params.search) qs.set("search", params.search);
		if (params.sort) qs.set("sort", params.sort);
		if (params.limit !== undefined) qs.set("limit", String(params.limit));
		if (params.offset !== undefined) qs.set("offset", String(params.offset));

		const query = qs.toString();
		return baseApiService.get(
			`${base(workspaceId)}/leads${query ? `?${query}` : ""}`,
			leadListResponseSchema
		);
	};

	getLead = async (workspaceId: number | string, leadId: string): Promise<Lead> => {
		return baseApiService.get(`${base(workspaceId)}/leads/${leadId}`, leadSchema);
	};

	updateLeadStatus = async (
		workspaceId: number | string,
		leadId: string,
		status: string
	): Promise<Lead> => {
		return baseApiService.patch(`${base(workspaceId)}/leads/${leadId}/status`, leadSchema, {
			body: { status },
		});
	};

	getCompanyGraph = async (
		workspaceId: number | string,
		companyName: string
	): Promise<CompanyGraph> => {
		return baseApiService.get(
			`${base(workspaceId)}/companies/${encodeURIComponent(companyName)}/graph`,
			companyGraphSchema
		);
	};
}

export const leadsApiService = new LeadsApiService();
