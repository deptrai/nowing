import { defineConfig, devices } from "@playwright/test";

/**
 * Environment profile presets for E2E testing:
 *   - local: Runs against local dev/Docker stack with Next.js webServer auto-started.
 *   - staging: Targets pre-production / staging environment (no local webServer).
 *   - production: Targets production environment (no local webServer).
 *
 * Switch modes via `PLAYWRIGHT_ENV=staging pnpm test:e2e` or use dedicated scripts.
 * Direct environment variables (PLAYWRIGHT_BASE_URL, etc.) always take precedence.
 */
type TargetEnvironment = "local" | "staging" | "production";
const targetEnv = (process.env.PLAYWRIGHT_ENV || "local").toLowerCase() as TargetEnvironment;

interface EnvPreset {
	baseURL: string;
	backendURL: string;
	zeroCacheURL: string;
	noWebServer: boolean;
	authType: string;
}

const PRESETS: Record<TargetEnvironment, EnvPreset> = {
	local: {
		baseURL: `http://localhost:${process.env.PORT || "3000"}`,
		backendURL: `http://localhost:${process.env.BACKEND_PORT || "8000"}`,
		zeroCacheURL: `http://localhost:${process.env.ZERO_CACHE_PORT || "4848"}`,
		noWebServer: false,
		authType: "LOCAL",
	},
	staging: {
		baseURL: "https://staging.nowing.net",
		backendURL: "https://api-staging.nowing.net",
		zeroCacheURL: "https://zero-staging.nowing.net",
		noWebServer: true,
		authType: "LOCAL",
	},
	production: {
		baseURL: "https://nowing.net",
		backendURL: "https://api.nowing.net",
		zeroCacheURL: "https://zero.nowing.net",
		noWebServer: true,
		authType: "LOCAL",
	},
};

const activePreset = PRESETS[targetEnv] || PRESETS.local;

const PORT = process.env.PORT || "3000";
const baseURL = process.env.PLAYWRIGHT_BASE_URL || activePreset.baseURL;
const useProxyOrigin = process.env.PLAYWRIGHT_USE_PROXY_ORIGIN === "true";
const backendURL =
	process.env.NEXT_PUBLIC_FASTAPI_BACKEND_URL ||
	(useProxyOrigin ? baseURL : activePreset.backendURL);
const zeroCacheURL =
	process.env.NEXT_PUBLIC_ZERO_CACHE_URL ||
	(useProxyOrigin ? `${baseURL}/zero` : activePreset.zeroCacheURL);

const workersEnv = process.env.PLAYWRIGHT_WORKERS
	? parseInt(process.env.PLAYWRIGHT_WORKERS, 10)
	: null;
const workersValue = workersEnv && workersEnv > 0 ? workersEnv : process.env.CI ? 2 : 1;

process.env.PLAYWRIGHT_ENV = targetEnv;
process.env.PLAYWRIGHT_BASE_URL = baseURL;
process.env.PLAYWRIGHT_TEST_EMAIL ??= "e2e-test@nowing.net";
process.env.PLAYWRIGHT_TEST_PASSWORD ??= "E2eTestPassword123!";
process.env.NEXT_PUBLIC_FASTAPI_BACKEND_URL = backendURL;
process.env.NOWING_BACKEND_INTERNAL_URL = backendURL;
process.env.AUTH_TYPE = process.env.AUTH_TYPE || activePreset.authType;
process.env.NEXT_PUBLIC_ZERO_CACHE_URL = zeroCacheURL;

/**
 * Playwright configuration for Nowing web E2E tests.
 *
 * Tests live under `tests/` and are NEVER bundled into the production Next.js
 * build (`.next/standalone/`) or the Electron desktop build, because:
 *   - This file and `tests/` are listed in `.dockerignore`.
 *   - `electron-builder.yml` only ships `.next/standalone/`, not source files.
 *   - `@playwright/test` is a `devDependency`, so production `pnpm install`
 *     with `--prod` skips it entirely.
 *
 * @see https://playwright.dev/docs/test-configuration
 */
export default defineConfig({
	testDir: "./tests",
	timeout: process.env.CI ? 60_000 : 120_000,
	expect: { timeout: 15_000 },
	fullyParallel: true,
	forbidOnly: !!process.env.CI,
	retries: process.env.CI ? 1 : 0,
	workers: workersValue,
	reporter: process.env.CI
		? [
				["html", { open: "never" }],
				["junit", { outputFile: "playwright-report/junit.xml" }],
				["github"],
				["list"],
			]
		: [
				["html", { open: "on-failure" }],
				["junit", { outputFile: "playwright-report/junit.xml" }],
				["list"],
			],
	use: {
		baseURL,
		actionTimeout: process.env.CI ? 15_000 : 60_000,
		navigationTimeout: process.env.CI ? 30_000 : 90_000,
		trace: "retain-on-failure",
		screenshot: "only-on-failure",
		video: "off",
		extraHTTPHeaders: {
			"x-playwright-test": "true",
		},
	},
	projects: [
		{
			name: "setup",
			testMatch: /.*\.setup\.ts/,
			use: { channel: "chrome" },
		},
		{
			name: "chromium",
			dependencies: ["setup"],
			use: {
				...devices["Desktop Chrome"],
				channel: "chrome",
				storageState: "playwright/.auth/user.json",
			},
		},
		// Unauthenticated public surface for remote environments
		// (staging/production) where no e2e user credentials exist:
		//   PLAYWRIGHT_ENV=production pnpm exec playwright test --project=production-public
		{
			name: "production-public",
			testMatch: [/.*login-page\.spec\.ts/],
			use: {
				...devices["Desktop Chrome"],
				channel: "chrome",
				storageState: { cookies: [], origins: [] },
			},
		},
	],
	webServer:
		process.env.PLAYWRIGHT_NO_WEB_SERVER === "true" ||
		process.env.PLAYWRIGHT_NO_WEB_SERVER === "1" ||
		activePreset.noWebServer
			? undefined
			: {
				// Local stays on webpack dev (Turbopack caused stale-lock panics in E2E).
				command: process.env.CI ? "pnpm build && pnpm start" : "pnpm exec next dev",
				url: `http://localhost:${PORT}`,
				reuseExistingServer: !process.env.CI,
				timeout: process.env.CI ? 300_000 : 180_000,
				stdout: "pipe",
				stderr: "pipe",
				env: {
					NEXT_PUBLIC_FASTAPI_BACKEND_URL: process.env.NEXT_PUBLIC_FASTAPI_BACKEND_URL,
					NOWING_BACKEND_INTERNAL_URL: process.env.NOWING_BACKEND_INTERNAL_URL,
					AUTH_TYPE: process.env.AUTH_TYPE,
					NEXT_PUBLIC_ZERO_CACHE_URL: process.env.NEXT_PUBLIC_ZERO_CACHE_URL,
				},
			},
});
