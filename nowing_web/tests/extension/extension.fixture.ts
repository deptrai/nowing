import path from "node:path";
import { type BrowserContext, chromium, test as base } from "@playwright/test";

export type ExtensionFixtures = {
	context: BrowserContext;
	extensionId: string;
};

const pathToExtension = path.resolve(__dirname, "../../../apps/chrome-extension/dist");

export const test = base.extend<ExtensionFixtures>({
	context: async ({}, use) => {
		const context = await chromium.launchPersistentContext("", {
			headless: true,
			channel: "chromium",
			args: [
				`--disable-extensions-except=${pathToExtension}`,
				`--load-extension=${pathToExtension}`,
				"--no-sandbox",
				"--disable-setuid-sandbox",
			],
		});
		await use(context);
		await context.close();
	},
	extensionId: async ({ context }, use) => {
		let [background] = context.serviceWorkers();
		if (!background) {
			background = await context.waitForEvent("serviceworker", { timeout: 15_000 });
		}
		const extensionId = background.url().split("/")[2];
		await use(extensionId);
	},
});

export { expect } from "@playwright/test";
