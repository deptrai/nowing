"use client";

import {
	AlertTriangle,
	CheckIcon,
	ChevronDownIcon,
	Database,
	Globe,
	XCircleIcon,
} from "lucide-react";
import { useMemo, useState } from "react";
import { NestedScroll } from "@/components/assistant-ui/nested-scroll";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible";
import { Separator } from "@/components/ui/separator";
import { Spinner } from "@/components/ui/spinner";
import { getToolDisplayName } from "@/contracts/enums/toolIcons";
import { cn } from "@/lib/utils";
import type { TimelineToolComponent } from "../types";
import { ToolCardRevertButton } from "./revert-button";

/**
 * Best-effort error/cancellation reason from a tool result. Used as
 * the card subtitle when ``status`` is "error" or "cancelled". Returns
 * ``null`` if no usable text can be extracted.
 *
 * Tries: plain string → ``result.error`` → ``result.message`` →
 * stringified result. Per-tool components own richer error UIs; this
 * is the generic fallback's coarse summary.
 */
function deriveResultMessage(result: unknown): string | null {
	if (result == null) return null;
	if (typeof result === "string") return result;
	if (typeof result !== "object") return null;
	const r = result as { error?: unknown; message?: unknown };
	if (typeof r.error === "string") return r.error;
	if (typeof r.message === "string") return r.message;
	try {
		return JSON.stringify(result);
	} catch {
		return null;
	}
}

interface ResearchSource {
	title?: string;
	url?: string;
	content?: string;
	source_type?: string;
	document_id?: number;
	chunk_id?: number;
}

interface ResearchResult {
	status?: "complete" | "partial" | "timeout" | "insufficient_evidence" | "engine_unavailable";
	degraded?: boolean;
	degradation_reason?: string;
	next_action?: string;
	answer?: string;
	sources?: ResearchSource[];
}

function asResearchResult(result: unknown): ResearchResult | undefined {
	if (typeof result !== "object" || result === null) return undefined;
	const r = result as Record<string, unknown>;
	if (r.degraded !== true && typeof r.status !== "string") return undefined;
	if (!("answer" in r) && !("sources" in r) && r.degraded !== true) return undefined;
	return r as ResearchResult;
}

function isChainlensResearchTool(toolName: string): boolean {
	return toolName === "chainlens_research" || toolName === "chainlens.research";
}

function researchBadge(result: ResearchResult): string {
	switch (result.status) {
		case "engine_unavailable":
			return "Engine unavailable";
		case "partial":
			return "Partial result";
		case "insufficient_evidence":
			return "No sources";
		case "timeout":
			return "Timed out";
		default:
			return result.degraded ? "Degraded" : "Completed";
	}
}

function researchSubtitle(result: ResearchResult): string | null {
	if (result.next_action) return result.next_action;
	switch (result.status) {
		case "engine_unavailable":
			return result.degradation_reason === "fallback_kb_hits"
				? "Engine unavailable — showing workspace knowledge base fallback"
				: "The deep research engine is unavailable";
		case "partial":
			return "Partial result — some sources could not be verified";
		case "insufficient_evidence":
			return "No relevant sources were found";
		case "timeout":
			return "The research stream timed out";
		default:
			return null;
	}
}

function ResearchResultView({ result }: { result: ResearchResult }) {
	return (
		<div className="flex flex-col gap-3">
			{result.answer && (
				<div className="flex flex-col gap-1 min-w-0">
					<p className="text-xs font-medium text-muted-foreground">Answer</p>
					<NestedScroll className="max-h-48 overflow-auto rounded-md bg-muted/40">
						<p className="px-3 py-2 text-sm text-foreground/80 whitespace-pre-wrap">
							{result.answer}
						</p>
					</NestedScroll>
				</div>
			)}
			{result.sources && result.sources.length > 0 && (
				<div className="flex flex-col gap-1.5 min-w-0">
					<p className="text-xs font-medium text-muted-foreground">
						{result.sources.some((s) => s.source_type === "kb" || s.url?.startsWith("nowing://"))
							? "Workspace knowledge base sources"
							: "Sources"}
					</p>
					<div className="flex flex-col gap-2">
						{result.sources.map((source, idx) => {
							const isKb = source.source_type === "kb" || source.url?.startsWith("nowing://");
							const title = source.title || `Source ${idx + 1}`;
							return (
								<div
									key={source.url || `${title}-${idx}`}
									className="flex items-start gap-2 rounded-md bg-muted/40 px-3 py-2"
								>
									{isKb ? (
										<Database
											className="size-3.5 shrink-0 text-muted-foreground mt-0.5"
											aria-hidden="true"
										/>
									) : (
										<Globe
											className="size-3.5 shrink-0 text-muted-foreground mt-0.5"
											aria-hidden="true"
										/>
									)}
									<div className="flex min-w-0 flex-col gap-0.5">
										{source.url && !isKb ? (
											<a
												href={source.url}
												target="_blank"
												rel="noopener noreferrer"
												className="text-xs font-medium text-foreground hover:underline break-all"
											>
												{title}
											</a>
										) : (
											<span className="text-xs font-medium text-foreground break-all">{title}</span>
										)}
										{source.content && (
											<p className="text-xs text-muted-foreground line-clamp-2">{source.content}</p>
										)}
										{isKb && (
											<span className="text-[10px] text-muted-foreground uppercase tracking-wider">
												Workspace KB
											</span>
										)}
									</div>
								</div>
							);
						})}
					</div>
				</div>
			)}
		</div>
	);
}

