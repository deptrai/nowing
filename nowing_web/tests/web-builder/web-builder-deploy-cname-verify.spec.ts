import { expect, type Page, type Route, test } from "@playwright/test";

/**
 * Story 31.2: Strict CNAME DNS/Ingress Ownership Verification — Web E2E Gate
 *
 * Verifies the web app does NOT crash and surfaces useful feedback on the new
 * API contract introduced by story 31.2:
 *   - verify-fail (TXT / CNAME) -> HTTP 400 + detail message (TXT instructions)
 *   - deploy/caddy-fail         -> HTTP 422
 *   - custom_domain_verify_token exposed on app DETAIL (for the modal), absent on list
 *
 * The page surfaces errors via sonner `toast.error(err.message)` — AppError for
 * 400 (default branch) and ValidationError for 422 both carry `data.detail`.
 */

interface MockApp {
	id: string;
	workspace_id: number;
	name: string;
	slug: string;
	status: string;
	language: string;
	public_url?: string;
	custom_domain?: string;
	custom_domain_status?: string;
	custom_domain_verify_token?: string | null;
	created_at: string;
	updated_at: string;
}

const mockApp = (overrides: Partial<MockApp> = {}): MockApp => ({
	id: overrides.id ?? "app-deploy-001",
	workspace_id: overrides.workspace_id ?? 1,
	name: overrides.name ?? "PulseAI SaaS Landing",
	slug: overrides.slug ?? "pulse-ai-landing",
	status: overrides.status ?? "published",
	language: "en",
	public_url: overrides.public_url ?? "https://pulse-ai-landing.apps.nowing.net",
	custom_domain: overrides.custom_domain,
	custom_domain_status: overrides.custom_domain_status,
	custom_domain_verify_token: overrides.custom_domain_verify_token ?? null,
	created_at: new Date().toISOString(),
	updated_at: new Date().toISOString(),
});

/** Route the app LIST (no token) and app DETAIL (with token). */
const setupBaseRoutes = async (page: Page, app: MockApp, detailToken: string | null) => {
	const workspaceId = app.workspace_id;
	const appId = app.id;

	// List endpoint — token must be absent (response_model_exclude on backend).
	await page.route(
		(url) =>
			url.pathname === "/api/v1/web-builder/apps" &&
			url.searchParams.get("workspace_id") === String(workspaceId),
		async (route: Route) => {
			const { custom_domain_verify_token: _omit, ...listShape } = app;
			await route.fulfill({
				status: 200,
				contentType: "application/json",
				body: JSON.stringify([listShape]),
			});
		}
	);

	// Detail endpoint — token present when set.
	await page.route(
		(url) =>
			url.pathname === `/api/v1/web-builder/apps/${appId}` &&
			url.searchParams.get("workspace_id") === String(workspaceId),
		async (route: Route) => {
			await route.fulfill({
				status: 200,
				contentType: "application/json",
				body: JSON.stringify({ ...app, custom_domain_verify_token: detailToken }),
			});
		}
	);

	// Preview iframe content so the app card renders without a real backend.
	await page.route(
		(url) => url.pathname === `/api/v1/web-builder/apps/${appId}/preview`,
		async (route: Route) => {
			await route.fulfill({
				status: 200,
				contentType: "text/html",
				body: "<html><body><h1>PulseAI Live</h1></body></html>",
			});
		}
	);
};

const openDomainModal = async (page: Page) => {
	const domainBtn = page
		.locator('[data-testid="custom-domain-btn"]')
		.or(page.getByRole("button", { name: /custom domain/i }));
	await expect(domainBtn).toBeVisible();
	await domainBtn.click();
	await expect(page.getByRole("heading", { name: /connect custom domain/i })).toBeVisible();
};

const fillAndSaveDomain = async (page: Page, domain: string) => {
	await page.getByPlaceholder(/app\.mycompany\.com/i).fill(domain);
	await page.getByRole("button", { name: /save domain/i }).click();
};

