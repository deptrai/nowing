import assert from "node:assert/strict";
import { test } from "node:test";

interface ServiceBreakdownItem {
	category: string;
	total_tokens: number;
	cost_micros: number;
	event_count: number;
}

// ---------------------------------------------------------------------------
// 1. Service Breakdown Percentage and Color Palette Resolution
// ---------------------------------------------------------------------------
const SERVICE_COLORS: Record<string, string> = {
	"AI Generation": "hsl(var(--chart-1, 217 91% 60%))",
	"Web Search": "hsl(var(--chart-2, 142 76% 36%))",
	"Social Media": "hsl(var(--chart-3, 262 83% 58%))",
	"Phone Waterfall": "hsl(var(--chart-4, 31 97% 54%))",
	"Outcome Meetings": "hsl(var(--chart-5, 340 75% 55%))",
};

function calculateServicePercentages(
	items: ServiceBreakdownItem[]
): Array<ServiceBreakdownItem & { percentage: number; color: string }> {
	const totalCost = items.reduce((sum, item) => sum + item.cost_micros, 0);

	return items.map((item) => ({
		...item,
		percentage: totalCost > 0 ? Math.round((item.cost_micros / totalCost) * 100) : 0,
		color: SERVICE_COLORS[item.category] || "hsl(var(--muted))",
	}));
}

test("calculateServicePercentages computes accurate proportions", () => {
	const items: ServiceBreakdownItem[] = [
		{ category: "Outcome Meetings", total_tokens: 0, cost_micros: 2_000_000, event_count: 1 },
		{ category: "Phone Waterfall", total_tokens: 0, cost_micros: 600_000, event_count: 10 },
		{ category: "Social Media", total_tokens: 0, cost_micros: 400_000, event_count: 20 },
		{ category: "AI Generation", total_tokens: 50_000, cost_micros: 0, event_count: 15 },
	];

	const calculated = calculateServicePercentages(items);
	assert.equal(calculated.length, 4);

	// Total cost = 3,000,000 micros
	const meetings = calculated.find((i) => i.category === "Outcome Meetings");
	assert.equal(meetings?.percentage, 67); // 2,000,000 / 3,000,000 = ~66.7% -> 67%

	const phone = calculated.find((i) => i.category === "Phone Waterfall");
	assert.equal(phone?.percentage, 20); // 600,000 / 3,000,000 = 20%

	const ai = calculated.find((i) => i.category === "AI Generation");
	assert.equal(ai?.percentage, 0); // $0 chat policy
});
