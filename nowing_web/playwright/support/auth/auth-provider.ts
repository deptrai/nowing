import { type AuthProvider } from "@seontechnologies/playwright-utils/auth-session";

/**
 * Nowing Auth Provider
 * Adapts the auth-session utility to Nowing's JWT-based auth.
 *
 * Environment variables required:
 *   TEST_USER_EMAIL    — test user email
 *   TEST_USER_PASSWORD — test user password
 *   API_URL            — backend base URL (default: http://localhost:8000)
 */
const nowingAuthProvider: AuthProvider = {
	getEnvironment: (options) => options.environment || "local",

	getUserIdentifier: (options) => options.userIdentifier || "default",

	extractToken: (storageState) => {
		const tokenEntry = storageState.origins?.[0]?.localStorage?.find(
			(item) => item.name === "nowing_access_token"
		);
		return tokenEntry?.value;
	},

	isTokenExpired: (storageState) => {
		const expiryEntry = storageState.origins?.[0]?.localStorage?.find(
			(item) => item.name === "nowing_token_expiry"
		);
		if (!expiryEntry) return true;
		return Date.now() > parseInt(expiryEntry.value, 10);
	},

	manageAuthToken: async (request, options) => {
		const email = process.env.TEST_USER_EMAIL;
		const password = process.env.TEST_USER_PASSWORD;
		const apiUrl = process.env.API_URL || "http://localhost:8000";

		if (!email || !password) {
			throw new Error("TEST_USER_EMAIL and TEST_USER_PASSWORD must be set in .env.test");
		}

		const response = await request.post(`${apiUrl}/api/auth/login`, {
			data: { email, password },
		});

		if (!response.ok()) {
			throw new Error(
				`Auth failed for user "${options.userIdentifier}": HTTP ${response.status()}`
			);
		}

		const { access_token, expires_in } = await response.json();
		const expiryTime = Date.now() + (expires_in ?? 3600) * 1000;

		return {
			cookies: [],
			origins: [
				{
					origin: process.env.BASE_URL || "http://localhost:3999",
					localStorage: [
						{ name: "nowing_access_token", value: access_token },
						{ name: "nowing_token_expiry", value: String(expiryTime) },
					],
				},
			],
		};
	},
};

export default nowingAuthProvider;
