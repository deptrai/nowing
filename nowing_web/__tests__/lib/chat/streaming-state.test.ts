/**
 * Unit tests for lib/chat/streaming-state.ts
 * Pure-function coverage for ContentPartsState mutation helpers.
 */
import { describe, it, expect, beforeEach } from "vitest";
import {
	appendText,
	addToolCall,
	updateToolCall,
	updateThinkingSteps,
	buildContentForUI,
	buildContentForPersistence,
	type ContentPartsState,
	type ThinkingStepData,
} from "@/lib/chat/streaming-state";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function makeState(): ContentPartsState {
	return {
		contentParts: [],
		currentTextPartIndex: -1,
		toolCallIndices: new Map(),
	};
}

function makeThinkingStep(overrides: Partial<ThinkingStepData> = {}): ThinkingStepData {
	return {
		id: "step-1",
		title: "Thinking…",
		status: "in_progress",
		items: [],
		...overrides,
	};
}

// ---------------------------------------------------------------------------
// appendText
// ---------------------------------------------------------------------------

describe("appendText", () => {
	it("pushes a new text part when state is empty", () => {
		const state = makeState();
		appendText(state, "hello");

		expect(state.contentParts).toHaveLength(1);
		expect(state.contentParts[0]).toEqual({ type: "text", text: "hello" });
		expect(state.currentTextPartIndex).toBe(0);
	});

	it("appends to the current text part when it is active", () => {
		const state = makeState();
		appendText(state, "hello");
		appendText(state, " world");

		expect(state.contentParts).toHaveLength(1);
		expect(state.contentParts[0]).toEqual({ type: "text", text: "hello world" });
	});

	it("starts a new text part after currentTextPartIndex is reset to -1", () => {
		const state = makeState();
		appendText(state, "first");
		state.currentTextPartIndex = -1; // simulate reset (e.g. after tool-call)
		appendText(state, "second");

		expect(state.contentParts).toHaveLength(2);
		expect(state.contentParts[1]).toEqual({ type: "text", text: "second" });
		expect(state.currentTextPartIndex).toBe(1);
	});

	it("appends empty delta without error", () => {
		const state = makeState();
		appendText(state, "");
		expect(state.contentParts).toHaveLength(1);
		expect((state.contentParts[0] as { type: "text"; text: string }).text).toBe("");
	});
});

// ---------------------------------------------------------------------------
// addToolCall
// ---------------------------------------------------------------------------

describe("addToolCall", () => {
	it("adds a tool-call part when tool is in toolsWithUI", () => {
		const state = makeState();
		const toolsWithUI = new Set(["my-tool"]);
		addToolCall(state, toolsWithUI, "tc-1", "my-tool", { foo: "bar" });

		expect(state.contentParts).toHaveLength(1);
		expect(state.contentParts[0]).toMatchObject({
			type: "tool-call",
			toolCallId: "tc-1",
			toolName: "my-tool",
			args: { foo: "bar" },
		});
	});

	it("indexes the tool-call in toolCallIndices", () => {
		const state = makeState();
		const toolsWithUI = new Set(["my-tool"]);
		addToolCall(state, toolsWithUI, "tc-1", "my-tool", {});

		expect(state.toolCallIndices.get("tc-1")).toBe(0);
	});

	it("resets currentTextPartIndex to -1 after adding tool-call", () => {
		const state = makeState();
		appendText(state, "prefix");
		const toolsWithUI = new Set(["my-tool"]);
		addToolCall(state, toolsWithUI, "tc-1", "my-tool", {});

		expect(state.currentTextPartIndex).toBe(-1);
	});

	it("does NOT add tool-call when tool is not in toolsWithUI", () => {
		const state = makeState();
		const toolsWithUI = new Set<string>();
		addToolCall(state, toolsWithUI, "tc-1", "hidden-tool", {});

		expect(state.contentParts).toHaveLength(0);
		expect(state.toolCallIndices.size).toBe(0);
	});

	it("indexes correctly when tool-call is appended after text", () => {
		const state = makeState();
		appendText(state, "text");
		const toolsWithUI = new Set(["t"]);
		addToolCall(state, toolsWithUI, "tc-2", "t", {});

		expect(state.toolCallIndices.get("tc-2")).toBe(1);
	});
});

