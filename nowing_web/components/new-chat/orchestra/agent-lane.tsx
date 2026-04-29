"use client";

import { useEffect, useRef, useState } from "react";
import {
	Activity,
	Bot,
	ChevronDown,
	ChevronUp,
	MessageSquare,
	Newspaper,
	Percent,
	Shield,
	TrendingUp,
} from "lucide-react";
import { type LucideIcon } from "lucide-react";
import { type OrchestraAgent } from "@/atoms/chat/orchestra.atom";
import { cn } from "@/lib/utils";
import { LiveNarrationStream } from "./live-narration-stream";
import { ModelAttributionBadge } from "./model-attribution-badge";
import { SourceFaviconRiver } from "./source-favicon-river";
import { StatusLight } from "./status-light";

interface AgentLaneProps {
	agent: OrchestraAgent;
	className?: string;
}

const AGENT_ICONS: Record<string, LucideIcon> = {
	tokenomics_analyst: TrendingUp,
	defillama_analyst: Activity,
	yield_optimizer: Percent,
	smart_contract_analyst: Shield,
	news_analyst: Newspaper,
	sentiment_analyst: MessageSquare,
};

/**
 * AC11 / V2-D3: explicit status pill combining a colored dot with a text label.
 * Replaces the dot-only StatusLight in the AgentLane header so users can read
 * the state at a glance even with reduced color vision.
 */
function StatusPill({ status }: { status: OrchestraAgent["status"] }) {
	const config: Record<OrchestraAgent["status"], { label: string; classes: string }> = {
		idle: { label: "Idle", classes: "bg-muted text-muted-foreground" },
		queued: { label: "⏳ Queued", classes: "bg-amber-500/10 text-amber-600 dark:text-amber-400" },
		running: {
			label: "🟢 Running",
			classes: "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400",
		},
		done: { label: "✓ Done", classes: "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400" },
		failed: { label: "Failed", classes: "bg-amber-500/10 text-amber-600 dark:text-amber-400" },
		cancelled: { label: "Cancelled", classes: "bg-muted text-muted-foreground" },
	};
	const { label, classes } = config[status];
	return (
		<span
			className={cn(
				"inline-flex shrink-0 items-center gap-1 rounded-full px-1.5 py-0.5 text-[10px] font-medium",
				classes
			)}
			role="status"
			aria-label={label}
		>
			<StatusLight status={status} className="size-1.5" />
			<span>{label}</span>
		</span>
	);
}

function AgentAvatar({ agentName, agentType }: { agentName: string; agentType: string }) {
	const key = agentName.toLowerCase().replace(/\s+/g, "_");
	const Icon = AGENT_ICONS[key] ?? AGENT_ICONS[agentType] ?? Bot;
	return (
		<span className="flex size-6 shrink-0 items-center justify-center rounded-full bg-muted">
			<Icon className="size-3.5 text-muted-foreground" aria-hidden="true" />
		</span>
	);
}

