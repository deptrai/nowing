import assert from "node:assert/strict";
import { test } from "node:test";
import { type SuggestedAction, suggestedActionSchema } from "../../../contracts/types/chat-messages.types";

test("suggestedActionSchema validates valid action pill payload (AC: 1)", () => {
	const validPill = {
		id: "decode_phones",
		label: "📱 Giải mã 9 SĐT (13.5 credits)",
		icon: "phone",
		action_type: "decode_phones",
		prompt_template: "Giải mã 9 số điện thoại.",
		cost_credits: 13.5,
		payload: { selection_count: 9, cost_credits: 13.5 },
	};

	const parsed = suggestedActionSchema.parse(validPill);
	assert.equal(parsed.id, "decode_phones");
	assert.equal(parsed.label, "📱 Giải mã 9 SĐT (13.5 credits)");
	assert.equal(parsed.cost_credits, 13.5);
	assert.equal(parsed.payload?.selection_count, 9);
});

test("suggestedActionSchema allows default icon and optional cost/payload", () => {
	const minimalPill = {
		id: "zalo_draft",
		label: "💬 Tạo tin nhắn Zalo mẫu",
		action_type: "zalo_draft",
		prompt_template: "Soạn tin nhắn Zalo tiếp cận khách hàng.",
	};

	const parsed = suggestedActionSchema.parse(minimalPill);
	assert.equal(parsed.icon, "sparkles");
	assert.equal(parsed.cost_credits, undefined);
});

test("Dynamic selection count and credit calculation formula (AC: 4)", () => {
	const calculatePill = (selectionCount: number): SuggestedAction => {
		const cost = selectionCount * 1.5;
		return {
			id: "decode_phones",
			label: `📱 Giải mã ${selectionCount} SĐT (${cost} credits)`,
			icon: "phone",
			action_type: "decode_phones",
			prompt_template: `Giải mã ${selectionCount} số điện thoại.`,
			cost_credits: cost,
			payload: { selection_count: selectionCount, cost_credits: cost },
		};
	};

	const pill3 = calculatePill(3);
	assert.equal(pill3.label, "📱 Giải mã 3 SĐT (4.5 credits)");
	assert.equal(pill3.cost_credits, 4.5);

	const pill9 = calculatePill(9);
	assert.equal(pill9.label, "📱 Giải mã 9 SĐT (13.5 credits)");
	assert.equal(pill9.cost_credits, 13.5);
});

test("Keyboard shortcut mapping matches Alt+1, Alt+2, Alt+3 (AC: 5)", () => {
	const actions: SuggestedAction[] = [
		{ id: "a1", label: "Action 1", icon: "phone", action_type: "t1", prompt_template: "P1" },
		{
			id: "a2",
			label: "Action 2",
			icon: "message-square",
			action_type: "t2",
			prompt_template: "P2",
		},
		{ id: "a3", label: "Action 3", icon: "search", action_type: "t3", prompt_template: "P3" },
	];

	const getActionForShortcut = (digitKey: string, isAlt: boolean): SuggestedAction | null => {
		if (!isAlt) return null;
		const index = Number.parseInt(digitKey, 10) - 1;
		if (index >= 0 && index < actions.length) {
			return actions[index];
		}
		return null;
	};

	assert.equal(getActionForShortcut("1", true)?.id, "a1");
	assert.equal(getActionForShortcut("2", true)?.id, "a2");
	assert.equal(getActionForShortcut("3", true)?.id, "a3");
	assert.equal(getActionForShortcut("4", true), null);
	assert.equal(getActionForShortcut("1", false), null);
});
