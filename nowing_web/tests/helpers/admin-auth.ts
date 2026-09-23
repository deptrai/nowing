import type { Page, Route } from "@playwright/test";
import { fulfillJson } from "./cors";

/**
 * Standard admin auth mocks used by every /admin/* E2E spec.
 *
 * Mocks:
 *   - /auth/session
 *   - /users/me
 *   - /zero/context
 *   - /api/v1/broadcasts/active
 *
 * The superuser id is a valid UUID so the zod schema in user-api.service
 * does not throw a client-side validation error.
 */
export const ADMIN_USER_ID = "11111111-1111-4111-8111-111111111111";

export async function mockAdminAuth(page: Page) {
	await page.route("**/auth/session*", async (route: Route) => {
		await fulfillJson(route, 200, {
			authenticated: true,
			access_expires_at: Date.now() / 1000 + 3_600,
			is_impersonation: false,
			impersonated_by: null,
			target_user: null,
		});
	});

	await page.route("**/users/me*", async (route: Route) => {
		await fulfillJson(route, 200, {
			id: ADMIN_USER_ID,
			email: "admin-test@nowing.net",
			is_active: true,
			is_superuser: true,
			is_verified: true,
			credit_micros_balance: 0,
			display_name: "Admin Test",
			avatar_url: null,
			notification_preferences: null,
		});
	});

	await page.route("**/zero/context*", async (route: Route) => {
		await fulfillJson(route, 200, {
			userId: ADMIN_USER_ID,
			allowedSpaceIds: [1],
		});
	});

	await page.route("**/api/v1/broadcasts/active*", async (route: Route) => {
		await fulfillJson(route, 200, []);
	});
}
