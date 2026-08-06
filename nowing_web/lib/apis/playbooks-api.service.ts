import {
	type PlaybookCreateRequest,
	type PlaybookInstantiateRequest,
	type PlaybookListParams,
	type PlaybookUpdateRequest,
	playbookCreateRequest,
	playbookDetail,
	playbookInstantiateRequest,
	playbookInstantiateResponse,
	playbookListResponse,
	playbookUpdateRequest,
} from "@/contracts/types/playbook.types";
import { ValidationError } from "../error";
import { baseApiService } from "./base-api.service";

const BASE = "/api/v1/playbooks";

function rejectIfInvalid<T>(
	parsed: { success: true; data: T } | { success: false; error: { issues: { message: string }[] } }
): T {
	if (!parsed.success) {
		throw new ValidationError(
			`Invalid request: ${parsed.error.issues.map((i) => i.message).join(", ")}`
		);
	}
	return parsed.data;
}

class PlaybooksApiService {
	listPlaybooks = async (params: PlaybookListParams) => {
		const qs = new URLSearchParams({
			workspace_id: String(params.workspace_id),
			limit: String(params.limit),
			offset: String(params.offset),
		});
		return baseApiService.get(`${BASE}?${qs.toString()}`, playbookListResponse);
	};

	getPlaybook = async (playbookId: number) => {
		return baseApiService.get(`${BASE}/${playbookId}`, playbookDetail);
	};

	createPlaybook = async (request: PlaybookCreateRequest) => {
		const data = rejectIfInvalid(playbookCreateRequest.safeParse(request));
		return baseApiService.post(BASE, playbookDetail, { body: data });
	};

	updatePlaybook = async (playbookId: number, request: PlaybookUpdateRequest) => {
		const data = rejectIfInvalid(playbookUpdateRequest.safeParse(request));
		return baseApiService.patch(`${BASE}/${playbookId}`, playbookDetail, { body: data });
	};

	instantiatePlaybook = async (playbookId: number, request: PlaybookInstantiateRequest) => {
		const data = rejectIfInvalid(playbookInstantiateRequest.safeParse(request));
		return baseApiService.post(`${BASE}/${playbookId}/instantiate`, playbookInstantiateResponse, {
			body: data,
		});
	};
}

export const playbooksApiService = new PlaybooksApiService();