// ---------------------------------------------------------------------------
// updateToolCall
// ---------------------------------------------------------------------------

describe("updateToolCall", () => {
	it("updates args of an existing tool-call", () => {
		const state = makeState();
		addToolCall(state, new Set(["t"]), "tc-1", "t", { x: 1 });
		updateToolCall(state, "tc-1", { args: { x: 99 } });

		const tc = state.contentParts[0] as { type: "tool-call"; args: Record<string, unknown> };
		expect(tc.args).toEqual({ x: 99 });
	});

	it("sets result on an existing tool-call", () => {
		const state = makeState();
		addToolCall(state, new Set(["t"]), "tc-1", "t", {});
		updateToolCall(state, "tc-1", { result: { ok: true } });

		const tc = state.contentParts[0] as { type: "tool-call"; result?: unknown };
		expect(tc.result).toEqual({ ok: true });
	});

	it("does nothing for unknown toolCallId", () => {
		const state = makeState();
		addToolCall(state, new Set(["t"]), "tc-1", "t", { x: 1 });
		updateToolCall(state, "unknown-id", { args: { x: 999 } });

		const tc = state.contentParts[0] as { type: "tool-call"; args: Record<string, unknown> };
		expect(tc.args).toEqual({ x: 1 }); // unchanged
	});
});

// ---------------------------------------------------------------------------
// updateThinkingSteps
// ---------------------------------------------------------------------------

describe("updateThinkingSteps", () => {
	it("inserts thinking-steps part at front when none exists", () => {
		const state = makeState();
		appendText(state, "text");
		const steps = new Map([["s1", makeThinkingStep({ id: "s1" })]]);

		const changed = updateThinkingSteps(state, steps);

		expect(changed).toBe(true);
		expect(state.contentParts[0].type).toBe("data-thinking-steps");
	});

	it("bumps currentTextPartIndex when inserting at front", () => {
		const state = makeState();
		appendText(state, "text");
		expect(state.currentTextPartIndex).toBe(0);

		const steps = new Map([["s1", makeThinkingStep({ id: "s1" })]]);
		updateThinkingSteps(state, steps);

		expect(state.currentTextPartIndex).toBe(1);
	});

	it("bumps toolCallIndices when inserting at front", () => {
		const state = makeState();
		addToolCall(state, new Set(["t"]), "tc-1", "t", {});
		expect(state.toolCallIndices.get("tc-1")).toBe(0);

		const steps = new Map([["s1", makeThinkingStep({ id: "s1" })]]);
		updateThinkingSteps(state, steps);

		expect(state.toolCallIndices.get("tc-1")).toBe(1);
	});

	it("updates in-place when thinking-steps part already exists", () => {
		const state = makeState();
		const steps1 = new Map([["s1", makeThinkingStep({ id: "s1", title: "Old" })]]);
		updateThinkingSteps(state, steps1);

		const steps2 = new Map([["s1", makeThinkingStep({ id: "s1", title: "New" })]]);
		const changed = updateThinkingSteps(state, steps2);

		expect(changed).toBe(true);
		expect(state.contentParts).toHaveLength(1); // no duplication
		const part = state.contentParts[0] as {
			type: "data-thinking-steps";
			data: { steps: ThinkingStepData[] };
		};
		expect(part.data.steps[0].title).toBe("New");
	});

	it("returns false when thinking-steps are identical (no change)", () => {
		const state = makeState();
		const step = makeThinkingStep({ id: "s1", title: "Same", items: ["a"] });
		const steps1 = new Map([["s1", step]]);
		updateThinkingSteps(state, steps1);

		const step2 = makeThinkingStep({ id: "s1", title: "Same", items: ["a"] });
		const steps2 = new Map([["s1", step2]]);
		const changed = updateThinkingSteps(state, steps2);

		expect(changed).toBe(false);
	});
});

