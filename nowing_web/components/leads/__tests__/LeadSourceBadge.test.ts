import assert from "node:assert/strict";
import { test } from "node:test";
import { resolveSourceConfig } from "../LeadSourceBadge";

test("LeadSourceBadge: websets maps to correct label, class, and fallback tooltip (Story 41.2)", () => {
	const config = resolveSourceConfig("websets");
	assert.equal(config.key, "websets");
	assert.equal(config.label, "Websets");
	assert.equal(
		config.className,
		"bg-emerald-50 text-emerald-700 border-emerald-200 dark:bg-emerald-950/40 dark:text-emerald-300 dark:border-emerald-800"
	);
	assert.equal(config.fallbackTooltip, "ChainLens Websets (Trích xuất từ web)");
});

test("LeadSourceBadge: websets substring matching works for variants", () => {
	const config = resolveSourceConfig("webset_crawler");
	assert.equal(config.key, "websets");
	assert.equal(config.label, "Websets");
});

test("LeadSourceBadge: standard sources resolve correctly", () => {
	assert.equal(resolveSourceConfig("facebook_group").key, "facebook");
	assert.equal(resolveSourceConfig("telegram_channel").key, "telegram");
	assert.equal(resolveSourceConfig("batdongsan_listing").key, "batdongsan");
	assert.equal(resolveSourceConfig("topcv_jobs").key, "topcv");
	assert.equal(resolveSourceConfig("muasamcong_tender").key, "tender");
	assert.equal(resolveSourceConfig("unknown_source").key, "other");
});
