"use client";

import type { ToolCallMessagePartProps } from "@assistant-ui/react";
import {
	AlertCircleIcon,
	CheckIcon,
	CopyIcon,
	ExternalLinkIcon,
	FileCode2Icon,
	GlobeIcon,
	Loader2Icon,
	RocketIcon,
	SparklesIcon,
} from "lucide-react";
import { useParams, useRouter } from "next/navigation";
import { useMemo, useState } from "react";
import { toast } from "sonner";
import { z } from "zod";
import { TextShimmerLoader } from "@/components/prompt-kit/loader";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { webBuilderApiService } from "@/lib/apis/web-builder-api.service";
import { getWorkspaceIdNumber } from "@/lib/route-params";
import { cn } from "@/lib/utils";

// ============================================================================
// Schemas & Types
// ============================================================================

export const WebAppBuildArgsSchema = z.object({
	prompt: z.string().optional(),
	app_name: z.string().nullish(),
	language: z.string().nullish(),
});

export const WebAppBuildResultSchema = z.object({
	app_id: z.string().optional(),
	workspace_id: z.number().optional(),
	name: z.string().optional(),
	slug: z.string().optional(),
	status: z.string().optional(),
	preview_url: z.string().nullish(),
	public_url: z.string().nullish(),
	message: z.string().nullish(),
	files: z.array(z.string()).nullish(),
	error: z.string().nullish(),
});

export type WebAppBuildArgs = z.infer<typeof WebAppBuildArgsSchema>;
export type WebAppBuildResult = z.infer<typeof WebAppBuildResultSchema>;

function parseToolResult(raw: unknown): Partial<WebAppBuildResult> {
	if (typeof raw === "object" && raw !== null) {
		return raw as Partial<WebAppBuildResult>;
	}
	if (typeof raw === "string") {
		try {
			const parsed = JSON.parse(raw);
			if (typeof parsed === "object" && parsed !== null) {
				return parsed as Partial<WebAppBuildResult>;
			}
		} catch {
			return { message: raw, error: raw, status: "error" };
		}
	}
	return {};
}

// ============================================================================
// Subcomponents
// ============================================================================

function WebAppGeneratingState({ prompt, appName }: { prompt?: string; appName?: string }) {
	return (
		<div className="my-4 max-w-xl overflow-hidden rounded-2xl border border-border/80 bg-card p-5 shadow-sm select-none">
			<div className="flex items-center justify-between gap-3">
				<div className="flex items-center gap-2.5 min-w-0">
					<div className="flex size-9 shrink-0 items-center justify-center rounded-xl bg-pink-500/10 text-pink-600 dark:text-pink-400">
						<GlobeIcon className="size-4.5" />
					</div>
					<div className="min-w-0">
						<h4 className="truncate text-sm font-semibold text-foreground">
							{appName || "Generating Web App"}
						</h4>
						<TextShimmerLoader text="Designing & scaffolding Next.js page..." size="sm" />
					</div>
				</div>
				<Badge variant="secondary" className="gap-1 px-2 py-0.5 text-xs">
					<Loader2Icon className="size-3 animate-spin text-muted-foreground" />
					Building
				</Badge>
			</div>

			<div className="mt-4 space-y-2 rounded-xl border border-dashed border-border/70 bg-muted/20 p-4">
				<div className="h-3.5 w-3/4 rounded bg-muted/60 animate-pulse" />
				<div className="h-3 w-1/2 rounded bg-muted/50 animate-pulse [animation-delay:150ms]" />
				<div className="mt-3 flex gap-2">
					<div className="h-6 w-16 rounded-md bg-muted/60 animate-pulse [animation-delay:300ms]" />
					<div className="h-6 w-20 rounded-md bg-muted/40 animate-pulse [animation-delay:450ms]" />
				</div>
			</div>

			{prompt && (
				<p className="mt-3 truncate text-xs text-muted-foreground italic">
					Prompt: &ldquo;{prompt}&rdquo;
				</p>
			)}
		</div>
	);
}

