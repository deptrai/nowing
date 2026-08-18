import {
	type CompanyGraph,
	type ContactUnlockResponse,
	companyGraphSchema,
	contactUnlockResponseSchema,
	type Lead,
	type LeadListResponse,
	type ListLeadsParams,
	leadListResponseSchema,
	leadSchema,
	type ReverseIcpResponse,
	reverseIcpResponseSchema,
	type ZaloDraftResponse,
	type ZnsSendRequest,
	type ZnsSendResponse,
	zaloDraftResponseSchema,
	znsSendResponseSchema,
} from "@/contracts/types/leads.types";
import { baseApiService } from "./base-api.service";

const base = (workspaceId: number | string) => `/api/v1/workspaces/${workspaceId}`;

class LeadsApiService {
	analyzeReverseIcp = async (
		workspaceId: number | string,
		url: string,
		customInstructions?: string
	): Promise<ReverseIcpResponse> => {
		return baseApiService.post(`${base(workspaceId)}/leads/reverse-icp`, reverseIcpResponseSchema, {
			body: { url, custom_instructions: customInstructions },
		});
	};

	listLeads = async (
		workspaceId: number | string,
		params: ListLeadsParams = {}
	): Promise<LeadListResponse> => {
		const qs = new URLSearchParams();
		if (params.client_id) qs.set("client_id", params.client_id);
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

	getZaloDraft = async (
		workspaceId: number | string,
		leadId: string,
		customContext?: string
	): Promise<ZaloDraftResponse> => {
		return baseApiService.post(
			`${base(workspaceId)}/leads/${leadId}/zalo-draft`,
			zaloDraftResponseSchema,
			{
				body: { custom_context: customContext },
			}
		);
	};

	sendZns = async (
		workspaceId: number | string,
		leadId: string,
		data: ZnsSendRequest
	): Promise<ZnsSendResponse> => {
		return baseApiService.post(
			`${base(workspaceId)}/leads/${leadId}/zns-send`,
			znsSendResponseSchema,
			{
				body: data,
			}
		);
	};

	unlockContact = async (
		workspaceId: number | string,
		leadId: string,
		contactId: string
	): Promise<ContactUnlockResponse> => {
		return baseApiService.post(
			`${base(workspaceId)}/leads/${leadId}/contacts/${contactId}/unlock`,
			contactUnlockResponseSchema
		);
	};

	relockContact = async (
		workspaceId: number | string,
		leadId: string,
		contactId: string
	): Promise<ContactUnlockResponse> => {
		return baseApiService.post(
			`${base(workspaceId)}/leads/${leadId}/contacts/${contactId}/relock`,
			contactUnlockResponseSchema
		);
	};
}

export const leadsApiService = new LeadsApiService();
