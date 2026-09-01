import type { Route } from "@playwright/test";

/**
 * Returns CORS headers that mirror the request Origin so cross-origin
 * mocked responses are accepted by the browser during local E2E runs.
 *
 * Playwright `route.fulfill` does not add CORS headers automatically;
 * tests that mock the backend (running on a different origin from the
 * Next.js dev server) must include these headers or the browser will
 * block the response and the app will redirect to /login.
 */
export async function corsHeaders(route: Route): Promise<Record<string, string>> {
	const origin = (await route.request().headerValue("origin")) || "http://localhost:4444";
	return {
		"Access-Control-Allow-Origin": origin,
		"Access-Control-Allow-Credentials": "true",
		"Access-Control-Allow-Headers":
			"Content-Type, Authorization, X-Requested-With, X-E2E-Mint-Secret, x-playwright-test",
		"Access-Control-Allow-Methods": "GET, POST, PUT, PATCH, DELETE, OPTIONS",
	};
}

export async function fulfillJson(route: Route, status: number, body: unknown): Promise<void> {
	console.log("[E2E route]", route.request().method(), route.request().url());
	if (route.request().method() === "OPTIONS") {
		await route.fulfill({
			status: 204,
			headers: await corsHeaders(route),
		});
		return;
	}
	await route.fulfill({
		status,
		contentType: "application/json",
		headers: await corsHeaders(route),
		body: JSON.stringify(body),
	});
}
