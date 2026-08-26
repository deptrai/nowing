import type { ThreadMessageLike } from "@assistant-ui/react";
import {
	ARTIFACT_TOOL_KINDS,
	type ArtifactKind,
	type ArtifactStatus,
	type ChatArtifact,
} from "../model/artifact";

interface ToolCallPart {
	type: "tool-call";
	toolCallId: string;
	toolName: string;
	args?: Record<string, unknown>;
	result?: unknown;
}

function isToolCallPart(part: unknown): part is ToolCallPart {
	return (
		typeof part === "object" &&
		part !== null &&
		(part as { type?: unknown }).type === "tool-call" &&
		typeof (part as { toolCallId?: unknown }).toolCallId === "string" &&
		typeof (part as { toolName?: unknown }).toolName === "string"
	);
}

function asRecord(value: unknown): Record<string, unknown> {
	if (typeof value === "object" && value !== null) return value as Record<string, unknown>;
	if (typeof value === "string") {
		try {
			const parsed = JSON.parse(value);
			if (typeof parsed === "object" && parsed !== null) return parsed as Record<string, unknown>;
		} catch {
			// ignore non-json string
		}
	}
	return {};
}

function firstString(...values: unknown[]): string | null {
	for (const value of values) {
		if (typeof value === "string" && value.trim().length > 0) return value;
	}
	return null;
}

function numericId(value: unknown): number | null {
	return typeof value === "number" && Number.isFinite(value) ? value : null;
}

/** Extracts entity id, title, and status for a single deliverable tool call. */
function describeArtifact(
	kind: ArtifactKind,
	args: Record<string, unknown>,
	result: Record<string, unknown>,
	hasResult: boolean
): { title: string; entityId: number | null; status: ArtifactStatus } {
	const resultStatus = typeof result.status === "string" ? result.status : null;
	const failed =
		resultStatus === "failed" ||
		resultStatus === "error" ||
		resultStatus === "validation_failed" ||
		resultStatus === "deploy_failed" ||
		!!result.error;

	switch (kind) {
		case "report": {
			const entityId = numericId(result.report_id);
			return {
				title: firstString(result.title, args.topic) ?? "Report",
				entityId,
				status: failed ? "error" : entityId != null ? "ready" : "running",
			};
		}
		case "resume": {
			const entityId = numericId(result.report_id);
			return {
				title: firstString(result.title) ?? "Resume",
				entityId,
				status: failed ? "error" : entityId != null ? "ready" : "running",
			};
		}
		case "podcast": {
			const entityId = numericId(result.podcast_id);
			return {
				title: firstString(result.title, args.podcast_title) ?? "Podcast",
				entityId,
				status: failed ? "error" : entityId != null ? "ready" : "running",
			};
		}
		case "video": {
			const entityId = numericId(result.video_presentation_id);
			return {
				title: firstString(result.title, args.video_title) ?? "Video Presentation",
				entityId,
				status: failed ? "error" : entityId != null ? "ready" : "running",
			};
		}
		case "presentation": {
			const presentationId = firstString(result.presentation_id);
			return {
				title: firstString(result.title, args.prompt) ?? "Slide Deck",
				entityId: null,
				status: failed ? "error" : presentationId ? "ready" : "running",
			};
		}
		case "meeting_minutes": {
			const meetingMinutesId = numericId(result.meeting_minutes_id);
			const ready = resultStatus === "ready" || resultStatus === "degraded";
			return {
				title: firstString(result.title) ?? "Meeting Minutes",
				entityId: meetingMinutesId,
				status: failed ? "error" : ready ? "ready" : "running",
			};
		}
		case "image": {
			const ready = typeof result.src === "string" && result.src.length > 0;
			return {
				title: firstString(result.title, args.prompt) ?? "Image",
				entityId: null,
				status: failed ? "error" : ready ? "ready" : hasResult ? "ready" : "running",
			};
		}
		case "web_app": {
			const appId = firstString(result.app_id);
			return {
				title: firstString(result.name, args.app_name, args.prompt) ?? "Web App",
				entityId: null,
				status: failed ? "error" : appId ? "ready" : "running",
			};
		}
	}
}

/**
 * Aggregate the deliverable artifacts referenced across a thread's messages.
 *
 * Scans assistant tool-call parts, keeps recognized deliverable tools, and
 * dedupes by backing entity (so a regenerated report collapses to one entry,
 * refreshed in place to keep chronological order). Errored deliverables are
 * dropped — they have nothing to open or jump to.
 */
export function collectArtifacts(messages: readonly ThreadMessageLike[]): ChatArtifact[] {
	const byKey = new Map<string, ChatArtifact>();

	for (const message of messages) {
		if (message.role !== "assistant" || !Array.isArray(message.content)) continue;

		for (const part of message.content) {
			if (!isToolCallPart(part)) continue;
			const kind = ARTIFACT_TOOL_KINDS[part.toolName];
			if (!kind) continue;

			const args = asRecord(part.args);
			const result = asRecord(part.result);
			const { title, entityId, status } = describeArtifact(
				kind,
				args,
				result,
				part.result !== undefined
			);
			if (status === "error") continue;

			const appId = kind === "web_app" ? firstString(result.app_id) : null;
			const presentationId = kind === "presentation" ? firstString(result.presentation_id) : null;
			const key =
				entityId != null
					? `${kind}:${entityId}`
					: appId != null
						? `${kind}:${appId}`
						: presentationId != null
							? `${kind}:${presentationId}`
							: part.toolCallId;
			byKey.set(key, {
				key,
				kind,
				title,
				status,
				toolCallId: part.toolCallId,
				entityId,
				contentType:
					kind === "resume"
						? "typst"
						: kind === "web_app"
							? "web"
							: kind === "presentation" || kind === "meeting_minutes"
								? "markdown"
								: "markdown",
			});
		}
	}

	return Array.from(byKey.values());
}
