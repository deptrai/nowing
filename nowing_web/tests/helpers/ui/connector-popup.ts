import type { Page } from "@playwright/test";
import { expect } from "@playwright/test";

/**
 * Page-object-style helpers for the connector dialog rendered by
 * components/assistant-ui/connector-popup.tsx.
 *
 * Kept minimal in Phase 1: most spec interactions go through API
 * fixtures for determinism. UI-driven coverage of every connector card
 * is a Phase 2 task and will use this helper as the entry point.
 */

// Composer "+" overflow menu (tooltip/aria-label from chat.composer_menu_tooltip).
const PLUS_MENU_LABEL = "Upload files, manage tools and more";
// Radix sub-content carries this data-slot (components/ui/dropdown-menu.tsx).
const SUBMENU_CONTENT = '[data-slot="dropdown-menu-sub-content"]';

/**
 * Opens the composer "+" menu and hovers the "MCP Connectors" sub-trigger so
 * the submenu listing connected connector groups is visible.
 */
async function openConnectorsSubmenu(page: Page) {
	const plus = page.getByRole("button", { name: PLUS_MENU_LABEL });
	// Long timeout absorbs Next.js dev cold-compile of the new-chat route.
	await expect(plus).toBeVisible({ timeout: 60_000 });
	await plus.click();
	await page.getByRole("menuitem", { name: "MCP Connectors" }).hover();
	const subContent = page.locator(SUBMENU_CONTENT);
	await expect(subContent).toBeVisible();
	return subContent;
}

export async function openConnectorPopup(page: Page): Promise<void> {
	// Empty-state entry point: the "Connect your tools" banner under the
	// composer only renders while the workspace has no connectors.
	const banner = page.getByRole("button", { name: "Connect your tools" });
	if (await banner.isVisible().catch(() => false)) {
		await banner.click();
		await expect(page.getByRole("dialog", { name: "MCP Connectors" })).toBeVisible();
		return;
	}

	// Connected-workspace entry point: "+" menu → MCP Connectors submenu → the
	// first connected connector group opens the dialog on its edit view, then
	// "Back to connectors" lands on the catalog (tabs + Search input).
	// Callers always create at least one connector via API fixture first.
	const subContent = await openConnectorsSubmenu(page);
	await subContent.getByRole("menuitem").first().click();

	const dialog = page.getByRole("dialog", { name: "MCP Connectors" });
	await expect(dialog).toBeVisible();
	await dialog.getByRole("button", { name: "Back to connectors" }).click();
	await expect(dialog.getByPlaceholder("Search")).toBeVisible();
}

/**
 * Asserts a connected connector group is offered in the composer's
 * "+" → "MCP Connectors" submenu (e.g. "Google Drive", "OneDrive", "Dropbox").
 * Replaces the removed Documents-sidebar import menu.
 */
export async function expectImportConnectorAvailable(page: Page, label: string): Promise<void> {
	const subContent = await openConnectorsSubmenu(page);
	await expect(subContent.getByRole("menuitem", { name: label })).toBeVisible();
	await page.keyboard.press("Escape");
}
