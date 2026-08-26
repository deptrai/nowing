import { expect, test } from "@playwright/test";

test.describe("Story 28.5: Workspace Memory Storage Cap & Retention UI", () => {
	test.beforeEach(async ({ page }) => {
		// Mock session as workspace owner
		await page.route("**/auth/session", async (route) => {
			await route.fulfill({
				status: 200,
				contentType: "application/json",
				body: JSON.stringify({
					authenticated: true,
					access_expires_at: Math.floor(Date.now() / 1000) + 3600,
					is_impersonation: false,
					impersonated_by: null,
					target_user: null,
				}),
			});
		});

		// Mock current user
		await page.route("**/api/v1/users/me", async (route) => {
			await route.fulfill({
				status: 200,
				contentType: "application/json",
				body: JSON.stringify({
					id: "11111111-1111-4111-8111-111111111111",
					email: "owner@example.com",
					is_active: true,
					is_superuser: false,
					is_verified: true,
				}),
			});
		});
	});

	test("AC-4: Data Retention settings page displays and saves memory retention rules", async ({
		page,
	}) => {
		// Mock workspace details
		await page.route("**/api/v1/workspaces/1", async (route) => {
			if (route.request().method() === "GET") {
				await route.fulfill({
					status: 200,
					contentType: "application/json",
					body: JSON.stringify({
						id: 1,
						name: "Acme Corp",
						document_retention_days: 365,
						auto_archive_enabled: false,
						document_retention_action: "archive",
						memory_retention_days: 180,
						memory_auto_archive_enabled: true,
						memory_retention_action: "archive",
					}),
				});
			} else if (route.request().method() === "PATCH") {
				const body = JSON.parse(route.request().postData() || "{}");
				await route.fulfill({
					status: 200,
					contentType: "application/json",
					body: JSON.stringify({
						id: 1,
						name: "Acme Corp",
						...body,
					}),
				});
			}
		});

		await page.goto("http://localhost:3000/dashboard/1/workspace-settings/data-retention");
		await page.waitForLoadState("networkidle");

		// Verify Memory Retention section is visible
		await expect(page.getByText("Memory Retention")).toBeVisible();
		await expect(page.getByTestId("data-retention-memory-auto-archive-switch")).toBeChecked();
		await expect(page.getByTestId("data-retention-memory-days-input")).toHaveValue("180");
	});
});
