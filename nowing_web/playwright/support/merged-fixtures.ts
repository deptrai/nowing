import { mergeTests } from "@playwright/test";
import { test as logFixture } from "@seontechnologies/playwright-utils/log/fixtures";
import { test as networkErrorMonitorFixture } from "@seontechnologies/playwright-utils/network-error-monitor/fixtures";
import { test as recurseFixture } from "@seontechnologies/playwright-utils/recurse/fixtures";
import { test as customFixtures } from "./custom-fixtures";

export const test = mergeTests(
	customFixtures,
	recurseFixture,
	logFixture,
	networkErrorMonitorFixture
);

export { expect } from "@playwright/test";
