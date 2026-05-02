import { defineConfig, devices } from "@playwright/test";

/**
 * Playwright E2E Configuration — nowing_web
 * See: https://playwright.dev/docs/test-configuration
 */
export default defineConfig({
	testDir: "./playwright",
	outputDir: "./playwright/test-results",

	// Fail fast in CI, allow retries locally
	fullyParallel: true,
	forbidOnly: !!process.env.CI,
	retries: process.env.CI ? 2 : 0,
	workers: process.env.CI ? Math.max(2, Math.floor(require("os").cpus().length * 0.75)) : undefined,

	// Timeout standards
	timeout: 60_000,
	expect: { timeout: 10_000 },

	use: {
		baseURL: process.env.BASE_URL || "http://localhost:4998",
		actionTimeout: 15_000,
		navigationTimeout: 30_000,

		// Artifacts — retain on failure
		trace: "retain-on-failure",
		screenshot: "only-on-failure",
		video: "retain-on-failure",
	},

	// Reporters
	reporter: process.env.CI
		? [
				["html", { open: "never", outputFolder: "playwright/reports/html" }],
				["junit", { outputFile: "playwright/reports/junit.xml" }],
				["list"],
			]
		: [["html", { open: "on-failure", outputFolder: "playwright/reports/html" }], ["list"]],

	// Browser projects
	projects: [
		// API Tests (No browser needed)
		{
			name: "api",
			testMatch: "api/**/*.spec.ts",
			use: {
				baseURL: process.env.API_URL || "http://localhost:8000",
				storageState: "playwright/auth-sessions/local/default/storage-state.json",
			},
			dependencies: ["setup"],
		},

		// Setup project (global auth)
		{ name: "setup", testMatch: "**/global-setup.ts" },

		{
			name: "chromium",
			testMatch: "e2e/**/*.spec.ts",
			use: {
				...devices["Desktop Chrome"],
				storageState: "playwright/auth-sessions/local/default/storage-state.json",
			},
			dependencies: ["setup"],
		},

		// Add more browsers as needed:
		// { name: 'firefox', use: { ...devices['Desktop Firefox'] }, dependencies: ['setup'] },
		// { name: 'webkit', use: { ...devices['Desktop Safari'] }, dependencies: ['setup'] },
	],

	// Local dev server (optional — comment out if running separately)
	// webServer: {
	//   command: 'pnpm dev',
	//   url: 'http://localhost:3999',
	//   reuseExistingServer: !process.env.CI,
	// },
});
