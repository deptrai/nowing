import assert from "node:assert/strict";
import { test } from "node:test";

// Test phone number normalization
function normalizePhoneNumber(phone: string): string {
	return phone.replace(/[^\d+]/g, "");
}

test("normalizePhoneNumber converts formatted Vietnamese phone to digits", () => {
	assert.equal(normalizePhoneNumber("0912.345.678"), "0912345678");
	assert.equal(normalizePhoneNumber("0912-345-678"), "0912345678");
	assert.equal(normalizePhoneNumber("0912 345 678"), "0912345678");
	assert.equal(normalizePhoneNumber("+84 912 345 678"), "+84912345678");
	assert.equal(normalizePhoneNumber("(024) 38.335.599"), "02438335599");
});

test("normalizePhoneNumber handles already normalized numbers", () => {
	assert.equal(normalizePhoneNumber("0987654321"), "0987654321");
	assert.equal(normalizePhoneNumber("+84987654321"), "+84987654321");
});

test("normalizePhoneNumber handles empty or special character strings gracefully", () => {
	assert.equal(normalizePhoneNumber(""), "");
	assert.equal(normalizePhoneNumber("N/A"), "");
	assert.equal(normalizePhoneNumber("---"), "");
});

// Test keyboard accessibility event recognition
function isCopyKey(key: string): boolean {
	return key === "Enter" || key === " ";
}

test("Keyboard accessibility triggers copy on Enter or Space", () => {
	assert.equal(isCopyKey("Enter"), true);
	assert.equal(isCopyKey(" "), true);
	assert.equal(isCopyKey("Tab"), false);
	assert.equal(isCopyKey("Escape"), false);
	assert.equal(isCopyKey("a"), false);
});