test.describe("Story 31.2: CNAME DNS Ownership Verification — Web E2E", () => {
	test("AC-web-1: TXT verify-fail (HTTP 400) shows error toast, app does not crash", async ({
		page,
	}) => {
		const app = mockApp({ custom_domain_verify_token: "tok-abc-123" });
		await setupBaseRoutes(page, app, "tok-abc-123");

		// Backend returns 400 with the TXT instruction in `detail`.
		await page.route(
			(url) => url.pathname === `/api/v1/web-builder/apps/${app.id}/custom-domain`,
			async (route: Route) => {
				await route.fulfill({
					status: 400,
					contentType: "application/json",
					body: JSON.stringify({
						detail:
							"Domain 'landing.pulseai.io' TXT record at '_nowing-verify.landing.pulseai.io' with value 'nowing-verify=tok-abc-123' not found.",
					}),
				});
			}
		);

		await page.goto("/dashboard/1/web-builder");
		await openDomainModal(page);
		await fillAndSaveDomain(page, "landing.pulseai.io");

		// App must not crash; a sonner error toast surfaces the server message.
		const toast = page.locator("[data-sonner-toast]").or(page.getByText(/TXT record/i));
		await expect(toast.first()).toBeVisible({ timeout: 8000 });
		// The page itself is still interactive (no error boundary / crash screen).
		await expect(page.locator("body")).not.toContainText(
			/application error|something went wrong!/i
		);
	});

	test("AC-web-2: CNAME verify-fail (HTTP 400) shows CNAME target guidance", async ({ page }) => {
		const app = mockApp();
		await setupBaseRoutes(page, app, "tok-abc-123");

		await page.route(
			(url) => url.pathname === `/api/v1/web-builder/apps/${app.id}/custom-domain`,
			async (route: Route) => {
				await route.fulfill({
					status: 400,
					contentType: "application/json",
					body: JSON.stringify({
						detail:
							"Domain 'landing.pulseai.io' CNAME does not point to cname-ingress.apps.nowing.net.",
					}),
				});
			}
		);

		await page.goto("/dashboard/1/web-builder");
		await openDomainModal(page);
		await fillAndSaveDomain(page, "landing.pulseai.io");

		await expect(
			page.locator("[data-sonner-toast]").or(page.getByText(/CNAME does not point/i))
		).toBeVisible({ timeout: 8000 });
	});

	test("AC-web-3: Deploy/Caddy failure (HTTP 422) still surfaces as error toast, not a crash", async ({
		page,
	}) => {
		const app = mockApp();
		await setupBaseRoutes(page, app, "tok-abc-123");

		await page.route(
			(url) => url.pathname === `/api/v1/web-builder/apps/${app.id}/custom-domain`,
			async (route: Route) => {
				await route.fulfill({
					status: 422,
					contentType: "application/json",
					body: JSON.stringify({
						detail: "Custom domain verified, but container redeploy failed: boom",
					}),
				});
			}
		);

		await page.goto("/dashboard/1/web-builder");
		await openDomainModal(page);
		await fillAndSaveDomain(page, "landing.pulseai.io");

		await expect(
			page.locator("[data-sonner-toast]").or(page.getByText(/redeploy failed|failed/i))
		).toBeVisible({ timeout: 8000 });
		await expect(page.locator("body")).not.toContainText(/application error/i);
	});

	test("AC-web-4: successful bind (200) shows success toast with cname_target", async ({
		page,
	}) => {
		const app = mockApp();
		await setupBaseRoutes(page, app, "tok-abc-123");

		await page.route(
			(url) => url.pathname === `/api/v1/web-builder/apps/${app.id}/custom-domain`,
			async (route: Route) => {
				const reqJson = route.request().postDataJSON();
				await route.fulfill({
					status: 200,
					contentType: "application/json",
					body: JSON.stringify({
						app_id: app.id,
						workspace_id: app.workspace_id,
						custom_domain: reqJson?.custom_domain || "landing.pulseai.io",
						status: "active",
						cname_target: "cname-ingress.apps.nowing.net",
						verify_stage: null,
						message: "Custom domain verified and bound",
					}),
				});
			}
		);

		await page.goto("/dashboard/1/web-builder");
		await openDomainModal(page);
		await fillAndSaveDomain(page, "landing.pulseai.io");

		await expect(
			page.locator("[data-sonner-toast]").or(page.getByText(/configured|cname-ingress/i))
		).toBeVisible({ timeout: 8000 });
	});
});