/**
 * Compact tool-call card. Used by ``FallbackToolBody`` for unregistered
 * tools whose result is not an HITL interrupt.
 *
 * shadcn composition note: ``Card`` is used as a visual frame WITHOUT
 * ``CardHeader``/``CardContent`` — the full composition's ``p-6``
 * doesn't fit a compact collapsible header that IS the trigger.
 *
 * Per-card expansion auto-syncs to ``isRunning`` (auto-expand on
 * stream start, auto-collapse on completion); manual toggle takes over
 * once streaming ends.
 */
export const DefaultFallbackCard: TimelineToolComponent = ({
	toolCallId,
	toolName,
	argsText,
	result,
	status,
	langchainToolCallId,
	progress,
	degraded,
}) => {
	const isCancelled = status === "cancelled";
	const isError = status === "error";
	const isRunning = status === "running";
	const liveProgress = isRunning ? (progress ?? []) : [];

	const researchResult = useMemo(() => asResearchResult(result), [result]);
	const isResearchCard = isChainlensResearchTool(toolName) && researchResult != null;
	const isDegraded =
		degraded === true ||
		(isResearchCard &&
			(researchResult.degraded === true ||
				(researchResult.status != null && researchResult.status !== "complete")));

	const [isExpanded, setIsExpanded] = useState(false);

	const serializedResult = useMemo(
		() =>
			result !== undefined && typeof result !== "string" ? JSON.stringify(result, null, 2) : null,
		[result]
	);

	const subtitle = useMemo(() => {
		if (isError || isCancelled) return deriveResultMessage(result);
		if (isDegraded && researchResult) return researchSubtitle(researchResult);
		// While running, surface the latest streamed activity line so progress
		// is visible even when the card is collapsed.
		if (isRunning && liveProgress.length > 0) return liveProgress[liveProgress.length - 1];
		return null;
	}, [isError, isCancelled, isDegraded, isRunning, liveProgress, result, researchResult]);

	const displayName = getToolDisplayName(toolName);

	return (
		<Card
			className={cn(
				"my-2 max-w-lg overflow-hidden",
				isCancelled && "opacity-60",
				isError && "border-destructive/30",
				isDegraded && "border-amber-500/50"
			)}
		>
			<Collapsible className="group" open={isExpanded} onOpenChange={setIsExpanded}>
				<div className="flex items-stretch transition-colors hover:bg-accent hover:text-accent-foreground">
					<CollapsibleTrigger asChild>
						<Button
							variant="ghost"
							type="button"
							className={cn(
								"h-auto flex-1 min-w-0 justify-start gap-2.5 rounded-none py-2.5 pl-3.5 pr-2 text-left font-normal hover:bg-transparent",
								"focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-inset",
								"disabled:cursor-default"
							)}
						>
							<div
								className={cn(
									"flex size-6 shrink-0 items-center justify-center rounded-md",
									isError
										? "bg-destructive/10"
										: isDegraded
											? "bg-amber-500/10"
											: isCancelled
												? "bg-muted"
												: "bg-primary/10"
								)}
							>
								{isError ? (
									<XCircleIcon className="size-3.5 text-destructive" aria-hidden="true" />
								) : isDegraded ? (
									<AlertTriangle className="size-3.5 text-amber-600" aria-hidden="true" />
								) : isCancelled ? (
									<XCircleIcon className="size-3.5 text-muted-foreground" aria-hidden="true" />
								) : isRunning ? (
									<Spinner size="sm" className="text-primary" />
								) : (
									<CheckIcon className="size-3.5 text-primary" aria-hidden="true" />
								)}
							</div>

							<div className="flex flex-1 min-w-0 flex-col gap-0.5">
								<div className="flex items-center gap-1.5">
									<p
										className={cn(
											"text-[11.5px] font-medium truncate",
											isCancelled && "text-muted-foreground line-through",
											isError && "text-destructive",
											isDegraded && "text-amber-600 dark:text-amber-400"
										)}
									>
										{displayName}
									</p>
									{isRunning && (
										<Badge variant="secondary" className="px-1.5 py-0 text-[10px]">
											Running
										</Badge>
									)}
									{isError && (
										<Badge variant="destructive" className="px-1.5 py-0 text-[10px]">
											Failed
										</Badge>
									)}
									{isCancelled && (
										<Badge variant="outline" className="px-1.5 py-0 text-[10px]">
											Cancelled
										</Badge>
									)}
									{isDegraded && researchResult && (
										<Badge
											variant="secondary"
											className="bg-amber-500/10 text-amber-700 border-amber-500/20 dark:text-amber-400 px-1.5 py-0 text-[10px]"
										>
											{researchBadge(researchResult)}
										</Badge>
									)}
								</div>
								{subtitle && (
									<p
										className={cn(
											"text-[10.5px] truncate",
											isError
												? "text-destructive/80"
												: isDegraded
													? "text-amber-600/80 dark:text-amber-400/80"
													: "text-muted-foreground"
										)}
									>
										{subtitle}
									</p>
								)}
							</div>
						</Button>
					</CollapsibleTrigger>

					<div className="flex shrink-0 items-center gap-1.5 pl-1.5 pr-3">
						<ToolCardRevertButton
							toolCallId={toolCallId}
							toolName={toolName}
							langchainToolCallId={langchainToolCallId}
						/>
						<CollapsibleTrigger asChild>
							<Button
								type="button"
								variant="ghost"
								size="icon"
								aria-label={isExpanded ? "Collapse details" : "Expand details"}
								className="size-6 shrink-0"
							>
								<ChevronDownIcon
									className={cn(
										"size-3.5 transition-transform duration-200",
										"group-data-[state=open]:rotate-180"
									)}
								/>
							</Button>
						</CollapsibleTrigger>
					</div>
				</div>

				<CollapsibleContent>
					<Separator />
					<div className="flex flex-col gap-3 px-5 py-3">
						{(argsText || isRunning) && (
							<div className="flex flex-col gap-1 min-w-0">
								<p className="text-xs font-medium text-muted-foreground">Inputs</p>
								<NestedScroll className="max-h-48 overflow-auto rounded-md bg-muted/40">
									{argsText ? (
										<pre className="px-3 py-2 text-xs text-foreground/80 whitespace-pre-wrap break-all font-mono">
											{argsText}
										</pre>
									) : (
										<p className="px-3 py-2 text-xs italic text-muted-foreground">
											Waiting for input…
										</p>
									)}
								</NestedScroll>
							</div>
						)}
						{isRunning && liveProgress.length > 0 && (
							<>
								<Separator />
								<div className="flex flex-col gap-1 min-w-0">
									<p className="text-xs font-medium text-muted-foreground">Progress</p>
									<div className="flex flex-col gap-1.5 rounded-md bg-muted/40 px-3 py-2">
										{liveProgress.map((line) => (
											<div
												key={line}
												className="flex items-center gap-2 text-xs text-foreground/80"
											>
												<Spinner size="sm" className="shrink-0 text-primary" />
												<span className="min-w-0 wrap-break-word">{line}</span>
											</div>
										))}
									</div>
								</div>
							</>
						)}
						{!isCancelled && result !== undefined && (
							<>
								<Separator />
								<div className="flex flex-col gap-1 min-w-0">
									<p className="text-xs font-medium text-muted-foreground">Result</p>
									{isResearchCard && researchResult ? (
										<NestedScroll className="max-h-96 overflow-auto rounded-md bg-muted/40 px-3 py-2">
											<ResearchResultView result={researchResult} />
										</NestedScroll>
									) : (
										<NestedScroll className="max-h-64 overflow-auto rounded-md bg-muted/40">
											<pre className="px-3 py-2 text-xs text-foreground/80 whitespace-pre-wrap break-all font-mono">
												{typeof result === "string" ? result : serializedResult}
											</pre>
										</NestedScroll>
									)}
								</div>
							</>
						)}
					</div>
				</CollapsibleContent>
			</Collapsible>
		</Card>
	);
};
