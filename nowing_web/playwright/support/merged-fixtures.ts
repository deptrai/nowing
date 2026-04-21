import { mergeTests } from "@playwright/test";
import { test as apiRequestFixture } from "@seontechnologies/playwright-utils/api-request/fixtures";
import { test as authFixture } from "@seontechnologies/playwright-utils/auth-session/fixtures";
import { test as interceptFixture } from "@seontechnologies/playwright-utils/intercept-network-call/fixtures";
import { test as recurseFixture } from "@seontechnologies/playwright-utils/recurse/fixtures";
import { test as logFixture } from "@seontechnologies/playwright-utils/log/fixtures";
import { test as networkErrorMonitorFixture } from "@seontechnologies/playwright-utils/network-error-monitor/fixtures";
import { test as customFixtures } from "./custom-fixtures";

/**
 * Merged test fixture — single import for all E2E tests.
 *
 * Available fixtures:
 *   apiRequest          — typed HTTP client with retry + schema validation
 *   authToken           — JWT token for the current test user (persisted to disk)
 *   interceptNetworkCall — spy/stub network calls
 *   recurse             — polling for async operations
 *   log                 — report-integrated logging
 *   networkErrorMonitor — auto 4xx/5xx detection
 *   testUser            — (custom) seeded test user
 */
export const test = mergeTests(
	apiRequestFixture,
	authFixture,
	interceptFixture,
	recurseFixture,
	logFixture,
	networkErrorMonitorFixture,
	customFixtures
);

export { expect } from "@playwright/test";
