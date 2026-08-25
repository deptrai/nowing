"use client";

import {
	Download,
	ExternalLink,
	FileText,
	ImageIcon,
	Music,
	Presentation,
	Wrench,
} from "lucide-react";
import { useTheme } from "next-themes";
import { MarkdownCodeBlock } from "@/components/assistant-ui/markdown-code-block";
import { MermaidDiagram } from "@/components/assistant-ui/mermaid-diagram";
import { ResearchStudioPanel } from "@/components/leads/panels/ResearchStudioPanel";
import { GenerateImageToolUI } from "@/components/tool-ui/generate-image";
import { GenerateReportToolUI } from "@/components/tool-ui/generate-report";
import { GeneratePodcastToolUI } from "@/components/tool-ui/podcast/generate-podcast";
import { GenerateVideoPresentationToolUI } from "@/components/tool-ui/video-presentation/generate-video-presentation";
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import { presentationApiService } from "@/lib/apis/presentation-api.service";
import { cn } from "@/lib/utils";
import type { DockTabPayload, ToolCallContentPart } from "../lib/parse-dock-content";

function buildToolCallProps(part: ToolCallContentPart) {
	return {
		type: part.type,
		toolCallId: part.toolCallId,
		toolName: part.toolName,
		args: part.args,
		result: part.result,
		argsText: part.argsText,
		langchainToolCallId: part.langchainToolCallId,
		metadata: part.metadata,
		status: { type: "complete" as const },
		addResult: () => {},
		resume: () => {},
		respondToApproval: () => {},
	};
}

function Placeholder({
	icon: Icon,
	title,
	children,
}: {
	icon: React.ElementType;
	title: string;
	children?: React.ReactNode;
}) {
	return (
		<div className="flex h-full flex-col items-center justify-center gap-3 p-8 text-center text-muted-foreground">
			<div className="flex size-12 items-center justify-center rounded-2xl bg-muted">
				<Icon className="size-6" aria-hidden="true" />
			</div>
			<p className="font-medium text-foreground">{title}</p>
			{children && <p className="max-w-xs text-sm">{children}</p>}
		</div>
	);
}

function ImageDockContent({ payload }: { payload: Extract<DockTabPayload, { kind: "images" }> }) {
	return (
		<ScrollArea className="h-full">
			<div className="flex flex-col gap-4 p-4">
				{payload.parts.map((part) => {
					const props = buildToolCallProps(part) as unknown as Parameters<
						typeof GenerateImageToolUI
					>[0];
					return <GenerateImageToolUI key={part.toolCallId} {...props} />;
				})}
			</div>
		</ScrollArea>
	);
}

function ReportDockContent({ payload }: { payload: Extract<DockTabPayload, { kind: "reports" }> }) {
	const props = buildToolCallProps(payload.part) as unknown as Parameters<
		typeof GenerateReportToolUI
	>[0];
	return (
		<ScrollArea className="h-full">
			<div className="p-2">
				<GenerateReportToolUI {...props} />
			</div>
		</ScrollArea>
	);
}

function MediaDockContent({ payload }: { payload: Extract<DockTabPayload, { kind: "media" }> }) {
	return (
		<ScrollArea className="h-full">
			<div className="flex flex-col gap-4 p-2">
				{payload.parts.map((part) => {
					if (part.toolName === "generate_podcast") {
						const props = buildToolCallProps(part) as unknown as Parameters<
							typeof GeneratePodcastToolUI
						>[0];
						return <GeneratePodcastToolUI key={part.toolCallId} {...props} />;
					}
					const props = buildToolCallProps(part) as unknown as Parameters<
						typeof GenerateVideoPresentationToolUI
					>[0];
					return <GenerateVideoPresentationToolUI key={part.toolCallId} {...props} />;
				})}
			</div>
		</ScrollArea>
	);
}

