import assert from "node:assert/strict";
import { test } from "node:test";

function getFitScorePolarity(score: number | null | undefined): {
	category: "high" | "medium" | "low";
	label: string;
	color: string;
} {
	const val = score ?? 0;
	if (val >= 80) {
		return { category: "high", label: "High Fit", color: "emerald" };
	}
	if (val >= 50) {
		return { category: "medium", label: "Medium Fit", color: "amber" };
	}
	return { category: "low", label: "Low Fit", color: "rose" };
}

test("Fit Score polarity maps correctly for all score ranges (AC-1)", () => {
	// High Fit (>= 80)
	assert.deepEqual(getFitScorePolarity(100), {
		category: "high",
		label: "High Fit",
		color: "emerald",
	});
	assert.deepEqual(getFitScorePolarity(80), {
		category: "high",
		label: "High Fit",
		color: "emerald",
	});
	assert.deepEqual(getFitScorePolarity(92.5), {
		category: "high",
		label: "High Fit",
		color: "emerald",
	});

	// Medium Fit (50-79)
	assert.deepEqual(getFitScorePolarity(79), {
		category: "medium",
		label: "Medium Fit",
		color: "amber",
	});
	assert.deepEqual(getFitScorePolarity(50), {
		category: "medium",
		label: "Medium Fit",
		color: "amber",
	});
	assert.deepEqual(getFitScorePolarity(65), {
		category: "medium",
		label: "Medium Fit",
		color: "amber",
	});

	// Low Fit (< 50)
	assert.deepEqual(getFitScorePolarity(49), { category: "low", label: "Low Fit", color: "rose" });
	assert.deepEqual(getFitScorePolarity(0), { category: "low", label: "Low Fit", color: "rose" });
	assert.deepEqual(getFitScorePolarity(null), { category: "low", label: "Low Fit", color: "rose" });
	assert.deepEqual(getFitScorePolarity(undefined), {
		category: "low",
		label: "Low Fit",
		color: "rose",
	});
});

function getIntentLabel(intent: string | null | undefined): string {
	const tag = (intent || "BÁN").toUpperCase();
	if (tag.includes("BÁN")) return "🏷️ INTENT: BÁN";
	if (tag.includes("MUA")) return "🏷️ INTENT: MUA";
	if (tag.includes("TUYỂN") || tag.includes("JOB")) return "🏷️ INTENT: TUYỂN DỤNG";
	if (tag.includes("THẦU") || tag.includes("TENDER")) return "🏷️ INTENT: ĐẤU THẦU";
	return `🏷️ INTENT: ${tag}`;
}

test("Intent tag formatting returns correct badge labels (Widget U3 & U4)", () => {
	assert.equal(getIntentLabel("BÁN"), "🏷️ INTENT: BÁN");
	assert.equal(getIntentLabel("bán nhà"), "🏷️ INTENT: BÁN");
	assert.equal(getIntentLabel("MUA"), "🏷️ INTENT: MUA");
	assert.equal(getIntentLabel("tuyển dụng"), "🏷️ INTENT: TUYỂN DỤNG");
	assert.equal(getIntentLabel("đấu thầu"), "🏷️ INTENT: ĐẤU THẦU");
	assert.equal(getIntentLabel(null), "🏷️ INTENT: BÁN");
});

function getSourceDisplay(source: string): string {
	const s = source.toLowerCase();
	if (s.includes("facebook")) return "👥 Facebook";
	if (s.includes("telegram")) return "✈️ Telegram";
	if (s.includes("bds") || s.includes("batdongsan")) return "🏠 Batdongsan";
	if (s.includes("topcv") || s.includes("itviec") || s.includes("job")) return "💼 Jobs";
	if (s.includes("tender") || s.includes("muasamcong")) return "🏛️ Đấu Thầu";
	if (s.includes("shopee") || s.includes("tiktok")) return "🛍️ E-commerce";
	if (s.includes("linkedin")) return "💼 LinkedIn";
	if (s.includes("x") || s.includes("twitter")) return "𝕏 Twitter/X";
	return `🌐 ${source}`;
}

test("Source platform icon mapping covers all scraper expansion channels", () => {
	assert.equal(getSourceDisplay("facebook_group"), "👥 Facebook");
	assert.equal(getSourceDisplay("telegram_channel"), "✈️ Telegram");
	assert.equal(getSourceDisplay("batdongsan_vn"), "🏠 Batdongsan");
	assert.equal(getSourceDisplay("topcv_jobs"), "💼 Jobs");
	assert.equal(getSourceDisplay("muasamcong_gov"), "🏛️ Đấu Thầu");
	assert.equal(getSourceDisplay("shopee_mall"), "🛍️ E-commerce");
	assert.equal(getSourceDisplay("linkedin_post"), "💼 LinkedIn");
	assert.equal(getSourceDisplay("twitter_feed"), "𝕏 Twitter/X");
	assert.equal(getSourceDisplay("custom_portal"), "🌐 custom_portal");
});
