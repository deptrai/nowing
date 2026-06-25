"use client";

import { atom } from "jotai";
import type { ChatRun } from "@/lib/apis/chat-runs-api.service";

/**
 * T21: Resume handler injected by page.tsx.
 * Called by OrchestraStrip when user clicks Resume on an abandoned session.
 * Keyed by langgraph_thread_id (== OrchestraSession.sessionId).
 */
export const resumeRunBySessionAtom = atom<((langgraphThreadId: string) => Promise<void>) | null>(
	null
);

/**
 * T21: Set of langgraph_thread_id values for runs with status="abandoned".
 * Written by page.tsx; read by AssistantMessageInner to show Resume UI.
 */
export const abandonedSessionIdsAtom = atom<Set<string>>(new Set<string>());

/**
 * Map of threadId → list of active (running or abandoned) ChatRun objects.
 * Populated on page mount by getActiveRuns() and updated as runs complete.
 */
export const activeRunsAtom = atom<Map<number, ChatRun[]>>(new Map());

/** Derived: all active runs for a specific thread. */
export const activeRunsForThreadAtom = (threadId: number) =>
	atom<ChatRun[]>((get) => {
		const map = get(activeRunsAtom);
		return map.get(threadId) ?? [];
	});

/** Actions: upsert a run into the map (running or updated status). */
export function upsertRun(map: Map<number, ChatRun[]>, run: ChatRun): Map<number, ChatRun[]> {
	const next = new Map(map);
	const existing = next.get(run.thread_id) ?? [];
	const idx = existing.findIndex((r) => r.id === run.id);
	if (idx >= 0) {
		const updated = [...existing];
		updated[idx] = run;
		next.set(run.thread_id, updated);
	} else {
		next.set(run.thread_id, [...existing, run]);
	}
	return next;
}

/** Actions: remove a run from the map (terminal status). */
export function removeRun(
	map: Map<number, ChatRun[]>,
	runId: string,
	threadId: number
): Map<number, ChatRun[]> {
	const next = new Map(map);
	const existing = next.get(threadId) ?? [];
	next.set(
		threadId,
		existing.filter((r) => r.id !== runId)
	);
	return next;
}

/** Update a run's status in the map. */
export function updateRunStatus(
	map: Map<number, ChatRun[]>,
	runId: string,
	threadId: number,
	status: ChatRun["status"]
): Map<number, ChatRun[]> {
	const next = new Map(map);
	const existing = next.get(threadId) ?? [];
	next.set(
		threadId,
		existing.map((r) => (r.id === runId ? { ...r, status } : r))
	);
	return next;
}
