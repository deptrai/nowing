import type { APIRequestContext } from "@playwright/test";
import { authHeaders, BACKEND_URL } from "./auth";

export type AutomationRow = {
	id: number;
	workspace_id: number;
	name: string;
	status: string;
};

export type RunRow = {
	id: number;
	automation_id: number;
	status: string;
};

export async function createAutomation(
	request: APIRequestContext,
	token: string,
	workspaceId: number,
	name: string
): Promise<AutomationRow> {
	const response = await request.post(`${BACKEND_URL}/api/v1/automations`, {
		headers: authHeaders(token),
		data: {
			workspace_id: workspaceId,
			name,
			definition: {
				schema_version: "1.1",
				name,
				// Explicit billable model snapshot — bypasses the workspace model
				// role check (positive ids count as BYOK and are always allowed),
				// so this works regardless of which global models exist in the env.
				models: {
					chat_model_id: 1,
					image_gen_model_id: 1,
					vision_model_id: 1,
				},
				plan: [
					{
						step_id: "s1",
						action: "agent_task",
						params: { query: "noop" },
					},
				],
			},
		},
	});
	if (!response.ok()) {
		throw new Error(`createAutomation failed (${response.status()}): ${await response.text()}`);
	}
	return (await response.json()) as AutomationRow;
}

export async function deleteAutomation(
	request: APIRequestContext,
	token: string,
	automationId: number
): Promise<void> {
	const response = await request.delete(`${BACKEND_URL}/api/v1/automations/${automationId}`, {
		headers: authHeaders(token),
	});
	if (!response.ok() && response.status() !== 404) {
		throw new Error(
			`deleteAutomation(${automationId}) failed (${response.status()}): ${await response.text()}`
		);
	}
}

export async function runAutomation(
	request: APIRequestContext,
	token: string,
	automationId: number
): Promise<RunRow> {
	const response = await request.post(`${BACKEND_URL}/api/v1/automations/${automationId}/run`, {
		headers: authHeaders(token),
	});
	if (!response.ok()) {
		throw new Error(
			`runAutomation(${automationId}) failed (${response.status()}): ${await response.text()}`
		);
	}
	return (await response.json()) as RunRow;
}
