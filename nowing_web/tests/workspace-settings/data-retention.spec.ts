import { expect, test } from "@playwright/test";
import { acquireTestToken, loginUser, registerUser } from "../helpers/api/auth";
import { uploadMarkdown, waitForDocumentReady } from "../helpers/api/documents";
import {
	acceptInvite,
	createInvite,
	createWorkspace,
	deleteWorkspace,
	listWorkspaceRoles,
} from "../helpers/api/workspaces";

/**
 * E2E red-phase ATDD tests for Story 3.7: Data Retention & Lifecycle.
 *
 * All tests are skipped while the data retention UI and backend endpoints are
 * not implemented.
 */

test.describe("Data retention workspace settings", () => {
	test("owner can open data retention tab and configure retention policy", async ({
		page,
		request,
	}) => {
		const ownerToken = await acquireTestToken(request);
		const workspace = await createWorkspace(
			request,
			ownerToken,
			`ATDD Data Retention ${Date.now()}`
		);
		const workspaceId = workspace.id;

		await page.goto(`/dashboard/${workspaceId}/workspace-settings/data-retention`);

		const section = page.getByRole("region", { name: /data retention/i });
		await expect(section).toBeVisible();

		const daysInput = page.getByRole("spinbutton", { name: /retention days/i });
		const autoArchiveSwitch = page.getByRole("switch", { name: /auto.*archive/i });
		const strategySelect = page.getByRole("combobox", { name: /strategy/i });
		const saveButton = page.getByRole("button", { name: /save/i });

		await expect(daysInput).toBeVisible();
		await expect(autoArchiveSwitch).toBeVisible();
		await expect(strategySelect).toBeVisible();

		await daysInput.fill("30");
		await autoArchiveSwitch.check();
		await strategySelect.selectOption("delete");
		await saveButton.click();

		// Settings should persist after reload (AC 2).
		await page.reload();
		await expect(section).toBeVisible();
		await expect(daysInput).toHaveValue("30");
		await expect(autoArchiveSwitch).toBeChecked();
		await expect(strategySelect).toHaveValue("delete");

		await deleteWorkspace(request, ownerToken, workspaceId);
	});

	test("non-owner sees data retention controls read-only", async ({ browser, request }) => {
		const ownerToken = await acquireTestToken(request);
		const workspace = await createWorkspace(
			request,
			ownerToken,
			`ATDD Data Retention RO ${Date.now()}`
		);
		const workspaceId = workspace.id;

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
		await memberPage.goto(`/dashboard/${workspaceId}/workspace-settings/data-retention`);

		const section = memberPage.getByRole("region", { name: /data retention/i });
		await expect(section).toBeVisible();

		const daysInput = memberPage.getByRole("spinbutton", { name: /retention days/i });
		const autoArchiveSwitch = memberPage.getByRole("switch", { name: /auto.*archive/i });
		const strategySelect = memberPage.getByRole("combobox", { name: /strategy/i });

		await expect(daysInput).toBeDisabled();
		await expect(autoArchiveSwitch).toBeDisabled();
		await expect(strategySelect).toBeDisabled();

		await memberContext.close();
		await deleteWorkspace(request, ownerToken, workspaceId);
	});

	test("archived document is removed from document list without reload", async ({
		page,
		request,
	}) => {
		const ownerToken = await acquireTestToken(request);
		const workspace = await createWorkspace(
			request,
			ownerToken,
			`ATDD Data Retention RT ${Date.now()}`
		);
		const workspaceId = workspace.id;

		const filename = `rt-doc-${Date.now()}.md`;
		const upload = await uploadMarkdown(
			request,
			ownerToken,
			workspaceId,
			filename,
			"Content that will be archived."
		);
		const documentId = upload.document_ids[0];
		await waitForDocumentReady(request, ownerToken, workspaceId, documentId, {
			timeoutMs: 60_000,
		});

		await page.goto(`/dashboard/${workspaceId}/new-chat`);
		await expect(page.getByText(filename)).toBeVisible({ timeout: 30_000 });

		// The retention lifecycle is covered by backend tests; here we verify Zero
		// real-time sync by archiving the document through a test-only endpoint and
		// confirming it disappears from the list without a full page reload.
		const backendUrl = process.env.NEXT_PUBLIC_BACKEND_URL ?? "http://localhost:8000";
		await request.post(`${backendUrl}/__e2e__/documents/${documentId}/archive`, {
			headers: { Authorization: `Bearer ${ownerToken}` },
		});

		await expect(page.getByText(filename)).not.toBeVisible({ timeout: 15_000 });

		await deleteWorkspace(request, ownerToken, workspaceId);
	});

	test("owner entering 0 retention days shows a validation error", async ({ page, request }) => {
		const ownerToken = await acquireTestToken(request);
		const workspace = await createWorkspace(
			request,
			ownerToken,
			`ATDD Data Retention 0 ${Date.now()}`
		);
		const workspaceId = workspace.id;

		await page.goto(`/dashboard/${workspaceId}/workspace-settings/data-retention`);

		const autoArchiveSwitch = page.getByRole("switch", { name: /auto.*archive/i });
		const daysInput = page.getByRole("spinbutton", { name: /retention days/i });
		const saveButton = page.getByRole("button", { name: /save/i });

		// Validation only fires when auto-archive is enabled (see data-retention-manager).
		await autoArchiveSwitch.check();
		await daysInput.fill("0");
		await saveButton.click();

		// AC-1: 0 days is not a positive integer → toast error shown, no save.
		await expect(page.getByText(/retention days must be a positive integer/i)).toBeVisible({
			timeout: 10_000,
		});

		await deleteWorkspace(request, ownerToken, workspaceId);
	});

	test("owner entering negative retention days shows a validation error", async ({
		page,
		request,
	}) => {
		const ownerToken = await acquireTestToken(request);
		const workspace = await createWorkspace(
			request,
			ownerToken,
			`ATDD Data Retention Neg ${Date.now()}`
		);
		const workspaceId = workspace.id;

		await page.goto(`/dashboard/${workspaceId}/workspace-settings/data-retention`);

		const autoArchiveSwitch = page.getByRole("switch", { name: /auto.*archive/i });
		const daysInput = page.getByRole("spinbutton", { name: /retention days/i });
		const saveButton = page.getByRole("button", { name: /save/i });

		await autoArchiveSwitch.check();
		await daysInput.fill("-5");
		await saveButton.click();

		// AC-1: negative days is not a positive integer → toast error shown, no save.
		await expect(page.getByText(/retention days must be a positive integer/i)).toBeVisible({
			timeout: 10_000,
		});

		await deleteWorkspace(request, ownerToken, workspaceId);
	});

	test("action select only exposes valid retention actions (archive/delete)", async ({
		page,
		request,
	}) => {
		const ownerToken = await acquireTestToken(request);
		const workspace = await createWorkspace(
			request,
			ownerToken,
			`ATDD Data Retention Action ${Date.now()}`
		);
		const workspaceId = workspace.id;

		await page.goto(`/dashboard/${workspaceId}/workspace-settings/data-retention`);

		const strategySelect = page.getByRole("combobox", { name: /strategy|action/i });

		// The action <select> is constrained to the two valid options, so an
		// invalid action cannot be submitted through the UI — this IS the
		// validation. Selecting each valid option must succeed.
		const options = await strategySelect.locator("option").allTextContents();
		expect(options).toEqual(expect.arrayContaining(["archive", "delete"]));
		// No invalid action option is exposed.
		expect(options.every((o) => o === "archive" || o === "delete")).toBe(true);

		await strategySelect.selectOption("delete");
		await expect(strategySelect).toHaveValue("delete");
		await strategySelect.selectOption("archive");
		await expect(strategySelect).toHaveValue("archive");

		await deleteWorkspace(request, ownerToken, workspaceId);
	});
});
