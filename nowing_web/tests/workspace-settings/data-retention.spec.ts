import { expect, type Page, test } from "@playwright/test";
import { acquireTestToken, loginUser, registerUser } from "../helpers/api/auth";
import { uploadMarkdown, waitForDocumentReady } from "../helpers/api/documents";
import {
	acceptInvite,
	createInvite,
	createWorkspace,
	deleteWorkspace,
	listWorkspaceRoles,
} from "../helpers/api/workspaces";

async function dismissOnboardingModal(page: Page) {
	const gotIt = page.getByRole("button", { name: /got it/i });
	try {
		await expect(gotIt).toBeVisible({ timeout: 3000 });
		await gotIt.click();
	} catch {
		// modal not shown in this context
	}
}

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

		try {
			await page.goto(`/dashboard/${workspaceId}/workspace-settings/data-retention`);
			await dismissOnboardingModal(page);

			const section = page.getByRole("region", { name: /data retention/i });
			await expect(section).toBeVisible();

			const daysInput = page.getByTestId("data-retention-days-input");
			const autoArchiveSwitch = page.getByTestId("data-retention-auto-archive-switch");
			const strategySelect = page.getByTestId("data-retention-action-select");
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
		} finally {
			await deleteWorkspace(request, ownerToken, workspaceId).catch((err) => {
				console.error("data-retention cleanup failed:", err);
			});
		}
	});

	test("non-owner sees data retention controls read-only", async ({ browser, request }) => {
		const ownerToken = await acquireTestToken(request);
		const workspace = await createWorkspace(
			request,
			ownerToken,
			`ATDD Data Retention RO ${Date.now()}`
		);
		const workspaceId = workspace.id;
		let memberContext: Awaited<ReturnType<typeof browser.newContext>> | null = null;

		try {
			const memberEmail = `e2e-member-${Date.now()}@nowing.net`;
			const memberPassword = "E2eMemberPassword123!";
			await registerUser(request, memberEmail, memberPassword);
			const memberToken = await loginUser(request, memberEmail, memberPassword);

			const roles = await listWorkspaceRoles(request, ownerToken, workspaceId);
			const editorRole = roles.find((r) => r.name === "Editor");
			if (!editorRole) throw new Error("Editor role not found");

			const invite = await createInvite(
				request,
				ownerToken,
				workspaceId,
				memberEmail,
				editorRole.id
			);
			await acceptInvite(request, memberToken, invite.invite_code);

			memberContext = await browser.newContext({
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
			await dismissOnboardingModal(memberPage);

			const section = memberPage.getByRole("region", { name: /data retention/i });
			await expect(section).toBeVisible();

			const daysInput = memberPage.getByTestId("data-retention-days-input");
			const autoArchiveSwitch = memberPage.getByTestId("data-retention-auto-archive-switch");
			const strategySelect = memberPage.getByTestId("data-retention-action-select");

			await expect(daysInput).toBeDisabled();
			await expect(autoArchiveSwitch).toBeDisabled();
			await expect(strategySelect).toBeDisabled();
		} finally {
			if (memberContext) {
				await memberContext.close().catch((err) => {
					console.error("data-retention cleanup failed:", err);
				});
			}
			await deleteWorkspace(request, ownerToken, workspaceId).catch((err) => {
				console.error("data-retention cleanup failed:", err);
			});
		}
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

		try {
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
			await dismissOnboardingModal(page);
			await expect(page.getByText(filename)).toBeVisible({ timeout: 30_000 });

			// The retention lifecycle is covered by backend tests; here we verify Zero
			// real-time sync by archiving the document through a test-only endpoint and
			// confirming it disappears from the list without a full page reload.
			const backendUrl =
				process.env.NEXT_PUBLIC_FASTAPI_BACKEND_URL ??
				process.env.NEXT_PUBLIC_BACKEND_URL ??
				"http://localhost:8000";
			await request.post(`${backendUrl}/__e2e__/documents/${documentId}/archive`, {
				headers: { Authorization: `Bearer ${ownerToken}` },
			});

			await expect(page.getByText(filename)).not.toBeVisible({ timeout: 15_000 });
		} finally {
			await deleteWorkspace(request, ownerToken, workspaceId).catch((err) => {
				console.error("data-retention cleanup failed:", err);
			});
		}
	});

	test("owner entering 0 retention days shows a validation error", async ({ page, request }) => {
		const ownerToken = await acquireTestToken(request);
		const workspace = await createWorkspace(
			request,
			ownerToken,
			`ATDD Data Retention 0 ${Date.now()}`
		);
		const workspaceId = workspace.id;

		try {
			await page.goto(`/dashboard/${workspaceId}/workspace-settings/data-retention`);
			await dismissOnboardingModal(page);

			const autoArchiveSwitch = page.getByTestId("data-retention-auto-archive-switch");
			const daysInput = page.getByTestId("data-retention-days-input");
			const saveButton = page.getByRole("button", { name: /save/i });

			// Validation only fires when auto-archive is enabled (see data-retention-manager).
			await autoArchiveSwitch.check();
			await daysInput.fill("0");
			await saveButton.click();

			// AC-1: 0 days is not a positive integer → toast error shown, no save.
			await expect(page.getByText(/retention days must be a positive integer/i)).toBeVisible({
				timeout: 10_000,
			});
		} finally {
			await deleteWorkspace(request, ownerToken, workspaceId).catch((err) => {
				console.error("data-retention cleanup failed:", err);
			});
		}
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

		try {
			await page.goto(`/dashboard/${workspaceId}/workspace-settings/data-retention`);
			await dismissOnboardingModal(page);

			const autoArchiveSwitch = page.getByTestId("data-retention-auto-archive-switch");
			const daysInput = page.getByTestId("data-retention-days-input");
			const saveButton = page.getByRole("button", { name: /save/i });

			await autoArchiveSwitch.check();
			await daysInput.fill("-5");
			await saveButton.click();

			// AC-1: negative days is not a positive integer → toast error shown, no save.
			await expect(page.getByText(/retention days must be a positive integer/i)).toBeVisible({
				timeout: 10_000,
			});
		} finally {
			await deleteWorkspace(request, ownerToken, workspaceId).catch((err) => {
				console.error("data-retention cleanup failed:", err);
			});
		}
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

		try {
			await page.goto(`/dashboard/${workspaceId}/workspace-settings/data-retention`);
			await dismissOnboardingModal(page);

			const strategySelect = page.getByTestId("data-retention-action-select");

			// The action <select> is constrained to the two valid options, so an
			// invalid action cannot be submitted through the UI — this IS the
			// validation. Selecting each valid option must succeed.
			await expect(strategySelect.locator("option")).toHaveCount(2);
			const options = await strategySelect.locator("option").allTextContents();
			expect(options).toEqual(expect.arrayContaining(["Archive", "Delete"]));
			// No invalid action option is exposed.
			expect(
				options.map((o) => o.toLowerCase()).every((o) => o === "archive" || o === "delete")
			).toBe(true);

			await strategySelect.selectOption("delete");
			await expect(strategySelect).toHaveValue("delete");
			await strategySelect.selectOption("archive");
			await expect(strategySelect).toHaveValue("archive");
		} finally {
			await deleteWorkspace(request, ownerToken, workspaceId).catch((err) => {
				console.error("data-retention cleanup failed:", err);
			});
		}
	});
});
