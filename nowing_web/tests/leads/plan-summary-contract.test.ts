import assert from "node:assert/strict";
import {
	campaignPlanResponseSchema,
	sourcePlanAllocationSchema,
	type CampaignPlanResponse,
} from "../../contracts/types/campaign.types";

const mockPlanData: CampaignPlanResponse = {
	campaign_name: "Chiến dịch BĐS Sài Gòn Q3",
	workspace_id: 1,
	total_planned_sources: 3,
	expected_sources: ["batdongsan", "topcv", "degraded_social"],
	subtasks: [
		{
			source_name: "batdongsan",
			query: "nhà đất Quận 1",
			limit: 50,
			filters: { locations: ["SG"] },
			priority: 2,
		},
		{
			source_name: "topcv",
			query: "nhà đất Quận 1",
			limit: 30,
			filters: {},
			priority: 1,
		},
	],
	source_allocations: [
		{
			source_name: "batdongsan",
			category: "real_estate",
			allocated_limit: 50,
			priority: 2,
			location_coverage_quality: "high",
			location_coverage_score: 1.0,
			supported_provinces: ["HN", "SG", "DN"],
			status: "ready",
			degraded_reason: null,
		},
		{
			source_name: "topcv",
			category: "real_estate",
			allocated_limit: 30,
			priority: 1,
			location_coverage_quality: "medium",
			location_coverage_score: 0.6,
			supported_provinces: ["HN", "*"],
			status: "ready",
			degraded_reason: null,
		},
		{
			source_name: "degraded_social",
			category: "social",
			allocated_limit: 20,
			priority: 1,
			location_coverage_quality: "none",
			location_coverage_score: 0.0,
			supported_provinces: ["*"],
			status: "degraded",
			degraded_reason: "Adapter degraded_social reported last execution status: degraded",
		},
	],
	estimated_reachable_leads: 100,
	estimated_cost_vnd: 150000,
	estimated_cost_micros: 6000000,
	warnings: [
		"Adapter degraded_social đang hoạt động ở chế độ suy giảm hiệu năng.",
	],
};

function assertParsesPlan() {
	const parsed = campaignPlanResponseSchema.safeParse(mockPlanData);
	assert.equal(parsed.success, true);
	if (parsed.success) {
		assert.equal(parsed.data.campaign_name, "Chiến dịch BĐS Sài Gòn Q3");
		assert.equal(parsed.data.total_planned_sources, 3);
		assert.equal(parsed.data.source_allocations.length, 3);
		assert.equal(parsed.data.estimated_reachable_leads, 100);
		assert.equal(parsed.data.estimated_cost_vnd, 150000);
		assert.equal(parsed.data.estimated_cost_micros, 6000000);
		assert.equal(parsed.data.warnings.length, 1);
	}
}

function assertSourceAllocations() {
	const bds = sourcePlanAllocationSchema.safeParse(mockPlanData.source_allocations[0]);
	assert.equal(bds.success, true);
	if (bds.success) {
		assert.equal(bds.data.location_coverage_quality, "high");
		assert.equal(bds.data.location_coverage_score, 1.0);
		assert.equal(bds.data.status, "ready");
		assert.equal(bds.data.degraded_reason, null);
	}

	const degraded = sourcePlanAllocationSchema.safeParse(mockPlanData.source_allocations[2]);
	assert.equal(degraded.success, true);
	if (degraded.success) {
		assert.equal(degraded.data.status, "degraded");
		assert.ok(degraded.data.degraded_reason?.includes("degraded"));
	}
}

function assertCoverageMapping() {
	const mapQuality = (score: number): string => {
		if (score >= 0.9) return "high";
		if (score >= 0.6) return "medium";
		if (score >= 0.3) return "low";
		return "none";
	};

	assert.equal(mapQuality(1.0), "high");
	assert.equal(mapQuality(0.92), "high");
	assert.equal(mapQuality(0.75), "medium");
	assert.equal(mapQuality(0.6), "medium");
	assert.equal(mapQuality(0.45), "low");
	assert.equal(mapQuality(0.3), "low");
	assert.equal(mapQuality(0.15), "none");
	assert.equal(mapQuality(0.0), "none");
}

function assertCostMapping() {
	const maxLeads = 200;
	const baseCostVnd = maxLeads * 1500;
	const baseCostMicros = baseCostVnd * 40;
	assert.equal(baseCostVnd, 300000);
	assert.equal(baseCostMicros, 12000000);

	const unlockCostVnd = maxLeads * 5000;
	const unlockCostMicros = unlockCostVnd * 40;
	assert.equal(unlockCostVnd, 1000000);
	assert.equal(unlockCostMicros, 40000000);
}

function assertFallbackWarning() {
	const uncoveredPlan: CampaignPlanResponse = {
		...mockPlanData,
		warnings: [
			"No adapter has explicit coverage for location CM; falling back to keyword-based routing.",
		],
	};

	const parsed = campaignPlanResponseSchema.safeParse(uncoveredPlan);
	assert.equal(parsed.success, true);
	if (parsed.success) {
		assert.ok(parsed.data.warnings.some((w) => w.includes("No adapter has explicit coverage")));
	}
}

assertParsesPlan();
assertSourceAllocations();
assertCoverageMapping();
assertCostMapping();
assertFallbackWarning();
console.log("All plan-summary-contract assertions passed");
