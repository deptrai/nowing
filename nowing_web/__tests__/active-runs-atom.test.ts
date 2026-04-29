import { describe, expect, it } from "vitest";
import { upsertRun, removeRun, updateRunStatus } from "@/atoms/chat/active-runs.atom";
import type { ChatRun } from "@/lib/apis/chat-runs-api.service";

function makeRun(overrides: Partial<ChatRun> = {}): ChatRun {
	return {
		id: "run-1",
		thread_id: 42,
		session_id: "42-abcd1234",
		langgraph_thread_id: "run-00000000-0000-0000-0000-000000000001",
		status: "running",
		user_query: "what is BTC?",
		started_at: new Date().toISOString(),
		completed_at: null,
		final_message_id: null,
		...overrides,
	};
}

describe("upsertRun", () => {
	it("inserts a new run into an empty map", () => {
		const map = new Map<number, ChatRun[]>();
		const run = makeRun();
		const result = upsertRun(map, run);
		expect(result.get(42)).toHaveLength(1);
		expect(result.get(42)![0].id).toBe("run-1");
	});

	it("appends a new run to an existing thread entry", () => {
		const run1 = makeRun({ id: "run-1" });
		const map = new Map([[42, [run1]]]);
		const run2 = makeRun({ id: "run-2" });
		const result = upsertRun(map, run2);
		expect(result.get(42)).toHaveLength(2);
	});

	it("updates an existing run (same id)", () => {
		const run = makeRun({ status: "running" });
		const map = new Map([[42, [run]]]);
		const updated = makeRun({ status: "completed" });
		const result = upsertRun(map, updated);
		expect(result.get(42)).toHaveLength(1);
		expect(result.get(42)![0].status).toBe("completed");
	});

	it("does not mutate the original map", () => {
		const map = new Map<number, ChatRun[]>();
		upsertRun(map, makeRun());
		expect(map.size).toBe(0);
	});
});

describe("removeRun", () => {
	it("removes the specified run", () => {
		const run = makeRun({ id: "run-1" });
		const map = new Map([[42, [run]]]);
		const result = removeRun(map, "run-1", 42);
		expect(result.get(42)).toHaveLength(0);
	});

	it("leaves other runs untouched", () => {
		const run1 = makeRun({ id: "run-1" });
		const run2 = makeRun({ id: "run-2" });
		const map = new Map([[42, [run1, run2]]]);
		const result = removeRun(map, "run-1", 42);
		expect(result.get(42)).toHaveLength(1);
		expect(result.get(42)![0].id).toBe("run-2");
	});

	it("is a no-op if run does not exist", () => {
		const map = new Map([[42, [makeRun()]]]);
		const result = removeRun(map, "nonexistent", 42);
		expect(result.get(42)).toHaveLength(1);
	});
});

describe("updateRunStatus", () => {
	it("updates status of matching run", () => {
		const run = makeRun({ status: "running" });
		const map = new Map([[42, [run]]]);
		const result = updateRunStatus(map, "run-1", 42, "abandoned");
		expect(result.get(42)![0].status).toBe("abandoned");
	});

	it("leaves other runs untouched", () => {
		const run1 = makeRun({ id: "run-1", status: "running" });
		const run2 = makeRun({ id: "run-2", status: "running" });
		const map = new Map([[42, [run1, run2]]]);
		const result = updateRunStatus(map, "run-1", 42, "completed");
		expect(result.get(42)![0].status).toBe("completed");
		expect(result.get(42)![1].status).toBe("running");
	});
});
