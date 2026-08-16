import { z } from "zod";
import { baseApiService } from "./base-api.service";

export const impersonationTokenResponse = z.object({
	access_token: z.string(),
});

export const userListItem = z.object({
	id: z.string(),
	email: z.string(),
	is_active: z.boolean(),
	is_superuser: z.boolean(),
	is_verified: z.boolean(),
});

export const userListResponse = z.array(userListItem);

export const workspaceListItem = z.object({
	id: z.number(),
	name: z.string(),
	description: z.string().nullable(),
	vertical: z.string().nullable(),
	created_at: z.string().nullable(),
	user_id: z.string().nullable(),
	citations_enabled: z.boolean(),
	api_access_enabled: z.boolean(),
	qna_custom_instructions: z.string().nullable(),
	member_count: z.number(),
	is_owner: z.boolean(),
});

export const workspaceListResponse = z.array(workspaceListItem);

class AdminUsersApiService {
	listUsers = async (): Promise<
		{ id: string; email: string; is_active: boolean; is_superuser: boolean; is_verified: boolean }[]
	> => {
		return baseApiService.get("/api/v1/admin/users", userListResponse);
	};

	listWorkspaces = async (): Promise<z.infer<typeof workspaceListItem>[]> => {
		return baseApiService.get("/api/v1/admin/workspaces", workspaceListResponse);
	};

	impersonate = async (userId: string, ticketRef: string): Promise<{ access_token: string }> => {
		const searchParams = new URLSearchParams({ ticket_ref: ticketRef });
		return baseApiService.post(
			`/api/v1/admin/users/${userId}/impersonate?${searchParams.toString()}`,
			impersonationTokenResponse
		);
	};

	exitImpersonation = async (): Promise<null> => {
		return baseApiService.post(`/api/v1/admin/impersonate/exit`, z.null());
	};
}

export const adminUsersApiService = new AdminUsersApiService();
