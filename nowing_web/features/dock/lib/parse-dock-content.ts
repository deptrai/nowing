"use client";

import type { DockTabId } from "@/atoms/layout/dock.atom";
import type { ContentPart } from "@/lib/chat/streaming-state";
import { parseWebAppResult, type WebAppBuildResult } from "./parse-web-app-result";

export interface ToolCallContentPart extends Extract<ContentPart, { type: "tool-call" }> {}

export interface CodeBlockData {
	language: string;
	code: string;
	source?: string;
}

export interface ResearchReportData {
	title: string;
	summary: string;
	keyFindings: string[];
	citations: Array<{ title: string; url: string; snippet?: string }>;
}

export interface DockSourceCitation {
	title: string;
	url: string;
	snippet?: string;
	domain?: string;
	sourceType?: string;
}

export type DockTabPayload =
	| { kind: "leads" }
	| { kind: "web-builder"; result: Partial<WebAppBuildResult> }
	| { kind: "images"; parts: ToolCallContentPart[] }
	| { kind: "reports"; part: ToolCallContentPart }
	| { kind: "media"; parts: ToolCallContentPart[] }
	| { kind: "research"; report: ResearchReportData | null }
	| { kind: "code"; blocks: CodeBlockData[] }
	| { kind: "charts"; specs: string[] }
	| { kind: "slides"; result: unknown }
	| { kind: "sources"; citations: DockSourceCitation[] }
	| { kind: "artifacts"; parts: ToolCallContentPart[] };

function asContentParts(content: unknown): ContentPart[] {
	if (Array.isArray(content)) return content as ContentPart[];
	if (typeof content === "string") return [{ type: "text", text: content } as ContentPart];
	return [];
}

function isCodeBlock(code: string): boolean {
	const lines = code.split("\n").filter((line) => line.trim().length > 0);
	return lines.length > 12;
}

function parseCodeBlocks(text: string): CodeBlockData[] {
	const blocks: CodeBlockData[] = [];
	const regex = /^```(\w+)?\n([\s\S]*?)^```/gm;
	let match: RegExpExecArray | null = regex.exec(text);
	while (match !== null) {
		const language = match[1]?.trim() || "text";
		const code = match[2].replace(/\n$/, "");
		if (language.toLowerCase() !== "mermaid" && isCodeBlock(code)) {
			blocks.push({ language, code, source: `${language} snippet` });
		}
		match = regex.exec(text);
	}
	return blocks;
}

function parseMermaidBlocks(text: string): string[] {
	const specs: string[] = [];
	const regex = /^```mermaid\n([\s\S]*?)^```/gim;
	let match: RegExpExecArray | null = regex.exec(text);
	while (match !== null) {
		specs.push(match[1].replace(/\n$/, ""));
		match = regex.exec(text);
	}
	return specs;
}

function parseResearchReport(raw: unknown): ResearchReportData | null {
	if (typeof raw !== "object" || raw === null) return null;
	const result = raw as Record<string, unknown>;
	const answer = typeof result.answer === "string" ? result.answer : "";
	const title =
		(typeof result.title === "string" && result.title) ||
		answer.split("\n")[0]?.slice(0, 80) ||
		"Research Report";

	const summary = answer.split("\n\n")[0] || answer.slice(0, 400);
	const keyFindings = answer
		.split("\n")
		.map((line) => line.trim())
		.filter((line) => line.startsWith("- ") || line.startsWith("* "))
		.map((line) => line.replace(/^[-*]\s+/, ""))
		.slice(0, 10);

	const sources = Array.isArray(result.sources) ? result.sources : [];
	const citations = sources
		.map((s: unknown) => {
			if (typeof s !== "object" || s === null) return null;
			const src = s as Record<string, unknown>;
			const url = typeof src.url === "string" ? src.url : "";
			return {
				title: (typeof src.title === "string" ? src.title : url) || "Source",
				url,
				snippet: typeof src.content === "string" ? src.content : undefined,
				domain: typeof src.domain === "string" ? src.domain : undefined,
				sourceType: typeof src.source_type === "string" ? src.source_type : undefined,
			} as DockSourceCitation;
		})
		.filter(Boolean) as DockSourceCitation[];

	return { title, summary, keyFindings, citations };
}

