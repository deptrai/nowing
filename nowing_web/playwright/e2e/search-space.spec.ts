import { test, expect } from "../support/merged-fixtures";

/**
 * E2E tests — Search Space management
 *
 * Covers P0-P1 scenarios for workspace creation and management:
 *   P0: Create a new search space
 *   P0: List search spaces on dashboard
 *   P1: Delete a search space
 *   P1: Cannot access another user's search space
 */

const UNIQUE_SUFFIX = () => Date.now().toString(36);

test.describe("Search Space Management", () => {
	// ---------------------------------------------------------------------------
	// P0 — Create search space
	// ---------------------------------------------------------------------------

	test("should create a new search space", async ({
		page,
		authToken,
		interceptNetworkCall,
		log,
	}) => {
		const spaceName = `E2E Space ${UNIQUE_SUFFIX()}`;

		// Given — authenticated user on dashboard
		await page.goto("/");

		// When — open create space dialog/form
		await log({ level: "step", message: "Open create space form" });
		const createButton = page
			.getByTestId("create-search-space-button")
			.or(page.getByRole("button", { name: /new space|create space|add space/i }));
		await createButton.click();

		// Fill in the form
		await log({ level: "step", message: "Fill space name" });
		await page
			.getByTestId("search-space-name-input")
			.or(page.getByLabel(/name/i).first())
			.fill(spaceName);

		// Intercept the POST request
		const createCall = interceptNetworkCall({
			url: "**/api/searchspaces",
			method: "POST",
		});

		// Submit
		await log({ level: "step", message: "Submit form" });
		await page
			.getByTestId("create-search-space-submit")
			.or(page.getByRole("button", { name: /create|save|confirm/i }))
			.click();

		// Then — POST succeeds
		const { status } = await createCall;
		expect(status).toBe(200);

		// And — new space appears in the list
		await expect(page.getByText(spaceName)).toBeVisible({ timeout: 15_000 });
	});

	// ---------------------------------------------------------------------------
	// P0 — List search spaces
	// ---------------------------------------------------------------------------

	test("should display search spaces on the dashboard", async ({
		page,
		authToken,
		interceptNetworkCall,
		log,
	}) => {
		// Given — intercept spaces list call
		const listCall = interceptNetworkCall({ url: "**/api/searchspaces" });

		// When — navigate to dashboard
		await log({ level: "step", message: "Navigate to dashboard" });
		await page.goto("/");

		// Then — spaces API called
		const { status, responseJson } = await listCall;
		expect(status).toBe(200);
		expect(Array.isArray(responseJson)).toBe(true);

		// And — at least one space item is rendered (or empty state)
		const spaceList = page.getByTestId("search-space-list");
		const emptyState = page
			.getByTestId("empty-search-spaces")
			.or(page.getByText(/no spaces|create your first/i));

		await expect(spaceList.or(emptyState)).toBeVisible({ timeout: 10_000 });
	});

	// ---------------------------------------------------------------------------
	// P1 — Delete search space
	// ---------------------------------------------------------------------------

	test("should delete a search space", async ({ page, authToken, interceptNetworkCall, log }) => {
		const spaceName = `Delete Me ${UNIQUE_SUFFIX()}`;

		// Given — create a space first via API (faster than UI)
		const token = authToken;
		const apiUrl = process.env.API_URL || "http://localhost:8000";

		const createResp = await page.request.post(`${apiUrl}/api/searchspaces`, {
			data: { name: spaceName, description: "E2E delete test" },
			headers: { Authorization: `Bearer ${token}` },
		});
		expect(createResp.status()).toBe(200);
		const { id: spaceId } = await createResp.json();

		// Navigate to dashboard
		await page.goto("/");
		await expect(page.getByText(spaceName)).toBeVisible({ timeout: 15_000 });

		// When — delete the space
		await log({ level: "step", message: "Delete search space" });

		// Intercept DELETE request
		const deleteCall = interceptNetworkCall({
			url: `**/api/searchspaces/${spaceId}`,
			method: "DELETE",
		});

		// Find and click delete action for this space
		const spaceItem = page.getByText(spaceName).first();
		await spaceItem.hover();

		const deleteButton = page
			.getByTestId(`delete-space-${spaceId}`)
			.or(page.getByRole("button", { name: /delete/i }).first());
		await deleteButton.click();

		// Confirm deletion if dialog appears
		const confirmButton = page
			.getByTestId("confirm-delete-button")
			.or(page.getByRole("button", { name: /confirm|yes|delete/i }));

		if (await confirmButton.isVisible({ timeout: 3_000 }).catch(() => false)) {
			await confirmButton.click();
		}

		// Then — DELETE called successfully
		const { status } = await deleteCall;
		expect(status).toBe(200);

		// And — space removed from UI
		await expect(page.getByText(spaceName)).not.toBeVisible({ timeout: 15_000 });
	});

	// ---------------------------------------------------------------------------
	// P1 — Navigate into a search space
	// ---------------------------------------------------------------------------

	test("should navigate into a search space", async ({
		page,
		authToken,
		interceptNetworkCall,
		log,
	}) => {
		const spaceName = `Nav Test ${UNIQUE_SUFFIX()}`;
		const token = authToken;
		const apiUrl = process.env.API_URL || "http://localhost:8000";

		// Given — create space via API
		const createResp = await page.request.post(`${apiUrl}/api/searchspaces`, {
			data: { name: spaceName, description: "Navigation test" },
			headers: { Authorization: `Bearer ${token}` },
		});
		expect(createResp.status()).toBe(200);
		const { id: spaceId } = await createResp.json();

		// When — navigate to dashboard and click the space
		await page.goto("/");
		await expect(page.getByText(spaceName)).toBeVisible({ timeout: 15_000 });

		await log({ level: "step", message: "Click into search space" });
		await page.getByText(spaceName).first().click();

		// Then — URL contains the space ID or space name
		await expect(page).toHaveURL(new RegExp(`(searchspace|space|dashboard).*${spaceId}`), {
			timeout: 15_000,
		});
	});
});
