"use client";

import { useAtomValue } from "jotai";
import { CheckCircle2, Loader2, XCircle } from "lucide-react";
import { type OrchestraAgent, activeOrchestraSessionAtom } from "@/atoms/chat/orchestra.atom";
import { cn } from "@/lib/utils";
import { AgentRow } from "./agent-row";
import { DegradationNotice } from "./degradation-notice";
import { ProgressMilestone } from "./progress-milestone";

interface OrchestraStripProps {
	/** Phase 9.2 placeholder — background pinning. Ignored in v1. */
	pinned?: boolean;
	className?: string;
}

/**
 * Orchestra Conductor Strip — inline horizontal status bar for multi-agent crypto analysis.
 * Renders inside the chat bubble ABOVE the synthesized response (AC1, AC6, AC15).
 *
 * Variants driven by session state:
 * - `default`       — full strip with all agent rows
 * - `single-agent`  — no strip wrapper, just inline status
 * - `collapsed`     — compact 1-line "N/M agents done"
 * - `pinned`        — Phase 9.2 placeholder
 */
export function OrchestraStrip({ className }: OrchestraStripProps) {
	const session = useAtomValue(activeOrchestraSessionAtom);

	if (!session) return null;

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

	return (
		<div
			className={cn(
				"mb-3 flex flex-col gap-1.5 rounded-lg border p-3",
				"border-border/60 bg-muted/20",
				"transition-all duration-150 ease-out",
				className
			)}
			data-slot="orchestra-strip"
			data-variant={isCollapsed ? "collapsed" : "default"}
		>
			{/* Collapsed summary after completion */}
			{isCollapsed ? (
				<div className="flex items-center gap-2 text-xs text-muted-foreground">
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
			) : (
				<>
					{/* Agent rows */}
					<div className="flex flex-col gap-1">
						{agents.map((agent) => (
							<AgentRow key={agent.agentId} agent={agent} />
						))}
					</div>

					{/* Progress milestone at T+30s */}
					<ProgressMilestone
						sessionId={session.sessionId}
						milestone={session.milestone ?? undefined}
						milestone30sFired={session.milestone30sFired}
						elapsedMs={Date.now() - session.spawnedAt}
					/>
				</>
			)}

			{/* Cancelled state footnote (AC5) */}
			{session.outcome === "cancelled" && (
				<p className="text-xs text-muted-foreground/70 mt-1">
					In-flight tokens vẫn được tính (best-effort cancel)
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
