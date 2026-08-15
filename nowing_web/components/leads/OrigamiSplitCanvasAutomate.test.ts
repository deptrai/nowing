import assert from "node:assert/strict";
import { test } from "node:test";

test("Resizer Dragging: dynamic clamp against container width and sidebar offset", () => {
	const MIN_LEFT_WIDTH = 360;
	const MAX_LEFT_WIDTH = 650;
	const MIN_RIGHT_WIDTH = 500;

	const calculateNewWidth = (clientX: number, containerLeft: number, containerWidth: number) => {
		const maxAllowedWidth = Math.min(MAX_LEFT_WIDTH, containerWidth - MIN_RIGHT_WIDTH);
		return Math.max(MIN_LEFT_WIDTH, Math.min(maxAllowedWidth, clientX - containerLeft));
	};

	// Standard desktop: containerWidth = 1400, sidebar offset = 240
	assert.equal(
		calculateNewWidth(660, 240, 1400),
		420,
		"ClientX 660 with 240 offset should calculate 420px"
	);

	// Below minimum clamp
	assert.equal(
		calculateNewWidth(300, 240, 1400),
		360,
		"Calculated width 60px should clamp to MIN_LEFT_WIDTH (360px)"
	);

	// Above maximum clamp
	assert.equal(
		calculateNewWidth(1200, 240, 1400),
		650,
		"Calculated width 960px should clamp to MAX_LEFT_WIDTH (650px)"
	);

	// Narrow container: containerWidth = 900 -> maxAllowedWidth = 400
	assert.equal(
		calculateNewWidth(800, 240, 900),
		400,
		"Narrow viewport should constrain maxAllowedWidth to 400px (900 - 500)"
	);
});

test("Fit Score Polarity: boundary conditions and null handling", () => {
	const getFitScoreBadge = (score: number | null | undefined) => {
		if (score == null) {
			return {
				label: "Chờ chấm",
				score: null,
				colorClass: "bg-zinc-800/60 text-zinc-400 border-zinc-700/50",
			};
		}
		const val = Number.isFinite(score) ? score : 0;
		if (val >= 80) {
			return {
				label: "High Fit",
				score: val,
				colorClass: "bg-emerald-500/15 text-emerald-400 border-emerald-500/30",
			};
		}
		if (val >= 50) {
			return {
				label: "Med Fit",
				score: val,
				colorClass: "bg-amber-500/15 text-amber-400 border-amber-500/30",
			};
		}
		return {
			label: "Low Fit",
			score: val,
			colorClass: "bg-rose-500/15 text-rose-400 border-rose-500/30",
		};
	};

	assert.equal(getFitScoreBadge(null).label, "Chờ chấm");
	assert.equal(getFitScoreBadge(undefined).label, "Chờ chấm");
	assert.equal(getFitScoreBadge(0).label, "Low Fit");
	assert.equal(getFitScoreBadge(49).label, "Low Fit");
	assert.equal(getFitScoreBadge(50).label, "Med Fit");
	assert.equal(getFitScoreBadge(79).label, "Med Fit");
	assert.equal(getFitScoreBadge(80).label, "High Fit");
	assert.equal(getFitScoreBadge(100).label, "High Fit");
	assert.equal(getFitScoreBadge(Number.NaN).label, "Low Fit");
});

test("Table Selection: isAllSelected checks true set containment without false positives", () => {
	const checkIsAllSelected = (visibleLeads: Array<{ id: string }>, selectedLeadIds: string[]) => {
		return visibleLeads.length > 0 && visibleLeads.every((l) => selectedLeadIds.includes(l.id));
	};

	const visibleBatch1 = [{ id: "l1" }, { id: "l2" }];
	const visibleBatch2 = [{ id: "l3" }, { id: "l4" }];

	// User selects l1, l2
	assert.equal(checkIsAllSelected(visibleBatch1, ["l1", "l2"]), true);

	// User switches filter to batch 2 (l3, l4) while l1, l2 remain in global selection
	assert.equal(
		checkIsAllSelected(visibleBatch2, ["l1", "l2"]),
		false,
		"Should not be all-selected when IDs do not match visible items"
	);

	// User partially selects visible items
	assert.equal(checkIsAllSelected(visibleBatch2, ["l1", "l2", "l3"]), false);

	// User selects all visible items
	assert.equal(checkIsAllSelected(visibleBatch2, ["l1", "l2", "l3", "l4"]), true);
});

test("Phone Call Link: minimum 8 digits validation threshold", () => {
	const shouldShowCallLink = (phone?: string | null) => {
		const cleanDigits = phone?.replace(/[^0-9+]/g, "") || "";
		return cleanDigits.length >= 8 ? `tel:${cleanDigits}` : null;
	};

	assert.equal(shouldShowCallLink("0901234567"), "tel:0901234567");
	assert.equal(shouldShowCallLink("+84 901 234 567"), "tel:+84901234567");
	assert.equal(shouldShowCallLink("Chưa có"), null);
	assert.equal(shouldShowCallLink("N/A"), null);
	assert.equal(shouldShowCallLink("123"), null);
	assert.equal(shouldShowCallLink(null), null);
	assert.equal(shouldShowCallLink(undefined), null);
});

test("Prompt Context: clean formatting without dangling delimiters", () => {
	const formatPromptWithLead = (
		query: string,
		lead?: {
			company_name?: string | null;
			location?: string | null;
			price_estimate?: string | null;
		} | null
	) => {
		const contextParts = lead
			? [lead.company_name, lead.location, lead.price_estimate].filter(Boolean)
			: [];
		const contextPrefix =
			contextParts.length > 0 ? `[Đang chọn: ${contextParts.join(" - ")}] ` : "";
		return `${contextPrefix}${query}`;
	};

	assert.equal(
		formatPromptWithLead("Lọc khách hàng quận 2", {
			company_name: "Công ty ABC",
			location: "Quận 2",
			price_estimate: "15 Tỷ",
		}),
		"[Đang chọn: Công ty ABC - Quận 2 - 15 Tỷ] Lọc khách hàng quận 2"
	);

	assert.equal(
		formatPromptWithLead("Phân tích chân dung", {
			company_name: "Nguyễn Văn A",
			location: null,
			price_estimate: null,
		}),
		"[Đang chọn: Nguyễn Văn A] Phân tích chân dung"
	);

	assert.equal(formatPromptWithLead("Quét danh sách", null), "Quét danh sách");
});
