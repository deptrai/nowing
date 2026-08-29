import { expect, test } from "@playwright/test";
import { acquireTestToken } from "../helpers/api/auth";
import { appendAssistantMessage, createThread } from "../helpers/api/chat";
import {
	getDocumentChunks,
	updateDocument,
	uploadMarkdown,
	waitForDocumentReady,
} from "../helpers/api/documents";
import { createWorkspace, deleteWorkspace } from "../helpers/api/workspaces";

/**
 * E2E ATDD tests for Story 3.6: Citation Scroll-to-Highlight in Full Document Editor.
 *
 * Each test seeds a document, creates a chat thread with an assistant message that
 * cites one of the document's chunks, then navigates to the thread and uses the
 * citation badge to open the full document editor. The assertions verify that the
 * editor receives the chunk ID and scrolls/highlight the cited text.
 */

test.describe("Citation scroll-to-highlight in editor", () => {
	let workspaceId: number;
	let ownerToken: string;

	test.beforeEach(async ({ request }) => {
		ownerToken = await acquireTestToken(request);
		const workspace = await createWorkspace(
			request,
			ownerToken,
			`ATDD Citation Editor ${Date.now()}`
		);
		workspaceId = workspace.id;
	});

	test.afterEach(async ({ request }) => {
		await deleteWorkspace(request, ownerToken, workspaceId);
	});

	async function seedDocument(
		request: Parameters<typeof uploadMarkdown>[0],
		content: string,
		filename = `citation-source-${Date.now()}.md`
	) {
		const upload = await uploadMarkdown(request, ownerToken, workspaceId, filename, content);
		const documentId = upload.document_ids[0];
		await waitForDocumentReady(request, ownerToken, workspaceId, documentId, { timeoutMs: 60_000 });
		return { documentId, filename };
	}

	async function pickChunkWithMarker(
		request: Parameters<typeof getDocumentChunks>[0],
		documentId: number,
		marker: string
	) {
		const pageSize = 100;
		let page = 0;
		while (true) {
			const chunks = await getDocumentChunks(request, ownerToken, documentId, page, pageSize);
			const chunk = chunks.items.find((c) => c.content.includes(marker));
			if (chunk) return chunk;
			if (!chunks.has_more || chunks.items.length === 0) break;
			page++;
		}
		throw new Error(`Chunk containing marker "${marker}" not found in document ${documentId}`);
	}

	async function openCitationAndEditor(
		page: import("@playwright/test").Page,
		request: Parameters<typeof createThread>[0],
		_documentId: number,
		chunkId: number,
		_chunkContent: string,
		documentTitle: string
	) {
		const thread = await createThread(request, ownerToken, workspaceId);
		await appendAssistantMessage(request, ownerToken, thread.id, `Answer: [citation:${chunkId}]`);

		await page.goto(`/dashboard/${workspaceId}/new-chat/${thread.id}`);
		await expect(page.getByRole("button", { name: `View cited chunk ${chunkId}` })).toBeVisible({
			timeout: 15_000,
		});

		await page.getByRole("button", { name: `View cited chunk ${chunkId}` }).click();
		await expect(page.getByText("Cited chunk")).toBeVisible({ timeout: 15_000 });

		// Open the full document editor from the citation panel.
		await page.locator('aside [data-slot="button"]:has-text("Open")').click();
		await expect(page.getByText(documentTitle)).toBeVisible({ timeout: 15_000 });
	}

	async function selectedText(page: import("@playwright/test").Page) {
		return page.evaluate(() => window.getSelection()?.toString() ?? "");
	}

	test("open full document from citation passes chunkId to editor panel", async ({
		page,
		request,
	}) => {
		const marker = `open-test-${Date.now()}`;
		const content = `${marker} The quick brown fox jumps over the lazy dog. `.repeat(30);
		const { documentId, filename } = await seedDocument(request, content);
		const chunk = await pickChunkWithMarker(request, documentId, marker);

		await openCitationAndEditor(page, request, documentId, chunk.id, chunk.content, filename);

		// The editor panel should be open and showing the document title.
		await expect(page.getByText(filename)).toBeVisible();
		// The cited chunk text should be selected/highlighted in the Plate editor.
		await expect.poll(async () => (await selectedText(page)).includes(marker)).toBe(true);
	});

	test("Plate editor scrolls and highlights cited chunk", async ({ page, request }) => {
		const marker = `plate-test-${Date.now()}`;
		const content =
			`${marker} This sentence is the target chunk for the citation scroll highlight test. `.repeat(
				25
			);
		const { documentId, filename } = await seedDocument(request, content);
		const chunk = await pickChunkWithMarker(request, documentId, marker);

		await openCitationAndEditor(page, request, documentId, chunk.id, chunk.content, filename);

		await expect.poll(async () => (await selectedText(page)).includes(marker)).toBe(true);
	});

	test("Monaco editor scrolls and highlights cited chunk for large documents", async ({
		page,
		request,
	}) => {
		const marker = `monaco-test-${Date.now()}`;
		// A document with >5000 lines forces the backend to report viewer_mode="monaco".
		const lines = Array.from({ length: 5100 }, (_, i) =>
			i === 2500 ? `${marker} target line for monaco highlight` : `line ${i} filler text`
		);
		const { documentId, filename } = await seedDocument(request, lines.join("\n"));
		const chunk = await pickChunkWithMarker(request, documentId, marker);

		await openCitationAndEditor(page, request, documentId, chunk.id, chunk.content, filename);

		// Monaco scrolls the cited marker into the center of the viewport and
		// highlights the line.
		await expect(page.getByText(marker)).toBeVisible({ timeout: 15_000 });
	});

	test("Markdown viewer scrolls and highlights cited chunk", async ({ page, request }) => {
		const marker = `markdown-test-${Date.now()}`;
		const content = `${marker} The quick brown fox jumps over the lazy dog. `.repeat(30);
		const { documentId, filename } = await seedDocument(request, content);

		// Switch the uploaded FILE to a connector-like type so the editor falls back
		// to the read-only MarkdownViewer instead of Plate.
		const doc = await waitForDocumentReady(request, ownerToken, workspaceId, documentId);
		await updateDocument(request, ownerToken, documentId, {
			document_type: "CRAWLED_URL",
			content: doc.content,
			workspace_id: workspaceId,
		});

		const chunk = await pickChunkWithMarker(request, documentId, marker);

		await openCitationAndEditor(page, request, documentId, chunk.id, chunk.content, filename);

		// The read-only MarkdownViewer sets a DOM selection on the cited text.
		await expect.poll(async () => (await selectedText(page)).includes(marker)).toBe(true);
	});

	test("highlight is cleared when editor panel closes or document changes", async ({
		page,
		request,
	}) => {
		const marker = `clear-test-${Date.now()}`;
		const content = `${marker} The quick brown fox jumps over the lazy dog. `.repeat(30);
		const { documentId, filename } = await seedDocument(request, content);
		const chunk = await pickChunkWithMarker(request, documentId, marker);

		await openCitationAndEditor(page, request, documentId, chunk.id, chunk.content, filename);
		await expect.poll(async () => (await selectedText(page)).includes(marker)).toBe(true);

		// The right panel closes citation first, then the editor on a second Escape,
		// which removes the highlight/selection.
		await page.keyboard.press("Escape");
		await page.keyboard.press("Escape");
		await expect(page.getByText(filename)).not.toBeVisible();
		await expect(
			page.locator('[class*="bg-yellow-200"], [class*="bg-yellow-800"]')
		).not.toBeVisible();
		await expect.poll(async () => (await selectedText(page)) === "").toBe(true);
	});
});
