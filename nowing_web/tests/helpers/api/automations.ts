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
