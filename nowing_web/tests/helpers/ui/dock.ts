import type { Page } from "@playwright/test";

/**
 * The contextual right dock starts closed (dockOpenAtom defaults to false) and
 * shows a FloatingReopenPill ("Open canvas") until the user opens it. Specs that
 * assert dock content (lead matrix, mission control, resizer) must open it first.
 */
export async function openContextualDock(page: Page): Promise<void> {
	const pill = page.getByRole("button", { name: /open canvas/i });
	if (await pill.isVisible()) {
		await pill.click();
	}
}