function ResearchDockContent({
	payload,
	workspaceId,
}: {
	payload: Extract<DockTabPayload, { kind: "research" }>;
	workspaceId: string | number;
}) {
	if (!payload.report) {
		return <Placeholder icon={FileText} title="No research data available" />;
	}
	return (
		<div className="h-full overflow-hidden">
			<ResearchStudioPanel workspaceId={workspaceId} report={payload.report} />
		</div>
	);
}

function CodeDockContent({ payload }: { payload: Extract<DockTabPayload, { kind: "code" }> }) {
	const { resolvedTheme } = useTheme();
	const isDarkMode = resolvedTheme === "dark";
	return (
		<ScrollArea className="h-full">
			<div className="flex flex-col gap-4 p-4">
				{payload.blocks.map((block) => (
					<MarkdownCodeBlock
						key={`code-${block.language}-${block.code.slice(0, 24)}-${block.code.length}`}
						language={block.language}
						codeText={block.code}
						isDarkMode={isDarkMode}
					/>
				))}
			</div>
		</ScrollArea>
	);
}

function ChartDockContent({ payload }: { payload: Extract<DockTabPayload, { kind: "charts" }> }) {
	const { resolvedTheme } = useTheme();
	const isDarkMode = resolvedTheme === "dark";
	return (
		<ScrollArea className="h-full">
			<div className="flex flex-col gap-4 p-4">
				{payload.specs.map((spec) => {
					const fallback = (
						<MarkdownCodeBlock language="mermaid" codeText={spec} isDarkMode={isDarkMode} />
					);
					return (
						<MermaidDiagram
							key={`chart-${spec.slice(0, 24)}-${spec.length}`}
							source={spec}
							isDarkMode={isDarkMode}
							fallback={fallback}
							className="w-full"
						/>
					);
				})}
			</div>
		</ScrollArea>
	);
}

function SlidesDockContent({
	payload,
	workspaceId,
}: {
	payload: Extract<DockTabPayload, { kind: "slides" }>;
	workspaceId: string | number;
}) {
	const result =
		typeof payload.result === "object" && payload.result !== null
			? (payload.result as Record<string, unknown>)
			: null;
	const title = typeof result?.title === "string" ? result.title : "Slide deck";
	const format = typeof result?.format === "string" ? result.format : "pptx";
	const slideCount = typeof result?.slide_count === "number" ? result.slide_count : 0;
	const presentationId =
		typeof result?.presentation_id === "string" ? result.presentation_id : null;
	const downloadUrl = presentationId
		? presentationApiService.downloadUrl(presentationId, Number(workspaceId))
		: null;
	const previewUrl =
		presentationId && format === "marp"
			? presentationApiService.previewUrl(presentationId, Number(workspaceId))
			: null;

	return (
		<div className="flex h-full flex-col gap-4 p-4">
			<div className="flex items-center gap-3">
				<Presentation className="size-5 text-purple-600 dark:text-purple-400" aria-hidden="true" />
				<div className="min-w-0">
					<h3 className="truncate text-sm font-semibold">{title}</h3>
					<p className="text-xs text-muted-foreground">
						{slideCount > 0 ? `${slideCount} slide${slideCount === 1 ? "" : "s"}` : "Slide deck"} ·{" "}
						{format.toUpperCase()}
					</p>
				</div>
			</div>
			<div className="flex flex-wrap gap-2">
				{downloadUrl && (
					<Button variant="outline" size="sm" asChild className="gap-1.5 text-xs">
						<a href={downloadUrl} download rel="noopener noreferrer">
							<Download className="size-3.5" aria-hidden="true" />
							Download .{format}
						</a>
					</Button>
				)}
				{previewUrl && (
					<Button variant="outline" size="sm" asChild className="gap-1.5 text-xs">
						<a href={previewUrl} target="_blank" rel="noopener noreferrer">
							<ExternalLink className="size-3.5" aria-hidden="true" />
							Preview
						</a>
					</Button>
				)}
			</div>
			{previewUrl ? (
				<div className="flex-1 overflow-hidden rounded-xl border border-border/60 bg-background">
					<iframe
						src={previewUrl}
						title={title}
						className="h-full w-full"
						sandbox="allow-same-origin allow-scripts"
					/>
				</div>
			) : (
				<div className="flex flex-1 flex-col items-center justify-center rounded-xl border border-dashed border-border/60 bg-muted/30 p-6 text-center">
					<p className="text-sm text-muted-foreground">
						{format === "marp"
							? "Marp HTML preview is not available. Download the .md file and open it in Marp for VS Code."
							: "PowerPoint preview is not available. Download the .pptx file to view it."}
					</p>
				</div>
			)}
		</div>
	);
}

