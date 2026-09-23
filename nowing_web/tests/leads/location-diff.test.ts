/**
 * Unit tests for computeLocationDiff (Story 26.29).
 * Run: pnpm exec tsx tests/leads/location-diff.test.ts
 */

import assert from "node:assert/strict";

import { computeLocationDiff, type LocationDiffResult } from "../../lib/geo/vietnam-divisions";

function testProvinceChange() {
	const prev = { province_code: "HN", district_codes: ["001"], ward_names: ["Phúc Xá"] };
	const next = { province_code: "SG", district_codes: ["760"], ward_names: [] };
	const diff = computeLocationDiff(prev, next);

	assert.equal(diff.provinceChanged, true);
	assert.equal(diff.prevProvinceName, "Hà Nội");
	assert.equal(diff.nextProvinceName, "TP. Hồ Chí Minh");
	assert.deepEqual(diff.addedDistricts, []);
	assert.deepEqual(diff.removedDistricts, []);
}

function testDistrictAddRemove() {
	const prev = { province_code: "HN", district_codes: ["001"], ward_names: [] };
	const next = { province_code: "HN", district_codes: ["001", "005"], ward_names: [] };
	const diff = computeLocationDiff(prev, next);

	assert.equal(diff.provinceChanged, false);
	assert.equal(diff.addedDistricts.length, 1);
	assert.equal(diff.addedDistricts[0].code, "005");
	assert.equal(diff.addedDistricts[0].name, "Cầu Giấy");
	assert.equal(diff.removedDistricts.length, 0);

	const removed = computeLocationDiff(next, prev);
	assert.equal(removed.removedDistricts.length, 1);
	assert.equal(removed.removedDistricts[0].code, "005");
}

function testWardAddRemove() {
	const prev = { province_code: "HN", district_codes: ["001"], ward_names: ["Phúc Xá"] };
	const next = { province_code: "HN", district_codes: ["001"], ward_names: ["Phúc Xá", "Trúc Bạch"] };
	const diff = computeLocationDiff(prev, next);

	assert.deepEqual(diff.addedWards, ["Trúc Bạch"]);
	assert.deepEqual(diff.removedWards, []);
}

testProvinceChange();
testDistrictAddRemove();
testWardAddRemove();
console.log("All location-diff tests passed!");
