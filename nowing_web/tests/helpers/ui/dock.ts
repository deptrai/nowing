import type { Page } from "@playwright/test";

/**
 * The contextual right dock starts closed (dockOpenAtom defaults to false) and
 * shows a FloatingReopenPill ("Open canvas") until the user opens it. Specs that
 * assert dock content (lead matrix, mission control, resizer) must open it first.
 */
export async function openContextualDock(page: Page): Promise<void> {
	// i18n: en renders "Open canvas", vi renders "Mở canvas".
	const pill = page.getByRole("button", { name: /open canvas|mở canvas/i });
	// The pill mounts asynchronously after React hydration — isVisible() alone
	// races and silently skips the click when the pill is not mounted yet.
	const visible = await pill
		.waitFor({ state: "visible", timeout: 5000 })
		.then(() => true)
		.catch(() => false);
	if (visible) {
		await pill.click();
	}
}
