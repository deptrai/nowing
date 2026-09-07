import type { Locator } from "@playwright/test";

/**
 * Safely click a Playwright locator that may be outside the current
 * viewport. Scrolls the element into view first, then clicks.
 *
 * This is the Epic 26 retrospective action item for avoiding E2E
 * failures caused by tall modals or multi-step forms where the target
 * button is rendered below the fold.
 */
export async function safeClick(
	locator: Locator,
	options?: {
		delay?: number;
		force?: boolean;
		noWaitAfter?: boolean;
		timeout?: number;
		position?: { x: number; y: number };
	}
): Promise<void> {
	// Scroll the element into the center of the viewport before clicking.
	// This is more reliable than the default "nearest" behavior for tall
	// modals where the top or bottom of the element may still be occluded.
	await locator.evaluate((el) =>
		el.scrollIntoView({ block: "center", inline: "center", behavior: "instant" })
	);
	await locator.scrollIntoViewIfNeeded({ timeout: options?.timeout ?? 5000 });

	try {
		await locator.click({
			delay: options?.delay,
			force: options?.force,
			noWaitAfter: options?.noWaitAfter,
			timeout: options?.timeout,
			position: options?.position,
		});
	} catch (error) {
		// Fall back to a native DOM click when Playwright's pointer action
		// is intercepted by a modal/dialog root element.
		await locator.evaluate((el) => el.click());
	}
}
