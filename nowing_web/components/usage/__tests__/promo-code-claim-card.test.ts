import assert from "node:assert/strict";
import { test } from "node:test";

// ---------------------------------------------------------------------------
// 1. Promo Code Normalization & Client-Side Validation Tests
// ---------------------------------------------------------------------------
function cleanPromoCode(input: string): string {
	return input.trim().toUpperCase();
}

function validatePromoCodeFormat(code: string): { isValid: boolean; error?: string } {
	const normalized = cleanPromoCode(code);
	if (!normalized) {
		return { isValid: false, error: "Vui lòng nhập mã khuyến mãi" };
	}
	if (normalized.length < 3) {
		return { isValid: false, error: "Mã khuyến mãi phải có ít nhất 3 ký tự" };
	}
	if (!/^[A-Z0-9_-]+$/.test(normalized)) {
		return { isValid: false, error: "Mã khuyến mãi chỉ chứa chữ cái, số và dấu gạch ngang" };
	}
	return { isValid: true };
}

test("cleanPromoCode converts to uppercase and trims whitespace", () => {
	assert.equal(cleanPromoCode(" welcome50 "), "WELCOME50");
	assert.equal(cleanPromoCode("nowing-gift-2026"), "NOWING-GIFT-2026");
});

test("validatePromoCodeFormat accepts standard alphanumeric codes", () => {
	assert.equal(validatePromoCodeFormat("WELCOME50").isValid, true);
	assert.equal(validatePromoCodeFormat("GIFT-100").isValid, true);
});

test("validatePromoCodeFormat rejects empty and short codes", () => {
	assert.equal(validatePromoCodeFormat("").isValid, false);
	assert.equal(validatePromoCodeFormat("AB").isValid, false);
});

test("validatePromoCodeFormat rejects invalid special characters", () => {
	assert.equal(validatePromoCodeFormat("CODE$100").isValid, false);
	assert.equal(validatePromoCodeFormat("MÃ_QUÀ").isValid, false);
});

// ---------------------------------------------------------------------------
// 2. Currency & Credit Formatting Helpers
// ---------------------------------------------------------------------------
function formatCreditDisplay(micros: number): { credits: string; usd: string } {
	const credits = (micros / 40_000).toLocaleString("vi-VN", { maximumFractionDigits: 1 });
	const dollars = (micros / 1_000_000).toFixed(2);
	return { credits: `${credits} credits`, usd: `$${dollars}` };
}

test("formatCreditDisplay formats 2,000,000 micros correctly", () => {
	const res = formatCreditDisplay(2_000_000);
	assert.equal(res.credits, "50 credits");
	assert.equal(res.usd, "$2.00");
});
