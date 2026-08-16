import { z } from "zod";
import { baseApiService } from "./base-api.service";

export const impersonationTokenResponse = z.object({
	access_token: z.string(),
});

class AdminUsersApiService {
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