function WebAppErrorState({
	title,
	error,
	prompt,
}: {
	title: string;
	error: string;
	prompt?: string;
}) {
	return (
		<div className="my-4 max-w-xl overflow-hidden rounded-2xl border border-destructive/20 bg-destructive/5 p-5 shadow-sm">
			<div className="flex items-center gap-3">
				<div className="flex size-9 shrink-0 items-center justify-center rounded-xl bg-destructive/10 text-destructive">
					<AlertCircleIcon className="size-5" />
				</div>
				<div className="min-w-0 flex-1">
					<h4 className="truncate text-sm font-semibold text-destructive">
						Web App Generation Failed {title ? `— ${title}` : ""}
					</h4>
					<p className="mt-0.5 text-xs text-muted-foreground line-clamp-2">{error}</p>
				</div>
			</div>
			{prompt && (
				<p className="mt-3 border-t border-destructive/10 pt-2 text-xs text-muted-foreground truncate">
					Request: {prompt}
				</p>
			)}
		</div>
	);
}

// ============================================================================
// Main Tool UI Component
// ============================================================================

export function GenerateWebAppToolUI({
	args,
	result: rawResult,
	status,
}: ToolCallMessagePartProps<WebAppBuildArgs, WebAppBuildResult | string>) {
	const params = useParams();
	const router = useRouter();
	const workspaceId = getWorkspaceIdNumber(params) || 1;

	const result = useMemo(() => parseToolResult(rawResult), [rawResult]);

	const [isPublishing, setIsPublishing] = useState(false);
	const [publishedUrl, setPublishedUrl] = useState<string | null>(() => result.public_url ?? null);
	const [copied, setCopied] = useState(false);

	const isRunning = status.type === "running" || status.type === "requires-action";
	const isFailed =
		result.status === "validation_failed" ||
		result.status === "error" ||
		result.status === "build_failed" ||
		result.status === "deploy_failed" ||
		Boolean(result.error) ||
		Boolean(result.message && !result.app_id);

	const appName = result.name || args.app_name || "Sales & Marketing Web App";
	const prompt = args.prompt;
	const appId = result.app_id;
	const slug = result.slug;
	const files = result.files ?? [];

	const effectivePublicUrl = publishedUrl || result.public_url;
	const isPublished = result.status === "published" && Boolean(effectivePublicUrl);

	const handlePublish = async () => {
		if (!appId) {
			toast.error("Missing app ID for publishing");
			return;
		}

		setIsPublishing(true);
		try {
			const deployRes = await webBuilderApiService.publishWebApp(appId, {
				workspace_id: workspaceId,
			});

			if (deployRes.status === "published" && deployRes.public_url) {
				setPublishedUrl(deployRes.public_url);
				toast.success("Web app published successfully!", {
					description: `Live at ${deployRes.public_url}`,
				});
			} else {
				toast.error(deployRes.message || "Failed to publish web app");
			}
		} catch (err: unknown) {
			const msg = err instanceof Error ? err.message : "Publish request failed";
			toast.error(msg);
		} finally {
			setIsPublishing(false);
		}
	};

	const handleCopyPublicUrl = async () => {
		if (!effectivePublicUrl) return;
		try {
			await navigator.clipboard.writeText(effectivePublicUrl);
			setCopied(true);
			toast.success("Public URL copied to clipboard");
			setTimeout(() => setCopied(false), 2000);
		} catch {
			toast.error("Failed to copy public URL");
		}
	};

	const handleOpenEditor = () => {
		if (!appId) return;
		router.push(`/dashboard/${workspaceId}/web-builder?app_id=${appId}`);
	};

	const handleOpenLive = () => {
		if (!effectivePublicUrl) return;
		window.open(effectivePublicUrl, "_blank", "noopener,noreferrer");
	};

	// 1. Generating State
	if (isRunning || (!result.app_id && !isFailed)) {
		return <WebAppGeneratingState prompt={prompt} appName={appName} />;
	}

	// 2. Error State
	if (isFailed) {
		const errorMessage =
			result.error || result.message || "Unable to generate the requested web application.";
		return <WebAppErrorState title={appName} error={errorMessage} prompt={prompt} />;
	}

	// 3. Published / Generated State
	return (
		<div className="my-4 max-w-xl overflow-hidden rounded-2xl border border-border/80 bg-card p-5 shadow-sm transition-all hover:border-border">
			{/* Card Header */}
			<div className="flex items-start justify-between gap-3">
				<div className="flex items-center gap-3 min-w-0">
					<div
						className={cn(
							"flex size-10 shrink-0 items-center justify-center rounded-xl",
							isPublished
								? "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400"
								: "bg-teal-500/10 text-teal-600 dark:text-teal-400"
						)}
					>
						{isPublished ? <RocketIcon className="size-5" /> : <GlobeIcon className="size-5" />}
					</div>
					<div className="min-w-0">
						<div className="flex items-center gap-2">
							<h4 className="truncate text-sm font-bold text-foreground">{appName}</h4>
						</div>
						{slug && (
							<p className="truncate text-xs font-mono text-muted-foreground">slug: {slug}</p>
						)}
					</div>
				</div>

				<Badge
					variant="outline"
					className={cn(
						"shrink-0 font-medium text-xs capitalize",
						isPublished
							? "border-emerald-500/30 bg-emerald-500/10 text-emerald-700 dark:text-emerald-400"
							: "border-teal-500/30 bg-teal-500/10 text-teal-700 dark:text-teal-300"
					)}
				>
					{isPublished ? "Published" : "Generated"}
				</Badge>
			</div>

			{/* Published Public URL Banner */}
			{isPublished && effectivePublicUrl && (
				<div className="mt-4 flex items-center justify-between gap-2 rounded-xl border border-emerald-500/20 bg-emerald-500/5 dark:bg-emerald-500/10 p-3">
					<div className="min-w-0 flex-1">
						<p className="text-[11px] font-semibold text-emerald-800 dark:text-emerald-300 uppercase tracking-wider">
							Public URL
						</p>
						<a
							href={effectivePublicUrl}
							target="_blank"
							rel="noopener noreferrer"
							className="truncate text-xs font-medium text-emerald-700 dark:text-emerald-400 hover:underline block"
						>
							{effectivePublicUrl}
						</a>
					</div>
					<div className="flex items-center gap-1 shrink-0">
						<Button
							type="button"
							variant="ghost"
							size="icon"
							onClick={handleCopyPublicUrl}
							className="size-7 rounded-lg text-emerald-700 dark:text-emerald-300 hover:bg-emerald-500/10"
							title="Copy URL"
						>
							{copied ? <CheckIcon className="size-3.5" /> : <CopyIcon className="size-3.5" />}
							<span className="sr-only">Copy public URL</span>
						</Button>
						<Button
							type="button"
							variant="ghost"
							size="icon"
							onClick={handleOpenLive}
							className="size-7 rounded-lg text-emerald-700 dark:text-emerald-300 hover:bg-emerald-500/10"
							title="Open site"
						>
							<ExternalLinkIcon className="size-3.5" />
							<span className="sr-only">Open live website</span>
						</Button>
					</div>
				</div>
			)}

			{/* Project Files Summary */}
			{files.length > 0 && (
				<div className="mt-3.5 flex items-center gap-2 text-xs text-muted-foreground">
					<FileCode2Icon className="size-3.5 shrink-0" />
					<span className="truncate">
						{files.length} project file{files.length === 1 ? "" : "s"} generated
					</span>
				</div>
			)}

			{/* Action CTA Buttons */}
			<div className="mt-4 flex flex-wrap items-center gap-2 pt-2 border-t border-border/60">
				{appId && (
					<Button
						type="button"
						variant="outline"
						size="sm"
						onClick={handleOpenEditor}
						className="gap-1.5 text-xs font-semibold rounded-xl"
					>
						<SparklesIcon className="size-3.5" />
						Open Editor
					</Button>
				)}

				{!isPublished && (
					<Button
						type="button"
						size="sm"
						disabled={isPublishing}
						onClick={handlePublish}
						className="gap-1.5 text-xs font-semibold rounded-xl bg-teal-600 hover:bg-teal-500 text-white shadow-xs transition-colors"
					>
						{isPublishing ? (
							<>
								<Loader2Icon className="size-3.5 animate-spin" />
								Publishing...
							</>
						) : (
							<>
								<RocketIcon className="size-3.5" />
								Publish
							</>
						)}
					</Button>
				)}

				{isPublished && effectivePublicUrl && (
					<Button
						type="button"
						size="sm"
						onClick={handleOpenLive}
						className="gap-1.5 text-xs font-semibold rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white shadow-xs transition-colors"
					>
						<ExternalLinkIcon className="size-3.5" />
						Visit Live Site
					</Button>
				)}
			</div>
		</div>
	);
}
