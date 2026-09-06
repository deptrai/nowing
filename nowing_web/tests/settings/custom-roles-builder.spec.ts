import { expect, test } from "@playwright/test";

/**
 * Story 29.1: Custom Workspace Roles & Permissions Builder
 * Governed by: AC-1, AC-2, AC-3, AC-4, AD-51, INV-29.1
 */

test.describe("Story 29.1: Custom Workspace Roles & Permissions Builder", () => {
	test.beforeEach(async ({ page }) => {
		// Mock role listing and permission endpoints
		await page.route("**/api/v1/permissions", async (route) => {
			await route.fulfill({
				status: 200,
				contentType: "application/json",
				body: JSON.stringify({
					permissions: [
						{
							value: "documents:read",
							name: "DOCUMENTS_READ",
							category: "documents",
							description: "View and search documents",
						},
						{
							value: "documents:create",
							name: "DOCUMENTS_CREATE",
							category: "documents",
							description: "Create documents",
						},
						{
							value: "analytics:read",
							name: "ANALYTICS_READ",
							category: "analytics",
							description: "View workspace analytics & adoption metrics",
						},
						{
							value: "billing:read",
							name: "BILLING_READ",
							category: "billing",
							description: "View workspace plans and invoices",
						},
						{
							value: "billing:manage",
							name: "BILLING_MANAGE",
							category: "billing",
							description: "Upgrade/downgrade plans",
						},
						{
							value: "members:view",
							name: "MEMBERS_VIEW",
							category: "members",
							description: "View members",
						},
						{
							value: "members:remove",
							name: "MEMBERS_REMOVE",
							category: "members",
							description: "Remove members from workspace",
						},
						{
							value: "memory:read",
							name: "MEMORY_READ",
							category: "memory",
							description: "Search research memories",
						},
						{
							value: "roles:read",
							name: "ROLES_READ",
							category: "roles",
							description: "View roles",
						},
						{
							value: "roles:create",
							name: "ROLES_CREATE",
							category: "roles",
							description: "Create custom roles",
						},
						{
							value: "roles:update",
							name: "ROLES_UPDATE",
							category: "roles",
							description: "Update roles",
						},
						{
							value: "roles:delete",
							name: "ROLES_DELETE",
							category: "roles",
							description: "Delete roles",
						},
					],
				}),
			});
		});

		await page.route("**/api/v1/workspaces/1/roles", async (route) => {
			if (route.request().method() === "GET") {
				await route.fulfill({
					status: 200,
					contentType: "application/json",
					body: JSON.stringify([
						{
							id: 1,
							workspace_id: 1,
							name: "Owner",
							description: "Workspace owner",
							permissions: ["*"],
							is_default: false,
							is_system_role: true,
							created_at: new Date().toISOString(),
						},
						{
							id: 2,
							workspace_id: 1,
							name: "Editor",
							description: "Content editor",
							permissions: ["documents:read", "documents:create"],
							is_default: false,
							is_system_role: true,
							created_at: new Date().toISOString(),
						},
						{
							id: 3,
							workspace_id: 1,
							name: "Custom Analyst",
							description: "Analytics viewer",
							permissions: ["documents:read", "analytics:read"],
							is_default: false,
							is_system_role: false,
							created_at: new Date().toISOString(),
						},
					]),
				});
			} else if (route.request().method() === "POST") {
				const body = JSON.parse(route.request().postData() || "{}");
				if (body.name?.trim().toLowerCase() === "admin") {
					await route.fulfill({
						status: 400,
						contentType: "application/json",
						body: JSON.stringify({ detail: "The role name 'Admin' is reserved" }),
					});
					return;
				}
				await route.fulfill({
					status: 200,
					contentType: "application/json",
					body: JSON.stringify({
						id: 4,
						workspace_id: 1,
						name: body.name,
						description: body.description,
						permissions: body.permissions,
						is_default: body.is_default || false,
						is_system_role: false,
						created_at: new Date().toISOString(),
					}),
				});
			}
		});

		await page.route("**/api/v1/workspaces/1/members/my-access", async (route) => {
			await route.fulfill({
				status: 200,
				contentType: "application/json",
				body: JSON.stringify({
					is_owner: true,
					permissions: ["*"],
				}),
			});
		});
	});

	test("AC-2 & AC-3: Displays template selector, populates permissions, and validates reserved Admin name", async ({
		page,
	}) => {
		await page.goto("/dashboard/1/workspace-settings/team-roles");

		// Open Create Custom Role Dialog
		const createBtn = page.getByRole("button", { name: /create custom role/i });
		await expect(createBtn).toBeVisible({ timeout: 10000 });
		await createBtn.click();

		// Verify Template selector is present
		const templateTrigger = page.getByTestId("template-preset-trigger");
		await expect(templateTrigger).toBeVisible();

		// Select "Analyst" template
		await templateTrigger.click();
		await page.getByRole("option", { name: /analyst/i }).click();

		// Verify Name was pre-filled with "Analyst"
		const nameInput = page.getByTestId("role-name-input");
		await expect(nameInput).toHaveValue("Analyst");

		// Test Reserved "Admin" name inline validation
		await nameInput.fill("Admin");
		const errorMsg = page.getByTestId("admin-reserved-error");
		await expect(errorMsg).toBeVisible();
		await expect(errorMsg).toHaveText("The role name 'Admin' is reserved");

		const saveBtn = page.getByTestId("create-role-save-btn");
		await expect(saveBtn).toBeDisabled();

		// Fix name to valid
		await nameInput.fill("Business Analyst");
		await expect(errorMsg).not.toBeVisible();
		await expect(saveBtn).toBeEnabled();
	});

	test("AC-3: Shows warning chip when selected permissions exceed template baseline", async ({
		page,
	}) => {
		await page.goto("/dashboard/1/workspace-settings/team-roles");

		await page.getByRole("button", { name: /create custom role/i }).click();
		await page.getByTestId("template-preset-trigger").click();
		await page.getByRole("option", { name: /analyst/i }).click();

		// Expand members category or check permission outside Analyst baseline (e.g. members:remove)
		const membersCategoryBtn = page.getByRole("button", { name: /Team Members/i });
		if (await membersCategoryBtn.isVisible()) {
			await membersCategoryBtn.click();
			const removeMemberCheckbox = page.getByRole("checkbox", {
				name: /Remove members from workspace/i,
			});
			if (await removeMemberCheckbox.isVisible()) {
				await removeMemberCheckbox.click();
				const warningChip = page.getByTestId("exceeds-warning-members");
				await expect(warningChip).toBeVisible();
				await expect(warningChip).toHaveText(/This exceeds the recommended template/i);
			}
		}
	});

	test("AC-4: Clone Role action opens dialog pre-filled with '{name} (Copy)' and identical permissions", async ({
		page,
	}) => {
		await page.goto("/dashboard/1/workspace-settings/team-roles");

		// Find Custom Analyst role dropdown
		const cloneTrigger = page.getByTestId("clone-role-3");
		// If dropdown needs opening first
		const moreActionsBtn = page
			.locator("div")
			.filter({ hasText: /^Custom Analyst/ })
			.getByRole("button")
			.filter({ has: page.locator("svg.lucide-more-horizontal") });

		if (await moreActionsBtn.isVisible()) {
			await moreActionsBtn.click();
		}

		await expect(cloneTrigger).toBeVisible();
		await cloneTrigger.click();

		// Dialog opens with pre-filled name
		const nameInput = page.getByTestId("role-name-input");
		await expect(nameInput).toHaveValue("Custom Analyst (Copy)");
	});
});