function SourcesDockContent({
	payload,
}: {
	payload: Extract<DockTabPayload, { kind: "sources" }>;
}) {
	return (
		<ScrollArea className="h-full">
			<div className="flex flex-col gap-3 p-4">
				{payload.citations.map((citation) => (
					<a
						key={citation.url || citation.title || `source-${citation.snippet?.slice(0, 16) ?? ""}`}
						href={citation.url || "#"}
						target="_blank"
						rel="noreferrer"
						className="rounded-xl border bg-card p-3 text-sm hover:border-primary/50 transition-colors"
					>
						<p className="font-medium text-foreground line-clamp-2">{citation.title}</p>
						{citation.domain && (
							<p className="text-xs text-muted-foreground mt-0.5">{citation.domain}</p>
						)}
						{citation.snippet && (
							<p className="text-xs text-muted-foreground mt-1 line-clamp-3">{citation.snippet}</p>
						)}
					</a>
				))}
			</div>
		</ScrollArea>
	);
}

function ArtifactsDockContent({
	payload,
}: {
	payload: Extract<DockTabPayload, { kind: "artifacts" }>;
}) {
	return (
		<ScrollArea className="h-full">
			<div className="flex flex-col gap-2 p-4">
				{payload.parts.map((part) => (
					<div
						key={part.toolCallId}
						className="flex items-center gap-3 rounded-xl border bg-card p-3 text-sm"
					>
						<Wrench className="size-4 text-muted-foreground" aria-hidden="true" />
						<span className="font-medium text-foreground">{part.toolName}</span>
					</div>
				))}
			</div>
		</ScrollArea>
	);
}

export interface DockContentProps {
	activeTab: string;
	payload: DockTabPayload;
	workspaceId: string | number;
	className?: string;
}

export function DockContent({ activeTab, payload, workspaceId, className }: DockContentProps) {
	if (!payload) {
		return <Placeholder icon={ImageIcon} title={`No content for ${activeTab}`} />;
	}

	let content: React.ReactNode = null;
	switch (payload.kind) {
		case "images":
			content = <ImageDockContent payload={payload} />;
			break;
		case "reports":
			content = <ReportDockContent payload={payload} />;
			break;
		case "media":
			content = <MediaDockContent payload={payload} />;
			break;
		case "research":
			content = <ResearchDockContent payload={payload} workspaceId={workspaceId} />;
			break;
		case "code":
			content = <CodeDockContent payload={payload} />;
			break;
		case "charts":
			content = <ChartDockContent payload={payload} />;
			break;
		case "slides":
			content = <SlidesDockContent payload={payload} workspaceId={workspaceId} />;
			break;
		case "sources":
			content = <SourcesDockContent payload={payload} />;
			break;
		case "artifacts":
			content = <ArtifactsDockContent payload={payload} />;
			break;
		case "leads":
		case "web-builder":
			// These are rendered by ContextualDock directly.
			content = <Placeholder icon={Music} title={`${activeTab} tab`} />;
			break;
		default:
			content = <Placeholder icon={ImageIcon} title={`Unsupported tab: ${activeTab}`} />;
	}

	return <div className={cn("h-full w-full overflow-hidden", className)}>{content}</div>;
}
