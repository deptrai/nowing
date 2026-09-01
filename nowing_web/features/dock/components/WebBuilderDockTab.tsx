"use client";

import {
	CheckIcon,
	CopyIcon,
	ExternalLinkIcon,
	FileCode2Icon,
	Laptop,
	Loader2Icon,
	RocketIcon,
	Smartphone,
	SparklesIcon,
	Tablet,
} from "lucide-react";
import { useMemo, useState } from "react";
import { toast } from "sonner";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { webBuilderApiService } from "@/lib/apis/web-builder-api.service";
import { buildBackendUrl } from "@/lib/env-config";
import { cn } from "@/lib/utils";
import type { WebAppBuildResult } from "../lib/parse-web-app-result";

export interface WebBuilderDockTabProps {
	workspaceId: number | string;
	result: Partial<WebAppBuildResult>;
}

type ViewportMode = "desktop" | "tablet" | "mobile";

export function WebBuilderDockTab({ workspaceId, result }: WebBuilderDockTabProps) {
	const appId = result.app_id;
	const appName = result.name || "Web App";
	const slug = result.slug;
	const files = result.files ?? [];
	const [isPublishing, setIsPublishing] = useState(false);
	const [publishedUrl, setPublishedUrl] = useState<string | null>(result.public_url ?? null);
	const [copied, setCopied] = useState(false);
	const [viewport, setViewport] = useState<ViewportMode>("desktop");

	const isPublished = result.status === "published" && Boolean(publishedUrl || result.public_url);
	const effectivePublicUrl = publishedUrl || result.public_url;

	const previewUrl = useMemo(() => {
		if (!appId) return "";
		return buildBackendUrl(`/api/v1/web-builder/apps/${appId}/preview?workspace_id=${workspaceId}`);
	}, [appId, workspaceId]);

	const handlePublish = async () => {
		if (!appId) {
			toast.error("Missing app ID for publishing");
			return;
		}
		setIsPublishing(true);
		try {
			const deployRes = await webBuilderApiService.publishWebApp(appId, {
				workspace_id: Number(workspaceId),
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

	const handleCopy = async () => {
		if (!effectivePublicUrl) return;
		try {
			await navigator.clipboard.writeText(effectivePublicUrl);
			setCopied(true);
			toast.success("Public URL copied");
			setTimeout(() => setCopied(false), 2000);
		} catch {
			toast.error("Failed to copy");
		}
	};

	const handleOpenLive = () => {
		if (!effectivePublicUrl) return;
		window.open(effectivePublicUrl, "_blank", "noopener,noreferrer");
	};

	if (!appId) {
		return (
			<div className="flex h-full items-center justify-center p-6 text-sm text-muted-foreground">
				No web app selected.
			</div>
		);
	}

	return (
		<div className="flex h-full flex-col min-h-0">
			{/* Header */}
			<div className="shrink-0 border-b border-border/80 px-3 py-2.5 bg-card/60 backdrop-blur-xs">
				<div className="flex items-start justify-between gap-2">
					<div className="min-w-0">
						<h3 className="truncate text-sm font-semibold text-foreground">{appName}</h3>
						{slug && (
							<p className="truncate text-[11px] font-mono text-muted-foreground">slug: {slug}</p>
						)}
					</div>
					<Badge
						variant="outline"
						className={cn(
							"shrink-0 text-[10px] font-medium capitalize",
							isPublished
								? "border-emerald-500/30 bg-emerald-500/10 text-emerald-700 dark:text-emerald-400"
								: "border-teal-500/30 bg-teal-500/10 text-teal-700 dark:text-teal-300"
						)}
					>
						{isPublished ? "Published" : "Generated"}
					</Badge>
				</div>

				{files.length > 0 && (
					<div className="mt-2 flex items-center gap-1.5 text-[11px] text-muted-foreground">
						<FileCode2Icon className="size-3.5" aria-hidden="true" />
						<span>
							{files.length} file{files.length === 1 ? "" : "s"}
						</span>
					</div>
				)}

				<div className="mt-3 flex flex-wrap items-center justify-between gap-2">
					<div className="flex flex-wrap items-center gap-2">
						{!isPublished && (
							<Button
								type="button"
								size="sm"
								disabled={isPublishing}
								onClick={handlePublish}
								className="gap-1 text-xs h-7 rounded-lg bg-teal-600 hover:bg-teal-500 text-white"
							>
								{isPublishing ? (
									<Loader2Icon className="size-3.5 animate-spin" aria-hidden="true" />
								) : (
									<RocketIcon className="size-3.5" aria-hidden="true" />
								)}
								{isPublishing ? "Publishing..." : "Publish"}
							</Button>
						)}

						{isPublished && effectivePublicUrl && (
							<Button
								type="button"
								size="sm"
								onClick={handleOpenLive}
								className="gap-1 text-xs h-7 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white"
							>
								<ExternalLinkIcon className="size-3.5" aria-hidden="true" />
								Live Site
							</Button>
						)}

						{isPublished && effectivePublicUrl && (
							<Button
								type="button"
								variant="outline"
								size="sm"
								onClick={handleCopy}
								className="gap-1 text-xs h-7 rounded-lg"
							>
								{copied ? (
									<CheckIcon className="size-3.5" aria-hidden="true" />
								) : (
									<CopyIcon className="size-3.5" aria-hidden="true" />
								)}
								Copy URL
							</Button>
						)}

						<Button
							type="button"
							variant="outline"
							size="sm"
							className="gap-1 text-xs h-7 rounded-lg"
							onClick={() => toast.info("Code editor tab coming in next iteration.")}
						>
							<SparklesIcon className="size-3.5" aria-hidden="true" />
							Edit Prompt
						</Button>
					</div>

					{/* Device Viewport Selector */}
					<div className="flex items-center gap-0.5 rounded-lg border border-border/80 bg-muted/50 p-0.5">
						<button
							type="button"
							onClick={() => setViewport("desktop")}
							title="Toàn màn hình Desktop (100%)"
							className={cn(
								"flex items-center gap-1 rounded-md px-2 py-1 text-[11px] font-medium transition-all",
								viewport === "desktop"
									? "bg-background text-foreground shadow-2xs font-semibold"
									: "text-muted-foreground hover:text-foreground"
							)}
						>
							<Laptop className="size-3.5" />
							<span className="hidden sm:inline">Desktop</span>
						</button>
						<button
							type="button"
							onClick={() => setViewport("tablet")}
							title="Tablet Viewport (768px)"
							className={cn(
								"flex items-center gap-1 rounded-md px-2 py-1 text-[11px] font-medium transition-all",
								viewport === "tablet"
									? "bg-background text-foreground shadow-2xs font-semibold"
									: "text-muted-foreground hover:text-foreground"
							)}
						>
							<Tablet className="size-3.5" />
							<span className="hidden sm:inline">Tablet</span>
						</button>
						<button
							type="button"
							onClick={() => setViewport("mobile")}
							title="Mobile Viewport (375px)"
							className={cn(
								"flex items-center gap-1 rounded-md px-2 py-1 text-[11px] font-medium transition-all",
								viewport === "mobile"
									? "bg-background text-foreground shadow-2xs font-semibold"
									: "text-muted-foreground hover:text-foreground"
							)}
						>
							<Smartphone className="size-3.5" />
							<span className="hidden sm:inline">Mobile</span>
						</button>
					</div>
				</div>

				{isPublished && effectivePublicUrl && (
					<div className="mt-2 rounded-md border border-emerald-500/20 bg-emerald-500/5 px-2 py-1.5">
						<p className="text-[10px] font-semibold uppercase tracking-wider text-emerald-800 dark:text-emerald-300">
							Public URL
						</p>
						<a
							href={effectivePublicUrl}
							target="_blank"
							rel="noopener noreferrer"
							className="block truncate text-[11px] font-medium text-emerald-700 dark:text-emerald-400 hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-500"
						>
							{effectivePublicUrl}
						</a>
					</div>
				)}
			</div>

			{/* Preview Viewport Container */}
			<div className="flex-1 min-h-0 bg-neutral-950 flex flex-col items-center justify-center p-3 overflow-hidden relative">
				{previewUrl ? (
					<div
						className={cn(
							"h-full transition-all duration-300 ease-out flex flex-col rounded-xl overflow-hidden border border-border/40 shadow-xl bg-slate-950",
							viewport === "desktop" && "w-full",
							viewport === "tablet" && "w-[768px] max-w-full",
							viewport === "mobile" && "w-[375px] max-w-full"
						)}
					>
						{viewport !== "desktop" && (
							<div className="h-6 bg-neutral-900 border-b border-border/40 px-3 flex items-center justify-between text-[10px] text-muted-foreground select-none">
								<span className="font-mono">{viewport === "tablet" ? "768 × 1024" : "375 × 812"}</span>
								<span className="uppercase tracking-widest">{viewport} preview</span>
							</div>
						)}
						<iframe
							src={previewUrl}
							title={appName}
							sandbox="allow-scripts allow-forms allow-same-origin"
							className="w-full flex-1 border-0 bg-slate-950"
						/>
					</div>
				) : (
					<div className="text-sm text-muted-foreground">No preview available.</div>
				)}
			</div>
		</div>
	);
}

