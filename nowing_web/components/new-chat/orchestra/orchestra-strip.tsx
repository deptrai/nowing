"use client";

import { useAtomValue } from "jotai";
import { CheckCircle2, Loader2, XCircle } from "lucide-react";
import {
	type OrchestraAgent,
	type OrchestraSession,
	activeOrchestraSessionAtom,
	orchestraStateAtom,
	deriveEscalationLevel,
} from "@/atoms/chat/orchestra.atom";
import { cn } from "@/lib/utils";
import { ActivityTimeline } from "./activity-timeline";
import { AgentLane } from "./agent-lane";
import { DegradationNotice } from "./degradation-notice";
import { LabHeader } from "./lab-header";
import { ProgressMilestone } from "./progress-milestone";
import { RateGateBanner } from "./rate-gate-banner";

/**
 * AC6 dynamic grid: 1×N for sm, 2×⌈N/2⌉ for md, 3×⌈N/3⌉ for lg.
 * Static class strings (Tailwind safelist constraint).
 */
function gridColsForCount(n: number): string {
	// AC6 formula: 1×N for sm, 2×⌈N/2⌉ for md, 3×⌈N/3⌉ for lg.
	// V2-P10: n=4 now yields lg:grid-cols-3 (3×2 with 1 row of 1) per spec,
	// instead of 2×2.
	if (n <= 1) return "grid-cols-1";
	if (n === 2) return "grid-cols-1 md:grid-cols-2";
	if (n === 3) return "grid-cols-1 md:grid-cols-2 lg:grid-cols-3";
	// n >= 4: spec is 2 cols at md, 3 cols at lg
	return "grid-cols-1 md:grid-cols-2 lg:grid-cols-3";
}

interface OrchestraStripProps {
	className?: string;
	/** T20: render a specific session by id instead of activeOrchestraSessionAtom. */
	sessionId?: string;
	/** T21: show Resume button + amber border when true. */
	isAbandoned?: boolean;
	/** T21: callback when user clicks Resume. */
	onResume?: () => void;
}

/**
 * Orchestra Conductor Strip — inline horizontal status bar for multi-agent crypto analysis.
 * Renders inside the chat bubble ABOVE the synthesized response (AC1, AC6, AC15).
 *
 * Variants driven by session state:
 * - `default`       — full strip with all agent rows
 * - `single-agent`  — no strip wrapper, just inline status
 * - `collapsed`     — compact 1-line "N/M agents done"
 */
