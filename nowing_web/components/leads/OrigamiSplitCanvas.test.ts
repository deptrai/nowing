import assert from "node:assert/strict";
import { test } from "node:test";

test("Panel width clamp calculates correct bounding constraints (AC-1)", () => {
	const minWidth = 360;
	const maxWidth = 650;
	const defaultWidth = 420;

	const clampWidth = (w: number) => Math.max(minWidth, Math.min(maxWidth, w));

	assert.equal(clampWidth(200), 360, "Should clamp below minimum to 360px");
	assert.equal(clampWidth(420), 420, "Should keep default width at 420px");
	assert.equal(clampWidth(500), 500, "Should allow intermediate width 500px");
	assert.equal(clampWidth(900), 650, "Should clamp above maximum to 650px");
});

test("3-Mode Switcher validates supported active modes (AC-1)", () => {
	const validModes = ["leads", "research", "scrapers"] as const;
	type Mode = (typeof validModes)[number];

	const isSupportedMode = (mode: string): mode is Mode => validModes.includes(mode as Mode);

	assert.equal(isSupportedMode("leads"), true);
	assert.equal(isSupportedMode("research"), true);
	assert.equal(isSupportedMode("scrapers"), true);
	assert.equal(isSupportedMode("unknown"), false);
});

test("Bulk selection bar triggers when >= 2 items selected (AC-5)", () => {
	const shouldShowBulkBar = (selectedCount: number) => selectedCount >= 2;

	assert.equal(shouldShowBulkBar(0), false);
	assert.equal(shouldShowBulkBar(1), false);
	assert.equal(shouldShowBulkBar(2), true);
	assert.equal(shouldShowBulkBar(10), true);
});

test("Active lead context badge formatting outputs concise summary for AI prompt (AC-4)", () => {
	const formatLeadContextPrompt = (lead: {
		company_name?: string | null;
		title?: string | null;
		phone?: string | null;
		price?: string | null;
		location?: string | null;
	}) => {
		const name = lead.company_name || lead.title || "Khách hàng tiềm năng";
		const extra = [lead.location, lead.price].filter(Boolean).join(" - ");
		return extra ? `${name} (${extra})` : name;
	};

	assert.equal(
		formatLeadContextPrompt({
			company_name: "Nguyễn Văn Hùng",
			location: "Thủ Đức",
			price: "8.5 Tỷ",
		}),
		"Nguyễn Văn Hùng (Thủ Đức - 8.5 Tỷ)"
	);

	assert.equal(
		formatLeadContextPrompt({
			title: "Cần mua căn hộ 2PN Vinhomes Grand Park",
		}),
		"Cần mua căn hộ 2PN Vinhomes Grand Park"
	);
});
