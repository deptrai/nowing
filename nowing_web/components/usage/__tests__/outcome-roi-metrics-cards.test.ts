import assert from "node:assert/strict";
import { test } from "node:test";

interface RoiMetricsInput {
	meetingsBookedCount: number;
	totalMeetingsCostMicros: number;
	avgDealValueUsd: number;
	closeRatePercent: number;
}

interface RoiMetricsOutput {
	costPerMeetingUsd: number;
	estimatedPipelineValueUsd: number;
	estimatedClosedWonUsd: number;
	roiMultiplier: number;
}

function calculateRoiMetrics(input: RoiMetricsInput): RoiMetricsOutput {
	const costPerMeetingUsd =
		input.meetingsBookedCount > 0
			? input.totalMeetingsCostMicros / (input.meetingsBookedCount * 1_000_000)
			: 0;

	const estimatedPipelineValueUsd = input.meetingsBookedCount * input.avgDealValueUsd;
	const estimatedClosedWonUsd =
		estimatedPipelineValueUsd * (input.closeRatePercent / 100);

	const totalSpentUsd = input.totalMeetingsCostMicros / 1_000_000;
	const roiMultiplier =
		totalSpentUsd > 0
			? Number((estimatedClosedWonUsd / totalSpentUsd).toFixed(1))
			: 0;

	return {
		costPerMeetingUsd,
		estimatedPipelineValueUsd,
		estimatedClosedWonUsd,
		roiMultiplier,
	};
}

test("calculateRoiMetrics calculates cost per meeting and pipeline value ROI", () => {
	const metrics = calculateRoiMetrics({
		meetingsBookedCount: 5,
		totalMeetingsCostMicros: 10_000_000, // 5 meetings * $2 = $10.00
		avgDealValueUsd: 500, // $500 avg deal
		closeRatePercent: 20, // 20% win rate -> 1 deal won = $500
	});

	assert.equal(metrics.costPerMeetingUsd, 2.0);
	assert.equal(metrics.estimatedPipelineValueUsd, 2500);
	assert.equal(metrics.estimatedClosedWonUsd, 500);
	assert.equal(metrics.roiMultiplier, 50.0); // $500 / $10 = 50x ROI
});