export function OrchestraStrip({
	className,
	sessionId,
	isAbandoned,
	onResume,
}: OrchestraStripProps) {
	const defaultSession = useAtomValue(activeOrchestraSessionAtom);
	const allSessions = useAtomValue(orchestraStateAtom);
	const session: OrchestraSession | null = sessionId
		? (allSessions.sessions.get(sessionId) ?? null)
		: defaultSession;

	if (!session) {
		// T21: abandoned run with no orchestra session yet (e.g. after page reload)
		if (!isAbandoned || !onResume) return null;
		return (
			<div
				className={cn(
					"mb-3 flex items-center justify-between rounded-lg border px-3 py-2",
					"border-amber-400/50 bg-amber-50/10 text-xs text-muted-foreground",
					className
				)}
				data-slot="orchestra-strip"
				data-variant="abandoned-stub"
			>
				<span>Research paused — agent was interrupted</span>
				<button
					type="button"
					className="ml-3 rounded px-2 py-0.5 font-medium text-amber-600 hover:bg-amber-100 dark:text-amber-400 dark:hover:bg-amber-900/20"
					onClick={onResume}
				>
					Resume
				</button>
			</div>
		);
	}

	const agents = Array.from(session.agents.values());
	const failedAgents = agents.filter((a) => a.status === "failed");
	const doneCount = agents.filter((a) => a.status === "done").length;
	const totalCount = agents.length;

	// Single-agent: skip strip wrapper, render inline status only
	if (agents.length === 1) {
		const agent = agents[0];
		if (!agent) return null;
		return (
			<div
				className={cn(
					"mb-2 inline-flex items-center gap-1.5 text-xs text-muted-foreground",
					className
				)}
				data-slot="orchestra-strip"
				data-variant="single-agent"
			>
				<AgentStatusIcon status={agent.status} />
				<span>{agent.agentName}</span>
				{session.outcome === "success" && <span className="text-muted-foreground/60">·</span>}
				{session.totalMs !== null && <span className="tabular-nums">{session.totalMs}ms</span>}
			</div>
		);
	}

	const isCollapsed = session.outcome === "success" || session.outcome === "partial";
	const isComplete = session.outcome !== "running";
	// P4: only show progress milestone while the session is still running. A "failed"
	// outcome (non-collapsed) would otherwise keep the 30s timer ticking post-completion.
	const isRunning = session.outcome === "running";
	// AC11: derive degradation level from observed rate-gate frequency.
	const escalationLevel = deriveEscalationLevel(session.rateGateWaits);
	const isDegraded = escalationLevel >= 1;

	return (
		<div
			className={cn(
				"mb-3 flex flex-col gap-1.5 rounded-lg border p-3",
				"transition-all duration-150 ease-out",
				isAbandoned
					? "border-amber-400/50 bg-amber-50/10"
					: isDegraded && isRunning
						? "border-amber-500/50 bg-amber-500/5"
						: "border-border/60 bg-muted/20",
				className
			)}
			data-slot="orchestra-strip"
			data-variant={isCollapsed ? "collapsed" : "research-lab"}
			data-escalation-level={escalationLevel}
		>
			{/* Collapsed summary after completion */}
			{isCollapsed ? (
				<div className="flex items-center justify-between gap-2 text-xs text-muted-foreground">
					<div className="flex items-center gap-2">
						<CheckCircle2 className="size-3.5 shrink-0 text-emerald-500" />
						<span>
							{doneCount}/{totalCount} done
							{session.totalMs !== null && (
								<>
									{" · "}
									<span className="tabular-nums">{session.totalMs}ms</span>
									{session.p95Bucket && (
										<span className="ml-1 opacity-60">({session.p95Bucket})</span>
									)}
								</>
							)}
						</span>
					</div>
					{/* T21: Resume button in strip header for abandoned runs */}
					{isAbandoned && onResume && (
						<button
							type="button"
							className="ml-3 rounded px-2 py-0.5 text-xs font-medium text-amber-600 hover:bg-amber-100 dark:text-amber-400 dark:hover:bg-amber-900/20"
							onClick={onResume}
						>
							Resume
						</button>
					)}
				</div>
			) : (
				<>
					{/* Research Lab header — overall progress + ETA + degradation state */}
					{isRunning && (
						<>
							<LabHeader
								doneCount={doneCount}
								totalCount={totalCount}
								elapsedMs={Date.now() - session.spawnedAt}
								completedAgentMs={session.completedAgentMs}
								degraded={isDegraded}
								className="mb-1"
							/>
							{isDegraded && (
								<p className="mb-1 text-[11px] text-amber-600 dark:text-amber-400">
									Optimizing for rate limits — taking 2× longer to ensure complete results
								</p>
							)}
						</>
					)}

					{/* Agent grid — adaptive 1×N / 2×⌈N/2⌉ / 3×⌈N/3⌉ (AC6) */}
					<div className={cn("grid gap-2", gridColsForCount(totalCount))} data-slot="agent-grid">
						{agents.map((agent) => (
							<AgentLane key={agent.agentId} agent={agent} />
						))}
					</div>

					{/* Progress milestone at T+30s — only while running (P4) */}
					{isRunning && (
						<ProgressMilestone
							sessionId={session.sessionId}
							milestone={session.milestone ?? undefined}
							milestone30sFired={session.milestone30sFired}
							elapsedMs={Date.now() - session.spawnedAt}
						/>
					)}

					{/* Activity timeline: per-LLM-call ticks + gate pauses */}
					{isRunning && (
						<ActivityTimeline
							spawnedAt={session.spawnedAt}
							rateGateWaits={session.rateGateWaits}
							llmCallEvents={session.llmCallEvents}
						/>
					)}

					{/* Rate-gate educational banner — shown when actively throttling */}
					{isRunning && session.rateGateWaits.length > 0 && (
						<RateGateBanner
							latestGate={session.rateGateWaits[session.rateGateWaits.length - 1] ?? null}
						/>
					)}
				</>
			)}

			{/* Cancelled state footnote (AC5) */}
			{session.outcome === "cancelled" && (
				<p className="mt-1 text-xs text-muted-foreground/70">
					In-flight tokens are still counted (best-effort cancel)
				</p>
			)}

			{/* Degradation notice for failed agents (AC3) */}
			{failedAgents.length > 0 && (
				<DegradationNotice
					failedAgents={failedAgents}
					successCount={doneCount}
					totalCount={totalCount}
					isComplete={isComplete}
					sessionId={session.sessionId}
					onRetry={onResume}
				/>
			)}
		</div>
	);
}

function AgentStatusIcon({ status }: { status: OrchestraAgent["status"] }) {
	switch (status) {
		case "running":
			return <Loader2 className="size-3.5 animate-spin shrink-0" aria-hidden="true" />;
		case "done":
			return <CheckCircle2 className="size-3.5 text-emerald-500 shrink-0" aria-hidden="true" />;
		case "failed":
		case "cancelled":
			return <XCircle className="size-3.5 text-muted-foreground/60 shrink-0" aria-hidden="true" />;
		default:
			return <div className="size-3.5 rounded-full bg-muted shrink-0" aria-hidden="true" />;
	}
}
