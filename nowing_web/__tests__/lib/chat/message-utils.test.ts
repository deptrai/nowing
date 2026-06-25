/**
 * Unit tests — lib/chat/message-utils.ts
 * Covers: convertToThreadMessage
 * Priority: P1
 */
import { describe, it, expect } from "vitest";
import { convertToThreadMessage } from "@/lib/chat/message-utils";
import type { MessageRecord } from "@/lib/chat/thread-persistence";

// -----------------------------------------------------------------------
// Helpers
// -----------------------------------------------------------------------

function makeMsg(overrides: Partial<MessageRecord> = {}): MessageRecord {
	return {
		id: 1,
		thread_id: 10,
		role: "assistant",
		content: "Hello",
		created_at: "2026-01-01T00:00:00Z",
		...overrides,
	};
}

// -----------------------------------------------------------------------
// String content
// -----------------------------------------------------------------------

describe("convertToThreadMessage — string content", () => {
	it("wraps string content in text part array", () => {
		const result = convertToThreadMessage(makeMsg({ content: "Hello world" }));
		expect(result.content).toEqual([{ type: "text", text: "Hello world" }]);
	});

	it("preserves empty string content", () => {
		const result = convertToThreadMessage(makeMsg({ content: "" }));
		expect(result.content).toEqual([{ type: "text", text: "" }]);
	});
});

// -----------------------------------------------------------------------
// Non-string / non-array content
// -----------------------------------------------------------------------

describe("convertToThreadMessage — non-string/non-array content", () => {
	it("converts null content to text part with 'null'", () => {
		const result = convertToThreadMessage(makeMsg({ content: null }));
		expect(result.content).toEqual([{ type: "text", text: "null" }]);
	});

	it("converts number content to text via String()", () => {
		const result = convertToThreadMessage(makeMsg({ content: 42 as unknown }));
		expect(result.content).toEqual([{ type: "text", text: "42" }]);
	});
});

// -----------------------------------------------------------------------
// Array content — basic
// -----------------------------------------------------------------------

describe("convertToThreadMessage — array content", () => {
	it("passes through plain text parts unchanged", () => {
		const content = [{ type: "text", text: "Hello" }];
		const result = convertToThreadMessage(makeMsg({ content }));
		expect(result.content).toEqual([{ type: "text", text: "Hello" }]);
	});

	it("passes through multiple content parts", () => {
		const content = [
			{ type: "text", text: "Part 1" },
			{ type: "text", text: "Part 2" },
		];
		const result = convertToThreadMessage(makeMsg({ content }));
		expect(result.content).toHaveLength(2);
	});

	it("returns fallback text part when all parts are filtered out", () => {
		const content = [{ type: "mentioned-documents" }, { type: "attachments" }];
		const result = convertToThreadMessage(makeMsg({ content }));
		expect(result.content).toEqual([{ type: "text", text: "" }]);
	});

	it("returns fallback text part for empty array", () => {
		const result = convertToThreadMessage(makeMsg({ content: [] }));
		expect(result.content).toEqual([{ type: "text", text: "" }]);
	});
});

// -----------------------------------------------------------------------
// Array content — filters
// -----------------------------------------------------------------------

describe("convertToThreadMessage — filters mentioned-documents and attachments", () => {
	it("filters out mentioned-documents parts", () => {
		const content = [
			{ type: "text", text: "Hello" },
			{ type: "mentioned-documents", docs: [] },
		];
		const result = convertToThreadMessage(makeMsg({ content }));
		expect(result.content).toEqual([{ type: "text", text: "Hello" }]);
	});

	it("filters out attachments parts", () => {
		const content = [
			{ type: "text", text: "Message" },
			{ type: "attachments", files: [] },
		];
		const result = convertToThreadMessage(makeMsg({ content }));
		expect(result.content).toEqual([{ type: "text", text: "Message" }]);
	});

	it("filters both mentioned-documents and attachments, keeps text", () => {
		const content = [
			{ type: "mentioned-documents" },
			{ type: "text", text: "Kept" },
			{ type: "attachments" },
		];
		const result = convertToThreadMessage(makeMsg({ content }));
		expect(result.content).toEqual([{ type: "text", text: "Kept" }]);
	});
});

// -----------------------------------------------------------------------
// Array content — thinking-steps migration
// -----------------------------------------------------------------------

describe("convertToThreadMessage — thinking-steps → data-thinking-steps migration", () => {
	it("converts thinking-steps part to data-thinking-steps", () => {
		const steps = [{ thought: "step 1" }, { thought: "step 2" }];
		const content = [{ type: "thinking-steps", steps }];
		const result = convertToThreadMessage(makeMsg({ content }));
		expect(result.content).toEqual([{ type: "data-thinking-steps", data: { steps } }]);
	});

	it("preserves steps array in data-thinking-steps", () => {
		const steps = [{ thought: "only step" }];
		const content = [{ type: "thinking-steps", steps }];
		const result = convertToThreadMessage(makeMsg({ content }));
		const part = (result.content as Array<{ type: string; data?: { steps: unknown[] } }>)[0];
		expect(part.data?.steps).toEqual(steps);
	});

	it("defaults to empty steps when thinking-steps has no steps", () => {
		const content = [{ type: "thinking-steps" }];
		const result = convertToThreadMessage(makeMsg({ content }));
		const part = (result.content as Array<{ type: string; data?: { steps: unknown[] } }>)[0];
		expect(part.data?.steps).toEqual([]);
	});

	it("migrates thinking-steps alongside text parts", () => {
		const content = [
			{ type: "text", text: "Response" },
			{ type: "thinking-steps", steps: [{ thought: "thinking" }] },
		];
		const result = convertToThreadMessage(makeMsg({ content }));
		expect(result.content).toHaveLength(2);
		const parts = result.content as Array<{ type: string }>;
		expect(parts[0].type).toBe("text");
		expect(parts[1].type).toBe("data-thinking-steps");
	});
});

// -----------------------------------------------------------------------
// Return shape
// -----------------------------------------------------------------------

describe("convertToThreadMessage — return shape", () => {
	it("id is prefixed with 'msg-'", () => {
		const result = convertToThreadMessage(makeMsg({ id: 42 }));
		expect(result.id).toBe("msg-42");
	});

	it("role is preserved", () => {
		const result = convertToThreadMessage(makeMsg({ role: "user" }));
		expect(result.role).toBe("user");
	});

	it("createdAt is a Date object from created_at", () => {
		const result = convertToThreadMessage(makeMsg({ created_at: "2026-03-15T10:00:00Z" }));
		expect(result.createdAt).toBeInstanceOf(Date);
		expect((result.createdAt as Date).toISOString()).toBe("2026-03-15T10:00:00.000Z");
	});

	it("metadata is undefined when no author_id", () => {
		const result = convertToThreadMessage(makeMsg({ author_id: null }));
		expect(result.metadata).toBeUndefined();
	});

	it("metadata includes author info when author_id is present", () => {
		const result = convertToThreadMessage(
			makeMsg({
				author_id: "user-123",
				author_display_name: "Alice",
				author_avatar_url: "https://example.com/avatar.jpg",
			})
		);
		expect(result.metadata).toEqual({
			custom: {
				author: {
					displayName: "Alice",
					avatarUrl: "https://example.com/avatar.jpg",
				},
			},
		});
	});

	it("metadata author has null display name when not provided", () => {
		const result = convertToThreadMessage(
			makeMsg({ author_id: "user-123", author_display_name: undefined })
		);
		// eslint-disable-next-line @typescript-eslint/no-explicit-any
		expect((result.metadata as any)?.custom?.author?.displayName).toBeNull();
	});
});