export interface ParsedDockTab {
	id: DockTabId;
	label: string;
	payload: DockTabPayload;
}

export interface ParseDockContentOptions {
	hasLeads?: boolean;
}

export function parseDockContent(
	messages: Array<{ role: string; content?: unknown }>,
	options: ParseDockContentOptions = {}
): ParsedDockTab[] {
	const tabs: ParsedDockTab[] = [];
	const images: ToolCallContentPart[] = [];
	const media: ToolCallContentPart[] = [];
	const artifacts: ToolCallContentPart[] = [];
	let reportPart: ToolCallContentPart | null = null;
	let researchPart: ToolCallContentPart | null = null;
	let slidesPart: ToolCallContentPart | null = null;
	let webAppResult: Partial<WebAppBuildResult> | null = null;
	const codeBlocks: CodeBlockData[] = [];
	const chartSpecs: string[] = [];

	for (const message of messages) {
		if (message.role !== "assistant") continue;
		const parts = asContentParts(message.content);
		for (const part of parts) {
			if (part.type === "text") {
				codeBlocks.push(...parseCodeBlocks(part.text));
				chartSpecs.push(...parseMermaidBlocks(part.text));
				continue;
			}
			if (part.type !== "tool-call") continue;
			const tool = part as ToolCallContentPart;
			switch (tool.toolName) {
				case "build_web_app":
					webAppResult = parseWebAppResult(tool.result);
					break;
				case "generate_image":
				case "display_image":
					images.push(tool);
					break;
				case "generate_report":
					reportPart = tool;
					break;
				case "generate_podcast":
				case "generate_video_presentation":
				case "generate_audio":
					media.push(tool);
					break;
				case "chainlens.research":
					researchPart = tool;
					break;
				case "generate_presentation":
					slidesPart = tool;
					break;
				default:
					// Capture other deliverable-looking tool calls as artifacts.
					if (tool.result !== undefined) artifacts.push(tool);
					break;
			}
		}
	}

	// Push tabs in the same order as DockHeader's TAB_ORDER so the default
	// active tab and the rendered tab order are consistent.
	if (options.hasLeads) {
		tabs.push({ id: "leads", label: "Leads", payload: { kind: "leads" } });
	}

	if (webAppResult?.app_id) {
		tabs.push({
			id: "web-builder",
			label: "Web Builder",
			payload: { kind: "web-builder", result: webAppResult },
		});
	}

	if (researchPart) {
		tabs.push({
			id: "research",
			label: "Research",
			payload: { kind: "research", report: parseResearchReport(researchPart.result) },
		});
		if (researchPart.result) {
			const report = parseResearchReport(researchPart.result);
			if (report && report.citations.length > 0) {
				tabs.push({
					id: "sources",
					label: "Sources",
					payload: { kind: "sources", citations: report.citations },
				});
			}
		}
	}

	if (reportPart) {
		tabs.push({ id: "reports", label: "Report", payload: { kind: "reports", part: reportPart } });
	}

	if (images.length > 0) {
		tabs.push({
			id: "images",
			label: images.length > 1 ? `Images (${images.length})` : "Image",
			payload: { kind: "images", parts: images },
		});
	}

	if (media.length > 0) {
		tabs.push({ id: "media", label: "Media", payload: { kind: "media", parts: media } });
	}

	if (chartSpecs.length > 0) {
		tabs.push({ id: "charts", label: "Charts", payload: { kind: "charts", specs: chartSpecs } });
	}

	if (codeBlocks.length > 0) {
		tabs.push({ id: "code", label: "Code", payload: { kind: "code", blocks: codeBlocks } });
	}

	if (artifacts.length > 0) {
		tabs.push({
			id: "artifacts",
			label: "Artifacts",
			payload: { kind: "artifacts", parts: artifacts },
		});
	}

	if (slidesPart) {
		tabs.push({
			id: "slides",
			label: "Slides",
			payload: { kind: "slides", result: slidesPart.result },
		});
	}

	return tabs;
}