// ---------------------------------------------------------------------------
// buildContentForUI
// ---------------------------------------------------------------------------

describe("buildContentForUI", () => {
	it("returns [{type:'text',text:''}] when state is empty", () => {
		const state = makeState();
		const result = buildContentForUI(state, new Set());

		expect(result).toEqual([{ type: "text", text: "" }]);
	});

	it("includes non-empty text parts", () => {
		const state = makeState();
		appendText(state, "hello");
		const result = buildContentForUI(state, new Set());

		expect(result).toHaveLength(1);
		expect(result[0]).toMatchObject({ type: "text", text: "hello" });
	});

	it("excludes empty text parts", () => {
		const state = makeState();
		appendText(state, "");
		const result = buildContentForUI(state, new Set());

		expect(result).toEqual([{ type: "text", text: "" }]); // fallback
	});

	it("includes tool-calls that are in toolsWithUI", () => {
		const state = makeState();
		addToolCall(state, new Set(["visible"]), "tc-1", "visible", {});
		const result = buildContentForUI(state, new Set(["visible"]));

		expect(result).toHaveLength(1);
		expect(result[0]).toMatchObject({ type: "tool-call", toolName: "visible" });
	});

	it("excludes tool-calls not in toolsWithUI", () => {
		const state = makeState();
		// Tool added (simulating hidden tool by directly pushing)
		state.contentParts.push({ type: "tool-call", toolCallId: "tc-1", toolName: "hidden", args: {} });
		const result = buildContentForUI(state, new Set()); // "hidden" not in set

		expect(result).toEqual([{ type: "text", text: "" }]); // fallback
	});

	it("always includes data-thinking-steps parts", () => {
		const state = makeState();
		const steps = new Map([["s1", makeThinkingStep()]]);
		updateThinkingSteps(state, steps);
		const result = buildContentForUI(state, new Set());

		expect(result).toHaveLength(1);
		expect(result[0].type).toBe("data-thinking-steps");
	});
});

// ---------------------------------------------------------------------------
// buildContentForPersistence
// ---------------------------------------------------------------------------

describe("buildContentForPersistence", () => {
	it("returns [{type:'text',text:''}] when state is empty", () => {
		const state = makeState();
		expect(buildContentForPersistence(state, new Set())).toEqual([{ type: "text", text: "" }]);
	});

	it("includes non-empty text parts", () => {
		const state = makeState();
		appendText(state, "content");
		const result = buildContentForPersistence(state, new Set());

		expect(result).toHaveLength(1);
		expect(result[0]).toMatchObject({ type: "text", text: "content" });
	});

	it("excludes empty text parts", () => {
		const state = makeState();
		appendText(state, "");
		const result = buildContentForPersistence(state, new Set());

		expect(result).toEqual([{ type: "text", text: "" }]);
	});

	it("includes tool-calls in toolsWithUI", () => {
		const state = makeState();
		addToolCall(state, new Set(["t"]), "tc-1", "t", { k: "v" });
		const result = buildContentForPersistence(state, new Set(["t"]));

		expect(result).toHaveLength(1);
		expect((result[0] as { toolName: string }).toolName).toBe("t");
	});

	it("excludes tool-calls not in toolsWithUI", () => {
		const state = makeState();
		state.contentParts.push({ type: "tool-call", toolCallId: "tc-1", toolName: "hidden", args: {} });
		const result = buildContentForPersistence(state, new Set());

		expect(result).toEqual([{ type: "text", text: "" }]);
	});

	it("includes data-thinking-steps parts", () => {
		const state = makeState();
		const steps = new Map([["s1", makeThinkingStep()]]);
		updateThinkingSteps(state, steps);
		const result = buildContentForPersistence(state, new Set());

		expect(result).toHaveLength(1);
		expect((result[0] as { type: string }).type).toBe("data-thinking-steps");
	});
});
