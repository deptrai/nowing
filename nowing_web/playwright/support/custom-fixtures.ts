import { test as base } from "@playwright/test";
import { createUserFactory } from "./factories/user-factory";

type TestUser = {
	id: string;
	email: string;
	name: string;
	role: string;
};

type CustomFixtures = {
	testUser: TestUser;
};

/**
 * Custom project fixtures for Nowing tests.
 * Extend with project-specific test data and helpers.
 */
export const test = base.extend<CustomFixtures>({
	testUser: async ({ request }, use) => {
		const user = await createUserFactory(request, {
			role: "user",
		});
		await use(user);
		// Cleanup: delete user via API after test
		await request.delete(`/api/test/users/${user.id}`).catch(() => {
			/* best-effort cleanup */
		});
	},
});
