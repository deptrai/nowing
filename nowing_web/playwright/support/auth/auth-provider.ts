import type { AuthProvider } from "@seontechnologies/playwright-utils/auth-session";

/**
 * Nowing Auth Provider — adapts auth-session v4 to Nowing's JWT auth.
 *
 * Environment variables:
 *   TEST_USER_EMAIL    — test user email    (default: test@nowing.test)
 *   TEST_USER_PASSWORD — test user password (default: Admin@Nowing1)
 *   API_URL            — backend base URL   (default: http://localhost:8000)
 *   BASE_URL           — frontend base URL  (default: http://localhost:4998)
 */
const nowingAuthProvider: AuthProvider = {
	getEnvironment: (options) => options?.environment ?? "local",

	getUserIdentifier: (options) => options?.userIdentifier ?? "default",

	// Token data is stored as { access_token, expires_at } in the record
	extractToken: (tokenData) => {
		return (tokenData["access_token"] as string) ?? null;
	},

	extractCookies: (_tokenData) => {
		// Nowing uses Bearer header auth, not cookies — return empty array
		return [];
	},

	isTokenExpired: (_rawToken) => {
		// Let the framework re-authenticate on each session start.
		// Implement JWT expiry parsing here if disk persistence is required.
		return true;
	},

	clearToken: (_options) => {
		// No-op — token lifecycle managed by auth-session storage
	},

	manageAuthToken: async (request, _options) => {
		const email = process.env.TEST_USER_EMAIL ?? "test@nowing.test";
		const password = process.env.TEST_USER_PASSWORD ?? "Admin@Nowing1";
		const apiUrl = process.env.API_URL ?? "http://localhost:8000";

		// FastAPI-Users login: form-encoded, field name is 'username'
		const response = await request.post(`${apiUrl}/auth/jwt/login`, {
			form: { username: email, password },
		});

		if (!response.ok()) {
			throw new Error(`Nowing auth failed (HTTP ${response.status()}): ${await response.text()}`);
		}

		const { access_token, expires_in } = await response.json();
		const expiresAt = Date.now() + (expires_in ?? 3600) * 1000;

		return {
			access_token,
			expires_at: expiresAt,
		};
	},

	getBaseUrl: (_options) => process.env.BASE_URL ?? "http://localhost:4998",
};

export default nowingAuthProvider;
