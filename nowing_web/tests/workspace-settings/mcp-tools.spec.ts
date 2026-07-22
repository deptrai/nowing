import { expect, test } from "@playwright/test";
import { acquireTestToken, loginUser, registerUser } from "../helpers/api/auth";
import {
	acceptInvite,
	createInvite,
	createWorkspace,
	deleteWorkspace,
	listWorkspaceRoles,
} from "../helpers/api/workspaces";

/**
 * E2E acceptance tests for Story 2.5: Workspace MCP Tool Toggle.
 */

test.describe("Workspace MCP tools", () => {
	let workspaceId: number;
	let ownerToken: string;

	test.beforeEach(async ({ request }) => {
		ownerToken = await acquireTestToken(request);
		const workspace = await createWorkspace(request, ownerToken, `ATDD MCP Tools ${Date.now()}`);
		workspaceId = workspace.id;
	});

	test.afterEach(async ({ request }) => {
		await deleteWorkspace(request, ownerToken, workspaceId);
	});

	test("owner sees all MCP tools with toggles on workspace settings", async ({ page }) => {
		await page.goto(`/dashboard/${workspaceId}/workspace-settings/general`);

		const section = page.getByRole("region", { name: /mcp tools/i });
		await expect(section).toBeVisible();

		// Built-in scraper and KB tools should appear.
		await expect(section.getByText(/google search/i)).toBeVisible();
		await expect(section.getByText(/search knowledge base/i)).toBeVisible();

		// Selector tools are always on and should not be toggle-able.
		const listWorkspacesToggle = section.locator("[data-testid='toggle-nowing_list_workspaces']");
		await expect(listWorkspacesToggle).toBeDisabled();
	});

	test("owner can disable a tool and the state persists after reload", async ({ page }) => {
		await page.goto(`/dashboard/${workspaceId}/workspace-settings/general`);

		const section = page.getByRole("region", { name: /mcp tools/i });
		await expect(section).toBeVisible();

		const toggle = section.locator("[data-testid='toggle-nowing_google_search']");
		await expect(toggle).toBeVisible();
		await expect(toggle).toBeChecked();

		await toggle.click();
		await expect(toggle).not.toBeChecked();

		// State should survive a reload.
		await page.reload();
		await expect(section).toBeVisible();
		await expect(toggle).not.toBeChecked();
	});

	test("non-owner sees MCP tools read-only", async ({ browser, request }) => {
		const memberEmail = `e2e-member-${Date.now()}@nowing.net`;
		const memberPassword = "E2eMemberPassword123!";
		await registerUser(request, memberEmail, memberPassword);
		const memberToken = await loginUser(request, memberEmail, memberPassword);

		const roles = await listWorkspaceRoles(request, ownerToken, workspaceId);
		const editorRole = roles.find((r) => r.name === "Editor");
		if (!editorRole) throw new Error("Editor role not found");

		const invite = await createInvite(request, ownerToken, workspaceId, memberEmail, editorRole.id);
		await acceptInvite(request, memberToken, invite.invite_code);

		const memberContext = await browser.newContext({
			storageState: {
				cookies: [
					{
						name: process.env.SESSION_COOKIE_NAME || "nowing_session",
						value: memberToken,
						domain: "localhost",
						path: "/",
						httpOnly: true,
						secure: false,
						sameSite: "Lax",
						expires: Math.floor(Date.now() / 1000) + 3600,
					},
				],
				origins: [],
			},
		});
		const memberPage = await memberContext.newPage();
		await memberPage.goto(`/dashboard/${workspaceId}/workspace-settings/general`);

		const section = memberPage.getByRole("region", { name: /mcp tools/i });
		await expect(section).toBeVisible();

		const toggle = section.locator("[data-testid='toggle-nowing_google_search']");
		await expect(toggle).toBeVisible();
		await expect(toggle).toBeDisabled();

		await memberContext.close();
	});
});
