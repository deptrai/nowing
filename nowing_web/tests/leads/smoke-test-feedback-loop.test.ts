import assert from "node:assert/strict";

/**
 * Story 26.29: Smoke Test Feedback Loop logic test
 * Run: pnpm exec tsx tests/leads/smoke-test-feedback-loop.test.ts
 */

import {
	computeLocationDiff,
	type LocationDiffResult,
} from "../../lib/geo/vietnam-divisions";

function testSmokeTestDiffSummary() {
	const prev = { province_code: "HN", district_codes: ["001"], ward_names: [] };
	const next = { province_code: "HN", district_codes: ["001", "005"], ward_names: ["Dịch Vọng"] };
	const diff: LocationDiffResult = computeLocationDiff(prev, next);

	assert.equal(diff.provinceChanged, false);
	assert.equal(diff.addedDistricts.length, 1);
	assert.equal(diff.addedDistricts[0].name, "Cầu Giấy");
	assert.deepEqual(diff.addedWards, ["Dịch Vọng"]);
}

function testProvinceSwitchDiff() {
	const prev = { province_code: "HN", district_codes: ["001"], ward_names: [] };
	const next = { province_code: "SG", district_codes: ["760"], ward_names: [] };
	const diff: LocationDiffResult = computeLocationDiff(prev, next);

	assert.equal(diff.provinceChanged, true);
	assert.equal(diff.prevProvinceName, "Hà Nội");
	assert.equal(diff.nextProvinceName, "TP. Hồ Chí Minh");
}

function testWardRemove() {
	const prev = { province_code: "HN", district_codes: ["001"], ward_names: ["Phúc Xá", "Trúc Bạch"] };
	const next = { province_code: "HN", district_codes: ["001"], ward_names: ["Phúc Xá"] };
	const diff: LocationDiffResult = computeLocationDiff(prev, next);

	assert.deepEqual(diff.removedWards, ["Trúc Bạch"]);
	assert.equal(diff.addedWards.length, 0);
}

testSmokeTestDiffSummary();
testProvinceSwitchDiff();
testWardRemove();
console.log("All smoke-test-feedback-loop tests passed!");
