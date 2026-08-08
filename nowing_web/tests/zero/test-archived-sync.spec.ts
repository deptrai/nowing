import { expect, test } from "@playwright/test";
import { acquireTestToken } from "../helpers/api/auth";
import { uploadMarkdown, waitForDocumentReady } from "../helpers/api/documents";
import { createWorkspace, deleteWorkspace } from "../helpers/api/workspaces";

/**
 * E2E tests for Zero real-time sync of `archived_at` changes.
 *
 * The Zero document query (`zero/queries/documents.ts`) filters with
 * `.where("archivedAt", "IS", null)`, so when a document's `archived_at`
 * column is set the row should drop out of the synced view — and the web
 * document list should update without a full page reload.
 *
 * NOTE: This test requires a running backend with Zero sync enabled (the
 * Zero cache server + the e2e test backend that mounts the
 * `__e2e__/documents/{id}/archive` endpoint via
 * `nowing_backend/tests/e2e/run_backend.py`). Without those services the
 * Playwright run will fail at the auth/workspace-creation step, not inside
 * the sync assertion. See AGENTS.md "Story 9.1a verification commands" for
 * the local run recipe.
 */
test.describe("Zero sync — archived_at", () => {
	test("archived document disappears from the document list without a page reload", async ({
		page,
		request,
	}) => {
		const ownerToken = await acquireTestToken(request);
		const workspace = await createWorkspace(
			request,
			ownerToken,
			`ATDD Zero Archived Sync ${Date.now()}`
		);
		const workspaceId = workspace.id;

		const filename = `zero-sync-doc-${Date.now()}.md`;
		const upload = await uploadMarkdown(
			request,
			ownerToken,
			workspaceId,
			filename,
			"Content that will be archived via Zero sync."
		);
		const documentId = upload.document_ids[0];
		await waitForDocumentReady(request, ownerToken, workspaceId, documentId, {
			timeoutMs: 60_000,
		});

		// Open the new-chat view which renders the Zero-synced document list.
		await page.goto(`/dashboard/${workspaceId}/new-chat`);
		await expect(page.getByText(filename)).toBeVisible({ timeout: 30_000 });

		// Archive the document through the test-only endpoint. The backend
		// sets `archived_at`; Zero sync propagates the row change to the web
		// client and the document query (which filters `archivedAt IS null`)
		// drops it from the list — no page reload required.
		const backendUrl = process.env.NEXT_PUBLIC_FASTAPI_BACKEND_URL ?? "http://localhost:8000";
		await request.post(`${backendUrl}/__e2e__/documents/${documentId}/archive`, {
			headers: { Authorization: `Bearer ${ownerToken}` },
		});

		// AC-6: the document list updates via Zero sync without a reload.
		await expect(page.getByText(filename)).not.toBeVisible({ timeout: 15_000 });

		await deleteWorkspace(request, ownerToken, workspaceId);
	});
});