export function AgentLane({ agent, className }: AgentLaneProps) {
	const {
		agentId,
		agentName,
		agentType,
		status,
		elapsedMs,
		currentNarration,
		narrationHistory,
		sourcesFetched,
		factsCapturedCount,
		modelAttribution,
		resultText,
		resultLength,
		resultTruncated,
	} = agent;

	const prevStatusRef = useRef(status);
	const [showGlow, setShowGlow] = useState(false);
	const [expanded, setExpanded] = useState(false);
	const [activeTab, setActiveTab] = useState<"activity" | "result">("activity");
	const canExpand = narrationHistory.length > 0 || sourcesFetched.length > 0 || !!resultText;

	useEffect(() => {
		if (prevStatusRef.current === "running" && status === "done") {
			setShowGlow(true);
			const timer = setTimeout(() => setShowGlow(false), 600);
			prevStatusRef.current = status;
			return () => clearTimeout(timer);
		}
		prevStatusRef.current = status;
	}, [status]);

	// Auto-switch to "result" tab when result arrives — works whether the user
	// is currently expanded OR expands later (we only mark "seen" once we've
	// auto-switched, so a delayed expand still triggers the switch on first render).
	const prevResultRef = useRef<string | undefined>(undefined);
	useEffect(() => {
		if (resultText && !prevResultRef.current && expanded) {
			setActiveTab("result");
			prevResultRef.current = resultText;
		} else if (!resultText) {
			// Reset when result clears (new session) so the next arrival auto-switches.
			prevResultRef.current = undefined;
		}
	}, [resultText, expanded]);

	const elapsedLabel =
		elapsedMs >= 1000
			? `${(elapsedMs / 1000).toFixed(1)}s`
			: elapsedMs > 0
				? `${elapsedMs}ms`
				: null;

	return (
		<div
			className={cn(
				"flex flex-col gap-1.5 rounded-lg border border-border/50 bg-card p-2.5 text-xs",
				"transition-shadow duration-[600ms]",
				showGlow && "shadow-[0_0_8px_2px_rgba(16,185,129,0.35)]",
				(status === "failed" || status === "cancelled") && "opacity-60",
				className
			)}
			data-slot="agent-lane"
			data-agent-id={agentId}
			data-status={status}
		>
			{/* Header row: avatar + name + status pill + elapsed */}
			<div className="flex items-center gap-1.5">
				<AgentAvatar agentName={agentName} agentType={agentType} />
				<span className="min-w-0 flex-1 truncate font-medium text-foreground">{agentName}</span>
				<StatusPill status={status} />
				{elapsedLabel && (
					<span className="shrink-0 tabular-nums text-muted-foreground/60">{elapsedLabel}</span>
				)}
			</div>

			{/* Model attribution badge */}
			{modelAttribution && (
				<ModelAttributionBadge
					model={modelAttribution.model}
					provider={modelAttribution.provider}
					tier={modelAttribution.tier}
				/>
			)}

			{/* Live narration — animated fade-in stream */}
			{status === "running" && <LiveNarrationStream text={currentNarration} />}

			{/* Source favicon river */}
			<SourceFaviconRiver sources={sourcesFetched} />

			{/* Fact counter + expand toggle */}
			<div className="flex items-center justify-between text-muted-foreground/70">
				{factsCapturedCount > 0 ? (
					<span>{factsCapturedCount} facts captured</span>
				) : (
					<span aria-hidden="true" />
				)}
				{canExpand && (
					<button
						type="button"
						onClick={() => setExpanded((v) => !v)}
						className="inline-flex items-center gap-0.5 rounded text-[10px] hover:text-foreground focus:outline-none focus-visible:ring-2 focus-visible:ring-ring"
						aria-expanded={expanded}
						aria-label={expanded ? "Collapse lane details" : "Expand lane details"}
					>
						{expanded ? (
							<>
								Less <ChevronUp className="size-3" />
							</>
						) : (
							<>
								Expand <ChevronDown className="size-3" />
							</>
						)}
					</button>
				)}
			</div>

			{/* Expanded view: tabbed (Activity | Result) */}
			{expanded && (
				<div className="border-t border-border/30 pt-1.5">
					{/* Tab bar */}
					<div className="mb-1.5 flex gap-2 text-[10px]">
						<button
							type="button"
							onClick={() => setActiveTab("activity")}
							className={cn(
								"rounded px-1.5 py-0.5 font-medium transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-ring",
								activeTab === "activity"
									? "bg-muted text-foreground"
									: "text-muted-foreground hover:text-foreground"
							)}
						>
							Activity
						</button>
						{resultText && (
							<button
								type="button"
								onClick={() => setActiveTab("result")}
								className={cn(
									"rounded px-1.5 py-0.5 font-medium transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-ring",
									activeTab === "result"
										? "bg-muted text-foreground"
										: "text-muted-foreground hover:text-foreground"
								)}
							>
								Result
							</button>
						)}
					</div>

					{/* Activity tab */}
					{activeTab === "activity" && narrationHistory.length > 0 && (
						<>
							<p className="mb-1 text-[10px] font-medium uppercase tracking-wide text-muted-foreground/70">
								Recent activity
							</p>
							<ul className="flex flex-col gap-0.5 text-[11px] text-muted-foreground/80">
								{narrationHistory
									.slice()
									.reverse()
									.map((n, i) => (
										<li key={`${n.ts}-${i}`} className="truncate">
											<span className="mr-1 inline-block size-1 rounded-full bg-muted-foreground/40 align-middle" />
											{n.text}
										</li>
									))}
							</ul>
						</>
					)}

					{/* Result tab — note: result text is session-only (not persisted to DB).
					    After page reload, the tab auto-hides via the resultText guard. */}
					{activeTab === "result" && resultText && (
						<div className="rounded bg-muted/40 p-2">
							<p className="mb-1 text-[10px] text-muted-foreground/70">
								{(resultLength ?? 0).toLocaleString()} chars
								{resultTruncated && " · showing first 3000 chars"}
								<span className="ml-1 italic">· session-only</span>
							</p>
							<pre className="max-h-64 overflow-y-auto whitespace-pre-wrap break-words font-mono text-[10px] leading-relaxed text-foreground/80">
								{resultText}
							</pre>
						</div>
					)}
				</div>
			)}
		</div>
	);
}
