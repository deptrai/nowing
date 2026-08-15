import assert from "node:assert/strict";
import test from "node:test";

/**
 * Helper to parse and validate CSV rows for DNC import (Story 21.14).
 */
export function parseDncCsv(
	csvText: string
): Array<{ record_type: string; value: string; reason?: string }> {
	const lines = csvText
		.split(/\r?\n/)
		.map((l) => l.trim())
		.filter(Boolean);
	if (lines.length <= 1) return [];

	const headers = lines[0]
		.toLowerCase()
		.split(",")
		.map((h) => h.trim());
	const typeIdx = headers.indexOf("type");
	const valueIdx = headers.indexOf("value");
	const reasonIdx = headers.indexOf("reason");

	if (typeIdx === -1 || valueIdx === -1) {
		throw new Error("Invalid CSV headers: must contain 'type' and 'value'");
	}

	const results = [];
	for (let i = 1; i < lines.length; i++) {
		const cols = lines[i].split(",").map((c) => c.trim());
		if (cols[valueIdx]) {
			results.push({
				record_type: cols[typeIdx] || "phone",
				value: cols[valueIdx],
				reason: reasonIdx !== -1 ? cols[reasonIdx] : undefined,
			});
		}
	}
	return results;
}

/**
 * Helper to format DNC badge label and color variant.
 */
export function formatDncBadge(
	isBlocked: boolean,
	reason?: string | null
): { label: string; isBlocked: boolean } {
	if (!isBlocked) {
		return { label: "Compliant", isBlocked: false };
	}
	return {
		label: reason ? `🚫 DNC: ${reason}` : "🚫 DNC Blocked",
		isBlocked: true,
	};
}

test("parseDncCsv parses valid 3-column CSV text", () => {
	const sampleCsv = `type,value,reason\nphone,0908123456,Customer Request\ndomain,*.competitor.vn,Competitor\nemail,ceo@blocked.com,Opt-out`;
	const rows = parseDncCsv(sampleCsv);

	assert.equal(rows.length, 3);
	assert.equal(rows[0].record_type, "phone");
	assert.equal(rows[0].value, "0908123456");
	assert.equal(rows[0].reason, "Customer Request");
	assert.equal(rows[1].record_type, "domain");
	assert.equal(rows[1].value, "*.competitor.vn");
});

test("parseDncCsv throws error on missing required headers", () => {
	const badCsv = `name,contact\nJohn,0908123456`;
	assert.throws(() => parseDncCsv(badCsv), /Invalid CSV headers/);
});

test("formatDncBadge returns compliant badge when lead is not blocked", () => {
	const badge = formatDncBadge(false);
	assert.equal(badge.isBlocked, false);
	assert.equal(badge.label, "Compliant");
});

test("formatDncBadge returns blocked badge with custom reason", () => {
	const badge = formatDncBadge(true, "Decree 91 Blacklist");
	assert.equal(badge.isBlocked, true);
	assert.equal(badge.label, "🚫 DNC: Decree 91 Blacklist");
});
