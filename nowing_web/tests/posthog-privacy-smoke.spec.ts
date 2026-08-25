import { expect, test } from "@playwright/test";

test.setTimeout(120_000);

test.describe("PostHog privacy smoke", () => {
	test("dashboard loads without PostHog-related console errors", async ({ page }) => {
		const errors: string[] = [];
		page.on("console", (msg) => {
			if (msg.type() === "error") {
				errors.push(msg.text());
			}
		});

		await page.goto("/dashboard", { waitUntil: "domcontentloaded", timeout: 60_000 });
		await expect(page.locator("body")).toContainText(/Nowing|workspace/i, { timeout: 30_000 });

		// Ad-block or missing key should not break the page.
		const posthogErrors = errors.filter(
			(e) => e.toLowerCase().includes("posthog") || e.toLowerCase().includes("analytics")
		);
		expect(posthogErrors, "No PostHog errors in console").toEqual([]);
	});
});
