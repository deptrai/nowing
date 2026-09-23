import assert from "node:assert/strict";

/**
 * Story 26.28: Source Coverage Badge & Status Panel Logic Test
 * Run: pnpm exec tsx tests/leads/source-status-panel.test.ts
 */

import {
	COVERAGE_BADGE_VARIANTS,
	formatCoveragePercentage,
	getCoverageQualityTier,
} from "../../components/leads/SourceCoverageBadge";

function testCoverageTierMapping() {
	// AC-1: score >= 0.9 -> high
	assert.equal(getCoverageQualityTier(1.0), "high");
	assert.equal(getCoverageQualityTier(0.9), "high");
	assert.equal(getCoverageQualityTier(0.899), "medium");

	// AC-1: 0.6 <= score < 0.9 -> medium
	assert.equal(getCoverageQualityTier(0.75), "medium");
	assert.equal(getCoverageQualityTier(0.6), "medium");
	assert.equal(getCoverageQualityTier(0.599), "low");

	// AC-1: 0.3 <= score < 0.6 -> low
	assert.equal(getCoverageQualityTier(0.45), "low");
	assert.equal(getCoverageQualityTier(0.3), "low");
	assert.equal(getCoverageQualityTier(0.299), "none");

	// AC-1: score < 0.3 -> none
	assert.equal(getCoverageQualityTier(0.15), "none");
	assert.equal(getCoverageQualityTier(0.0), "none");
	assert.equal(getCoverageQualityTier(null), "none");
}

function testCoverageBadgeColors() {
	assert.ok(COVERAGE_BADGE_VARIANTS.high.class.includes("emerald"));
	assert.ok(COVERAGE_BADGE_VARIANTS.medium.class.includes("sky"));
	assert.ok(COVERAGE_BADGE_VARIANTS.low.class.includes("amber"));
	assert.ok(COVERAGE_BADGE_VARIANTS.none.class.includes("rose"));

	assert.equal(COVERAGE_BADGE_VARIANTS.high.label, "High Coverage");
	assert.equal(COVERAGE_BADGE_VARIANTS.medium.label, "Medium Coverage");
	assert.equal(COVERAGE_BADGE_VARIANTS.low.label, "Low Coverage");
	assert.equal(COVERAGE_BADGE_VARIANTS.none.label, "No Coverage");
}

function testCoveragePercentageFormatting() {
	assert.equal(formatCoveragePercentage(1.0), "Độ phủ: 100%");
	assert.equal(formatCoveragePercentage(0.85), "Độ phủ: 85%");
	assert.equal(formatCoveragePercentage(0.6), "Độ phủ: 60%");
	assert.equal(formatCoveragePercentage(0.0), "Độ phủ: 0%");
	assert.equal(formatCoveragePercentage(null), "Độ phủ: 0%");
}

function testMinimumActiveSourceGuard() {
	const handleToggleSource = (
		sourceName: string,
		currentSources: string[]
	): { allowed: boolean; newSources: string[]; warning?: string } => {
		const isCurrentlyActive = currentSources.includes(sourceName);
		if (isCurrentlyActive) {
			if (currentSources.length <= 1) {
				return {
					allowed: false,
					newSources: currentSources,
					warning: "Phải giữ lại ít nhất 1 nguồn thu thập",
				};
			}
			return {
				allowed: true,
				newSources: currentSources.filter((s) => s !== sourceName),
			};
		}
		return {
			allowed: true,
			newSources: [...currentSources, sourceName],
		};
	};

	// Disabling when only 1 active is BLOCKED
	const resBlocked = handleToggleSource("batdongsan", ["batdongsan"]);
	assert.equal(resBlocked.allowed, false);
	assert.equal(resBlocked.newSources.length, 1);
	assert.ok(resBlocked.warning?.includes("ít nhất 1 nguồn"));

	// Disabling when 2 active is ALLOWED
	const resAllowed = handleToggleSource("batdongsan", ["batdongsan", "chotot"]);
	assert.equal(resAllowed.allowed, true);
	assert.deepEqual(resAllowed.newSources, ["chotot"]);

	// Enabling a new source is always ALLOWED
	const resAdd = handleToggleSource("vn_jobs", ["chotot"]);
	assert.equal(resAdd.allowed, true);
	assert.deepEqual(resAdd.newSources, ["chotot", "vn_jobs"]);
}

function testBadgeTierResolutionWithoutQuality() {
	// When quality is omitted, score resolves correctly
	const resolveTier = (quality?: string, score?: number | null) => {
		return quality && quality in COVERAGE_BADGE_VARIANTS ? quality : getCoverageQualityTier(score);
	};

	assert.equal(resolveTier(undefined, 0.95), "high");
	assert.equal(resolveTier(undefined, 0.7), "medium");
	assert.equal(resolveTier(undefined, 0.4), "low");
	assert.equal(resolveTier(undefined, 0.1), "none");
	// When explicit quality is given, it takes precedence
	assert.equal(resolveTier("medium", 0.95), "medium");
}

testCoverageTierMapping();
testCoverageBadgeColors();
testCoveragePercentageFormatting();
testMinimumActiveSourceGuard();
testBadgeTierResolutionWithoutQuality();
console.log("All source-status-panel tests passed!");
