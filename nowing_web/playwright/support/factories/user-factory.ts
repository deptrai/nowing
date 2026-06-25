import { type APIRequestContext } from "@playwright/test";

type UserRole = "user" | "admin";

type UserOverrides = {
	role?: UserRole;
	name?: string;
	email?: string;
};

type CreatedUser = {
	id: string;
	email: string;
	name: string;
	role: UserRole;
};

let _counter = 0;

/**
 * Creates a test user via the API.
 * Requires the backend test-helpers endpoint to be enabled (TEST_ENV=true).
 *
 * @param request — Playwright APIRequestContext
 * @param overrides — override defaults
 */
export async function createUserFactory(
	request: APIRequestContext,
	overrides: UserOverrides = {}
): Promise<CreatedUser> {
	const n = ++_counter;
	const timestamp = Date.now();

	const payload = {
		email: overrides.email ?? `test-user-${n}-${timestamp}@nowing.test`,
		name: overrides.name ?? `Test User ${n}`,
		role: overrides.role ?? "user",
	};

	const response = await request.post("/api/test/users", { data: payload });

	if (!response.ok()) {
		throw new Error(
			`createUserFactory failed: HTTP ${response.status()} — ${await response.text()}`
		);
	}

	return response.json() as Promise<CreatedUser>;
}
