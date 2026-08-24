import { expect, type Page, type Route, test } from "@playwright/test";

/**
 * Story 27.1b: Web App Build & Preview Runner
 * E2E Acceptance Tests for build progress, preview, logs, rebuild, and feature gating.
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
	error_message?: string;
	created_at: string;
	updated_at: string;
}

const mockApp = (overrides: Partial<MockApp> = {}): MockApp => ({
	id: overrides.id ?? "mock-app-001",
	workspace_id: overrides.workspace_id ?? 1,
	name: overrides.name ?? "Mock App",
	slug: overrides.slug ?? "mock-app",
	status: overrides.status ?? "building",
	language: "en",
	preview_url: overrides.preview_url,
	public_url: overrides.public_url,
	error_message: overrides.error_message,
	created_at: new Date().toISOString(),
	updated_at: new Date().toISOString(),
});

const setupAppRoutes = async (
	page: Page,
	app: MockApp,
	logs = "",
	files: Record<string, string> = {}
) => {
	const workspaceId = app.workspace_id;
	const appId = app.id;

	await page.route(
		`**/api/v1/web-builder/apps?workspace_id=${workspaceId}`,
		async (route: Route) => {
			await route.fulfill({
				status: 200,
				contentType: "application/json",
				body: JSON.stringify([app]),
			});
		}
	);

	await page.route(
		`**/api/v1/web-builder/apps/${appId}?workspace_id=${workspaceId}`,
		async (route: Route) => {
			await route.fulfill({
				status: 200,
				contentType: "application/json",
				body: JSON.stringify(app),
			});
		}
	);

	await page.route(
		`**/api/v1/web-builder/apps/${appId}/build-logs?workspace_id=${workspaceId}`,
		async (route: Route) => {
			await route.fulfill({
				status: 200,
				contentType: "application/json",
				body: JSON.stringify({
					app_id: appId,
					workspace_id: workspaceId,
					logs,
					lines: logs ? logs.split("\n").length : 0,
					status: app.status,
				}),
			});
		}
	);

	await page.route(
		`**/api/v1/web-builder/apps/${appId}/files?workspace_id=${workspaceId}`,
		async (route: Route) => {
			await route.fulfill({
				status: 200,
				contentType: "application/json",
				body: JSON.stringify(files),
			});
		}
	);

	await page.route(
		`**/api/v1/web-builder/apps/${appId}/preview?workspace_id=${workspaceId}`,
		async (route: Route) => {
			const html = `<!DOCTYPE html><html><head><title>Preview</title></head><body><main><h1>${app.name}</h1></main></body></html>`;
			await route.fulfill({
				status: app.status === "preview_ready" ? 200 : 202,
				contentType: "text/html",
				body: html,
			});
		}
	);
};

test.describe("Story 27.1b — Web App Build & Preview Runner", () => {
	test.beforeEach(async ({ page }) => {
		await page.goto("/dashboard/1/web-builder");
	});

	test("[P0] AC-2: shows building progress state and polls until preview_ready", async ({
		page,
	}) => {
		test.setTimeout(60_000);
		test.slow();

		const appId = "mock-building-app";
		let callCount = 0;

		// First response is building; after a couple of polls, become preview_ready
		await page.route("**/api/v1/web-builder/apps?workspace_id=1", async (route: Route) => {
			callCount += 1;
			const status = callCount >= 3 ? "preview_ready" : "building";
			const app = mockApp({ id: appId, status });
			await route.fulfill({
				status: 200,
				contentType: "application/json",
				body: JSON.stringify([app]),
			});
		});

		await page.route(`**/api/v1/web-builder/apps/${appId}?workspace_id=1`, async (route: Route) => {
			callCount += 1;
			const status = callCount >= 5 ? "preview_ready" : "building";
			const app = mockApp({ id: appId, status });
			await route.fulfill({
				status: 200,
				contentType: "application/json",
				body: JSON.stringify(app),
			});
		});

		await page.route(
			`**/api/v1/web-builder/apps/${appId}/preview?workspace_id=1`,
			async (route: Route) => {
				const html = `<!DOCTYPE html><html><body><main><h1>Lead Dashboard</h1></main></body></html>`;
				await route.fulfill({
					status: callCount >= 5 ? 200 : 202,
					contentType: "text/html",
					body: html,
				});
			}
		);

		await page.route(
			`**/api/v1/web-builder/apps/${appId}/files?workspace_id=1`,
			async (route: Route) => {
				await route.fulfill({
					status: 200,
					contentType: "application/json",
					body: JSON.stringify({ "app/page.tsx": "export default function Home() {}" }),
				});
			}
		);

		await page.goto("/dashboard/1/web-builder");

		const buildingIndicator = page.getByTestId("web-builder-building-indicator");
		await expect(buildingIndicator).toBeVisible();
		await expect(buildingIndicator).toContainText(/Building|Installing dependencies/i);

		const previewIframe = page.frameLocator('iframe[data-testid="web-app-preview-frame"]');
		await expect(previewIframe.locator("body")).toBeVisible({ timeout: 45_000 });
		await expect(previewIframe.locator("h1, h2, main")).toContainText(/Lead Dashboard/i);

		await expect(buildingIndicator).toBeHidden();
	});

	test("[P1] AC-2 & AC-5: displays collapsible build logs and failure state when compilation fails", async ({
		page,
	}) => {
		test.setTimeout(30_000);

		const appId = "mock-failed-app";
		const app = mockApp({
			id: appId,
			status: "build_failed",
			error_message: "Module not found: Can't resolve '@/components/missing'",
		});

		await setupAppRoutes(
			page,
			app,
			"Error: Module not found: Can't resolve '@/components/missing'\nnpm ERR! code ELIFECYCLE",
			{ "app/page.tsx": "export default function Home() {}" }
		);

		await page.goto("/dashboard/1/web-builder");

		const errorBanner = page.getByTestId("web-builder-error-banner");
		await expect(errorBanner).toBeVisible();
		await expect(errorBanner).toContainText(/Build Failed/i);

		const toggleLogsBtn = page.getByRole("button", { name: /View build logs|Hide build logs/i });
		await expect(toggleLogsBtn).toBeVisible();
		await toggleLogsBtn.click();

		const logsPanel = page.getByTestId("web-builder-logs-panel");
		await expect(logsPanel).toBeVisible();
		await expect(logsPanel).toContainText(/Error|Module not found|npm ERR/i);

		const retryBtn = page.getByRole("button", { name: /Rebuild|Retry/i });
		await expect(retryBtn).toBeVisible();
	});

	test("[P1] AC-2: allows user to manually trigger rebuild", async ({ page }) => {
		test.setTimeout(30_000);

		const appId = "mock-rebuild-app";
		const app = mockApp({ id: appId, status: "build_failed" });

		await setupAppRoutes(page, app, "Previous build failed", {
			"app/page.tsx": "export default function Home() {}",
		});

		await page.route(`**/api/v1/web-builder/apps/${appId}/build`, async (route: Route) => {
			await route.fulfill({
				status: 202,
				contentType: "application/json",
				body: JSON.stringify({ status: "building", app_id: appId, message: "Build started" }),
			});
		});

		await page.goto("/dashboard/1/web-builder");

		const rebuildBtn = page.getByRole("button", { name: /Rebuild|Biên dịch lại/i });
		await expect(rebuildBtn).toBeVisible();
		await rebuildBtn.click();

		const buildingIndicator = page.getByTestId("web-builder-building-indicator");
		await expect(buildingIndicator).toBeVisible();
	});

	test("[P2] AC-4: shows upgrade prompt when workspace web_builder feature is disabled", async ({
		page,
	}) => {
		test.setTimeout(30_000);

		await page.route("**/api/v1/web-builder/apps?workspace_id=999", async (route: Route) => {
			await route.fulfill({
				status: 403,
				contentType: "application/json",
				body: JSON.stringify({ detail: "Web Builder is not enabled on this workspace plan" }),
			});
		});

		await page.goto("/dashboard/999/web-builder");

		const upgradeBanner = page.getByTestId("web-builder-disabled-gate");
		await expect(upgradeBanner).toBeVisible();
		await expect(upgradeBanner).toContainText(/Upgrade plan|Web Builder is disabled|Nâng cấp gói/i);
	});
});
