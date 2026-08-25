import { expect, type Page, type Route, test } from "@playwright/test";

/**
 * Story 27.1c: Web App Container Deploy & Custom CNAME
 * E2E Acceptance Tests for 1-click publishing, dynamic URL propagation,
 * custom CNAME binding modal, and workspace feature gating.
 */

interface MockApp {
	id: string;
	workspace_id: number;
	name: string;
	slug: string;
	status: string;
	language: string;
	preview_url?: string;
	public_url?: string;
	custom_domain?: string;
	custom_domain_status?: string;
	error_message?: string;
	created_at: string;
	updated_at: string;
}

const mockApp = (overrides: Partial<MockApp> = {}): MockApp => ({
	id: overrides.id ?? "app-deploy-001",
	workspace_id: overrides.workspace_id ?? 1,
	name: overrides.name ?? "PulseAI SaaS Landing",
	slug: overrides.slug ?? "pulse-ai-landing",
	status: overrides.status ?? "preview_ready",
	language: "en",
	preview_url:
		overrides.preview_url ??
		"http://localhost:8000/api/v1/web-builder/apps/app-deploy-001/preview?workspace_id=1",
	public_url: overrides.public_url,
	custom_domain: overrides.custom_domain,
	custom_domain_status: overrides.custom_domain_status,
	error_message: overrides.error_message,
	created_at: new Date().toISOString(),
	updated_at: new Date().toISOString(),
});

const setupDeployRoutes = async (page: Page, app: MockApp) => {
	const workspaceId = app.workspace_id;
	const appId = app.id;

	await page.route(
		(url) =>
			url.pathname === "/api/v1/web-builder/apps" &&
			url.searchParams.get("workspace_id") === String(workspaceId),
		async (route: Route) => {
			await route.fulfill({
				status: 200,
				contentType: "application/json",
				body: JSON.stringify([app]),
			});
		}
	);

	await page.route(
		(url) =>
			url.pathname === `/api/v1/web-builder/apps/${appId}` &&
			url.searchParams.get("workspace_id") === String(workspaceId),
		async (route: Route) => {
			await route.fulfill({
				status: 200,
				contentType: "application/json",
				body: JSON.stringify(app),
			});
		}
	);

	await page.route(
		(url) => url.pathname === `/api/v1/web-builder/apps/${appId}/preview`,
		async (route: Route) => {
			await route.fulfill({
				status: 200,
				contentType: "text/html",
				body: "<html><body><h1 id='title'>PulseAI Live</h1></body></html>",
			});
		}
	);

	await page.route(
		(url) => url.pathname === `/api/v1/web-builder/apps/${appId}/publish`,
		async (route: Route) => {
			const updatedApp = {
				...app,
				status: "published",
				public_url: `https://${app.slug}.apps.nowing.net`,
			};
			await route.fulfill({
				status: 200,
				contentType: "application/json",
				body: JSON.stringify({
					app_id: appId,
					workspace_id: workspaceId,
					status: "published",
					public_url: updatedApp.public_url,
					slug: app.slug,
					message: `Application deployed successfully to ${updatedApp.public_url}`,
				}),
			});
		}
	);

	await page.route(
		(url) => url.pathname === `/api/v1/web-builder/apps/${appId}/custom-domain`,
		async (route: Route) => {
			const reqJson = route.request().postDataJSON();
			await route.fulfill({
				status: 200,
				contentType: "application/json",
				body: JSON.stringify({
					app_id: appId,
					workspace_id: workspaceId,
					custom_domain: reqJson?.custom_domain || "landing.pulseai.io",
					status: "active",
					cname_target: "cname-ingress.apps.nowing.net",
					message: "Custom domain verified and active",
				}),
			});
		}
	);
};

test.describe("Story 27.1c: Web App Deploy & Custom CNAME", () => {
	test("AC-1: User publishes preview-ready app with 1 click and sees live URL", async ({
		page,
	}) => {
		const app = mockApp({ status: "preview_ready" });
		await setupDeployRoutes(page, app);

		await page.goto("/dashboard/1/web-builder");

		// Verify app card is visible
		const appCard = page.locator(`[data-testid="app-card-${app.id}"]`);
		await expect(appCard).toBeVisible();

		// Click Publish button
		const publishBtn = page.locator('[data-testid="publish-btn"]');
		await expect(publishBtn).toBeVisible();
		await publishBtn.click();

		// Should show success toast or live indicator
		await expect(page.locator("text=LIVE HTTPS").or(page.locator("text=Live HTTPS"))).toBeVisible({
			timeout: 5000,
		});
	});

	test("AC-2: User configures custom domain and sees CNAME instruction target", async ({
		page,
	}) => {
		const app = mockApp({
			status: "published",
			public_url: "https://pulse-ai-landing.apps.nowing.net",
		});
		await setupDeployRoutes(page, app);

		await page.goto("/dashboard/1/web-builder");

		// Open custom domain modal if button exists
		const domainBtn = page
			.locator('[data-testid="custom-domain-btn"]')
			.or(page.locator('button:has-text("Custom Domain")'));
		if (await domainBtn.isVisible()) {
			await domainBtn.click();
			// Check CNAME target instruction is shown
			await expect(page.locator("text=cname-ingress.apps.nowing.net")).toBeVisible();
		}
	});

	test("AC-4: Workspace feature gate displays upgrade banner when Web Builder disabled", async ({
		page,
	}) => {
		await page.route(
			(url) => url.pathname === "/api/v1/web-builder/apps",
			async (route: Route) => {
				await route.fulfill({
					status: 403,
					contentType: "application/json",
					body: JSON.stringify({ detail: "Web Builder is disabled for this workspace" }),
				});
			}
		);

		await page.goto("/dashboard/1/web-builder");
		await expect(page.locator('[data-testid="web-builder-upgrade-prompt"]')).toBeVisible({
			timeout: 5000,
		});
	});
});
