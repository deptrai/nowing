/**
 * Unit tests — components/new-chat/report/embedded-charts/chart-spec.ts
 * Covers: parseChartSpec (line/pie/bar/area/candle parsing, edge cases)
 */
import { describe, it, expect } from "vitest";
import { parseChartSpec } from "@/components/new-chat/report/embedded-charts/chart-spec";

describe("parseChartSpec", () => {
	// ---------------------------------------------------------------------------
	// Happy path — inline JSON data
	// ---------------------------------------------------------------------------

	it("parses a line chart with inline JSON data", () => {
		const spec = `type: line
title: Price History
xKey: date
yKey: price
data: [{"date":"2026-01","price":100},{"date":"2026-02","price":120}]`;
		const result = parseChartSpec(spec);
		expect(result).not.toBeNull();
		expect(result!.type).toBe("line");
		expect(result!.title).toBe("Price History");
		expect(result!.xKey).toBe("date");
		expect(result!.yKey).toBe("price");
		expect(result!.data).toHaveLength(2);
	});

	it("parses a pie chart", () => {
		const spec = `type: pie
nameKey: name
valueKey: value
data: [{"name":"BTC","value":60},{"name":"ETH","value":40}]`;
		const result = parseChartSpec(spec);
		expect(result).not.toBeNull();
		expect(result!.type).toBe("pie");
		expect(result!.nameKey).toBe("name");
	});

	it("parses a bar chart", () => {
		const spec = `type: bar
data: [{"label":"A","val":10}]`;
		const result = parseChartSpec(spec);
		expect(result).not.toBeNull();
		expect(result!.type).toBe("bar");
	});

	it("parses an area chart", () => {
		const spec = `type: area
data: [{"x":1,"y":2}]`;
		const result = parseChartSpec(spec);
		expect(result).not.toBeNull();
		expect(result!.type).toBe("area");
	});

	it("parses a candle chart", () => {
		const spec = `type: candle
data: [{"open":1,"high":2,"low":0.5,"close":1.5}]`;
		const result = parseChartSpec(spec);
		expect(result).not.toBeNull();
		expect(result!.type).toBe("candle");
	});

	// ---------------------------------------------------------------------------
	// Multiline JSON data
	// ---------------------------------------------------------------------------

	it("returns null when data is on next line without inline bracket", () => {
		const spec = `type: line
xKey: date
yKey: price
data:
[{"date":"2026-01","price":100}]`;
		expect(parseChartSpec(spec)).toBeNull();
	});

	// ---------------------------------------------------------------------------
	// Optional fields
	// ---------------------------------------------------------------------------

	it("includes source and yLabel when present", () => {
		const spec = `type: bar
source: CoinGecko
yLabel: USD
data: [{"x":1,"y":2}]`;
		const result = parseChartSpec(spec);
		expect(result).not.toBeNull();
		expect(result!.source).toBe("CoinGecko");
		expect(result!.yLabel).toBe("USD");
	});

	it("omits optional fields when not provided", () => {
		const spec = `type: bar
data: [{"x":1}]`;
		const result = parseChartSpec(spec);
		expect(result).not.toBeNull();
		expect(result!.source).toBeUndefined();
		expect(result!.title).toBeUndefined();
	});

	// ---------------------------------------------------------------------------
	// Invalid / edge cases → null
	// ---------------------------------------------------------------------------

	it("returns null for missing type", () => {
		const spec = `data: [{"x":1}]`;
		expect(parseChartSpec(spec)).toBeNull();
	});

	it("returns null for missing data", () => {
		const spec = `type: line`;
		expect(parseChartSpec(spec)).toBeNull();
	});

	it("returns null for empty data array", () => {
		const spec = `type: line
data: []`;
		expect(parseChartSpec(spec)).toBeNull();
	});

	it("returns null for invalid JSON in data", () => {
		const spec = `type: line
data: not-json`;
		expect(parseChartSpec(spec)).toBeNull();
	});

	it("returns null for empty string", () => {
		expect(parseChartSpec("")).toBeNull();
	});

	it("returns null for whitespace-only input", () => {
		expect(parseChartSpec("   \n  ")).toBeNull();
	});
});
