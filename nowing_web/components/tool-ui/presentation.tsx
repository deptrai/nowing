"use client";

import type { ToolCallMessagePartProps } from "@assistant-ui/react";
import {
	AlertCircleIcon,
	DownloadIcon,
	ExternalLinkIcon,
	Loader2Icon,
	PresentationIcon,
} from "lucide-react";
import { useParams } from "next/navigation";
import { useMemo } from "react";
import { TextShimmerLoader } from "@/components/prompt-kit/loader";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { presentationApiService } from "@/lib/apis/presentation-api.service";
import { getWorkspaceIdNumber } from "@/lib/route-params";

export const PresentationBuildArgsSchema = {
	prompt: "",
	output_format: "pptx",
	language: "en",
};

export const PresentationBuildResultSchema = {
	status: "",
	presentation_id: "",
	workspace_id: 0,
	title: "",
	slug: "",
	format: "pptx",
	slide_count: 0,
	download_url: "",
	preview_url: "",
	error: "",
	degradation_reason: "",
};

export type PresentationBuildArgs = {
	prompt?: string;
	output_format?: string;
	language?: string;
};

export type PresentationBuildResult = {
	status?: string;
	presentation_id?: string;
	workspace_id?: number;
	title?: string;
	slug?: string;
	format?: string;
	slide_count?: number;
	download_url?: string;
	preview_url?: string;
	error?: string;
	degradation_reason?: string;
};

function parseToolResult(raw: unknown): Partial<PresentationBuildResult> {
	if (typeof raw === "object" && raw !== null) {
		return raw as Partial<PresentationBuildResult>;
	}
	if (typeof raw === "string") {
		try {
			const parsed = JSON.parse(raw);
			if (typeof parsed === "object" && parsed !== null) {
				return parsed as Partial<PresentationBuildResult>;
			}
		} catch {
			return { error: raw, status: "error" };
		}
	}
	return {};
}

export function GeneratePresentationToolUI({
	args,
	result: rawResult,
	status,
}: ToolCallMessagePartProps<PresentationBuildArgs, PresentationBuildResult | string>) {
	const params = useParams();
	const workspaceId = getWorkspaceIdNumber(params) || 1;

	const result = useMemo(() => parseToolResult(rawResult), [rawResult]);

	const isRunning = status.type === "running" || status.type === "requires-action";
	const isFailed =
		result.status === "validation_failed" ||
		result.status === "error" ||
		result.status === "failed" ||
		Boolean(result.error);

	const title = result.title || args.prompt || "Slide Deck";
	const prompt = args.prompt;
	const presentationId = result.presentation_id;
	const format = result.format || "pptx";
	const slideCount = result.slide_count ?? 0;
	const downloadUrl =
		result.download_url ||
		(presentationId ? presentationApiService.downloadUrl(presentationId, workspaceId) : "");
	const previewUrl =
		result.preview_url ||
		(presentationId ? presentationApiService.previewUrl(presentationId, workspaceId) : "");

	if (isRunning || (!result.presentation_id && !isFailed)) {
		return (
			<div className="my-4 max-w-xl overflow-hidden rounded-2xl border border-border/80 bg-card p-5 shadow-sm select-none">
				<div className="flex items-center gap-3">
					<div className="flex size-9 shrink-0 items-center justify-center rounded-xl bg-purple-500/10 text-purple-600 dark:text-purple-400">
						<PresentationIcon className="size-4.5" aria-hidden="true" />
					</div>
					<div className="min-w-0">
						<h4 className="truncate text-sm font-semibold text-foreground">{title}</h4>
						<TextShimmerLoader text="Designing your slides…" size="sm" />
					</div>
					<Badge variant="secondary" className="ml-auto gap-1 px-2 py-0.5 text-xs">
						<Loader2Icon className="size-3 animate-spin text-muted-foreground" aria-hidden="true" />
						Generating
					</Badge>
				</div>
				{prompt && (
					<p className="mt-3 truncate text-xs text-muted-foreground italic">
						Prompt: &ldquo;{prompt}&rdquo;
					</p>
				)}
			</div>
		);
	}

	if (isFailed) {
		return (
			<div className="my-4 max-w-xl overflow-hidden rounded-2xl border border-destructive/20 bg-destructive/5 p-5 shadow-sm">
				<div className="flex items-center gap-3">
					<div className="flex size-9 shrink-0 items-center justify-center rounded-xl bg-destructive/10 text-destructive">
						<AlertCircleIcon className="size-5" aria-hidden="true" />
					</div>
					<div className="min-w-0 flex-1">
						<h4 className="truncate text-sm font-semibold text-destructive">
							Slide Deck Generation Failed
						</h4>
						<p className="mt-0.5 text-xs text-muted-foreground line-clamp-2">
							{result.error || "Unable to generate the requested slide deck."}
						</p>
					</div>
				</div>
			</div>
		);
	}

	const isDegraded = result.status === "degraded" || Boolean(result.degradation_reason);

	return (
		<div className="my-4 max-w-xl overflow-hidden rounded-2xl border border-border/80 bg-card p-5 shadow-sm transition-all hover:border-border">
			<div className="flex items-start justify-between gap-3">
				<div className="flex items-center gap-3 min-w-0">
					<div className="flex size-10 shrink-0 items-center justify-center rounded-xl bg-purple-500/10 text-purple-600 dark:text-purple-400">
						<PresentationIcon className="size-5" aria-hidden="true" />
					</div>
					<div className="min-w-0">
						<h4 className="truncate text-sm font-bold text-foreground">{title}</h4>
						<p className="truncate text-xs text-muted-foreground">
							{slideCount > 0 ? `${slideCount} slide${slideCount === 1 ? "" : "s"}` : "Slide deck"}{" "}
							· {format.toUpperCase()}
						</p>
					</div>
				</div>
				<Badge
					variant="outline"
					className="shrink-0 font-medium text-xs capitalize border-purple-500/30 bg-purple-500/10 text-purple-700 dark:text-purple-300"
				>
					{isDegraded ? "Degraded" : "Ready"}
				</Badge>
			</div>

			{isDegraded && (
				<p className="mt-3 text-xs text-muted-foreground">
					{format === "marp"
						? "Open this file in Marp for VS Code / Marp Web."
						: "Preview is not available for this deck."}
				</p>
			)}

			<div className="mt-4 flex flex-wrap items-center gap-2 pt-2 border-t border-border/60">
				{downloadUrl && (
					<Button
						type="button"
						variant="outline"
						size="sm"
						asChild
						className="gap-1.5 text-xs font-semibold rounded-xl"
					>
						<a href={downloadUrl} download rel="noopener noreferrer">
							<DownloadIcon className="size-3.5" aria-hidden="true" />
							Download .{format}
						</a>
					</Button>
				)}

				{previewUrl && (
					<Button
						type="button"
						variant="outline"
						size="sm"
						asChild
						className="gap-1.5 text-xs font-semibold rounded-xl"
					>
						<a href={previewUrl} target="_blank" rel="noopener noreferrer">
							<ExternalLinkIcon className="size-3.5" aria-hidden="true" />
							Preview
						</a>
					</Button>
				)}
			</div>
		</div>
	);
}
