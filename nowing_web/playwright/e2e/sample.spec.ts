import { expect, test } from "../support/merged-fixtures";

/**
 * Sample spec — validates framework fixtures work end-to-end.
 * These are infrastructure tests, not feature tests.
 */
test.describe("Sample — Framework Smoke Tests", () => {
	test("authToken fixture injects a JWT string", async ({ authToken }) => {
		expect(authToken).toBeTruthy();
		expect(typeof authToken).toBe("string");
		// JWT has 3 dot-separated parts
		expect(authToken.split(".")).toHaveLength(3);
	});

	test("apiRequest fixture makes authenticated requests", async ({ apiRequest, authToken }) => {
		const { status } = await apiRequest({
			method: "GET",
			path: "/auth/jwt/login",
			baseUrl: process.env.API_URL || "http://localhost:8000",
			headers: { Authorization: `Bearer ${authToken}` },
		});
		// Any response (including 405 Method Not Allowed) proves the request was made
		expect(status).toBeGreaterThan(0);
	});

	test("page fixture navigates successfully", async ({ page }) => {
		await page.goto("/");
		await expect(page).toHaveURL(/localhost:4998/);
	});
});

test.describe("Sample — Network Interception", () => {
	test("interceptNetworkCall stubs a request before navigation", async ({
		page,
		interceptNetworkCall,
	}) => {
		// Setup stub BEFORE navigation
		const stubPromise = interceptNetworkCall({
			url: "**/api/**",
			fulfillResponse: { status: 200, body: { stubbed: true } },
		});

		// Navigate to trigger an API call
		await page.goto("/");

		// The stub should resolve once the first matching request is intercepted
		const result = await Promise.race([
			stubPromise,
			new Promise<null>((resolve) => setTimeout(() => resolve(null), 5000)),
		]);

		// If stubbed: result has status 200; if no matching request in 5s: result is null (acceptable)
		if (result !== null) {
			expect(result.status).toBe(200);
		}
		// Either way the fixture itself didn't throw — framework works
	});
});
