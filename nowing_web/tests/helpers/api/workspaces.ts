import type { APIRequestContext } from "@playwright/test";
import { authHeaders, BACKEND_URL } from "./auth";

export type WorkspaceRow = {
	id: number;
	name: string;
	description: string | null;
};

export type RoleRow = {
	id: number;
	name: string;
	description: string | null;
};

export type InviteRow = {
	id: number;
	invite_code: string;
	workspace_id: number;
	role: RoleRow | null;
};

export async function listWorkspaceRoles(
	request: APIRequestContext,
	token: string,
	workspaceId: number
): Promise<RoleRow[]> {
	const response = await request.get(`${BACKEND_URL}/api/v1/workspaces/${workspaceId}/roles`, {
		headers: authHeaders(token),
	});
	if (!response.ok()) {
		throw new Error(`listWorkspaceRoles failed (${response.status()}): ${await response.text()}`);
	}
	return (await response.json()) as RoleRow[];
}

export async function createInvite(
	request: APIRequestContext,
	token: string,
	workspaceId: number,
	email: string,
	roleId: number
): Promise<InviteRow> {
	const response = await request.post(`${BACKEND_URL}/api/v1/workspaces/${workspaceId}/invites`, {
		headers: authHeaders(token),
		data: { email, role_id: roleId },
	});
	if (!response.ok()) {
		throw new Error(`createInvite failed (${response.status()}): ${await response.text()}`);
	}
	return (await response.json()) as InviteRow;
}

export async function acceptInvite(
	request: APIRequestContext,
	token: string,
	inviteCode: string
): Promise<void> {
	const response = await request.post(`${BACKEND_URL}/api/v1/invites/accept`, {
		headers: authHeaders(token),
		data: { invite_code: inviteCode },
	});
	if (!response.ok()) {
		throw new Error(`acceptInvite failed (${response.status()}): ${await response.text()}`);
	}
}

export async function createWorkspace(
	request: APIRequestContext,
	token: string,
	name: string,
	description = "E2E test workspace"
): Promise<WorkspaceRow> {
	const response = await request.post(`${BACKEND_URL}/api/v1/workspaces`, {
		headers: authHeaders(token),
		data: { name, description },
	});
	if (!response.ok()) {
		throw new Error(`createWorkspace failed (${response.status()}): ${await response.text()}`);
	}
	return (await response.json()) as WorkspaceRow;
}

export type ModelRolesUpdate = {
	chat_model_id?: number | null;
	image_gen_model_id?: number | null;
	vision_model_id?: number | null;
};

export async function setWorkspaceModelRoles(
	request: APIRequestContext,
	token: string,
	workspaceId: number,
	roles: ModelRolesUpdate
): Promise<void> {
	const response = await request.put(
		`${BACKEND_URL}/api/v1/workspaces/${workspaceId}/model-roles`,
		{
			headers: authHeaders(token),
			data: roles,
		}
	);
	if (!response.ok()) {
		throw new Error(
			`setWorkspaceModelRoles failed (${response.status()}): ${await response.text()}`
		);
	}
}

export async function deleteWorkspace(
	request: APIRequestContext,
	token: string,
	id: number
): Promise<void> {
	const response = await request.delete(`${BACKEND_URL}/api/v1/workspaces/${id}`, {
		headers: authHeaders(token),
	});
	if (!response.ok() && response.status() !== 404) {
		// 404 is acceptable: the test may have already deleted the space.
		throw new Error(
			`deleteWorkspace(${id}) failed (${response.status()}): ${await response.text()}`
		);
	}
}
