"use client";

import { Activity } from "lucide-react";
import { cn } from "@/lib/utils";

interface LabHeaderProps {
	doneCount: number;
	totalCount: number;
	elapsedMs: number;
	completedAgentMs?: number[];
	tokenSymbol?: string;
	tokenName?: string;
	degraded?: boolean;
	className?: string;
}

/**
 * AC6: Research Lab header — overall progress + adaptive ETA + optional token context.
 * Renders above the agent-lane grid while the session is running.
 *
 * ETA strategy (V2-P6): derive from average completion velocity rather than
 * needing the caller to pass `estimatedTotalMs`. If <1 agent has completed,
 * show elapsed only; otherwise project remaining = (avg per agent) × remaining.
 */
export function LabHeader({
	doneCount,
	totalCount,
	elapsedMs,
	completedAgentMs,
	tokenSymbol,
	tokenName,
	degraded = false,
	className,
}: LabHeaderProps) {
	const pct = totalCount > 0 ? Math.min((doneCount / totalCount) * 100, 100) : 0;
	const remaining = totalCount - doneCount;
	const etaLabel = (() => {
		if (remaining <= 0) return null;
		if (completedAgentMs && completedAgentMs.length > 0) {
			return formatEta(median(completedAgentMs) * remaining);
		}
		// Fallback to wall-clock when no completed agents yet
		return null;
	})();

	return (
		<div
			className={cn("flex flex-col gap-1.5", className)}
			data-slot="lab-header"
			data-degraded={degraded || undefined}
		>
			<div className="flex items-center justify-between gap-2 text-xs">
				<div className="flex min-w-0 items-center gap-1.5">
					{tokenSymbol ? (
						<>
							<span className="font-bold tracking-tight text-foreground">{tokenSymbol}</span>
							{tokenName && <span className="truncate text-muted-foreground">· {tokenName}</span>}
						</>
					) : (
						<>
							<Activity className="size-3.5 text-muted-foreground" aria-hidden="true" />
							<span className="font-medium text-muted-foreground">Research in progress</span>
						</>
					)}
				</div>
				<div className="flex shrink-0 items-center gap-2 text-muted-foreground">
					<span className="tabular-nums">
						{doneCount}/{totalCount} agents done
					</span>
					{etaLabel && <span className="tabular-nums">~{etaLabel} left</span>}
				</div>
			</div>

			{/* Progress bar */}
			<div
				className="h-0.5 w-full overflow-hidden rounded-full bg-muted"
				role="progressbar"
				aria-valuenow={Math.round(pct)}
				aria-valuemin={0}
				aria-valuemax={100}
			>
				<div
					className={cn(
						"h-full rounded-full transition-all duration-500 ease-out",
						degraded ? "bg-amber-500/80" : "bg-emerald-500/80"
					)}
					style={{ width: `${pct}%` }}
				/>
			</div>
		</div>
	);
}

function median(arr: number[]): number {
	const sorted = [...arr].sort((a, b) => a - b);
	const mid = Math.floor(sorted.length / 2);
	return sorted.length % 2 === 0 ? (sorted[mid - 1] + sorted[mid]) / 2 : sorted[mid];
}

function formatEta(ms: number): string {
	const sec = Math.round(ms / 1000);
	if (sec < 60) return `${sec}s`;
	const min = Math.floor(sec / 60);
	const remSec = sec % 60;
	return remSec === 0 ? `${min}m` : `${min}m ${remSec}s`;
}
