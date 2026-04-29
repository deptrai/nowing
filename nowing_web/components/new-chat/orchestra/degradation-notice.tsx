"use client";

import { useState } from "react";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { ChevronDown, ChevronUp, RefreshCw, TriangleAlert } from "lucide-react";
import { type OrchestraAgent } from "@/atoms/chat/orchestra.atom";
import { trackDegradationNoticeExpanded, trackDegradationRetryClicked } from "@/lib/posthog/events";

const REASON_LABELS: Record<string, string> = {
	rate_limit: "Rate limited",
	timeout: "Timed out",
	unavailable: "Service unavailable",
	circuit_open: "Circuit breaker open",
	cancelled_by_user: "Cancelled",
};

interface DegradationNoticeProps {
	failedAgents: OrchestraAgent[];
	successCount: number;
	totalCount: number;
	isComplete: boolean;
	sessionId: string;
	onRetry?: () => void;
}

export function DegradationNotice({
	failedAgents,
	successCount,
	totalCount,
	isComplete,
	sessionId,
	onRetry,
}: DegradationNoticeProps) {
	const [expanded, setExpanded] = useState(false);

	if (failedAgents.length === 0) return null;

	const failCount = failedAgents.length;

	function handleToggleExpand() {
		const next = !expanded;
		setExpanded(next);
		if (next) {
			trackDegradationNoticeExpanded({ sessionId, failCount, successCount, totalCount });
		}
	}

	function handleRetry() {
		trackDegradationRetryClicked({ sessionId, failCount });
		onRetry?.();
	}

	return (
		<Alert className="border-amber-500/50 bg-amber-50 dark:bg-amber-950/20 py-2 px-3">
			<TriangleAlert className="h-3.5 w-3.5 text-amber-500 shrink-0 mt-0.5" />
			<AlertDescription className="flex items-start justify-between gap-2 text-xs text-amber-800 dark:text-amber-300">
				<div className="flex-1 min-w-0">
					{/* Inline summary — always visible */}
					<span>
						{successCount}/{totalCount} sources completed
						{failCount > 0 && (
							<>
								{" "}
								· <span className="font-medium">{failCount} degraded</span>
							</>
						)}
					</span>

					{/* Expanded failure list */}
					{expanded && (
						<ul className="mt-1.5 space-y-0.5">
							{failedAgents.map((agent) => (
								<li key={agent.agentId} className="flex items-center gap-1.5">
									<span className="inline-block w-1.5 h-1.5 rounded-full bg-amber-500 shrink-0" />
									<span className="font-medium truncate">{agent.agentName}</span>
									{agent.failReason && (
										<span className="text-amber-700/70 dark:text-amber-400/70 shrink-0">
											— {REASON_LABELS[agent.failReason] ?? agent.failReason}
										</span>
									)}
								</li>
							))}
						</ul>
					)}

					{/* P9: Retry CTA — shown whenever session is complete and a handler is
					    provided. Previously hidden behind `expanded` gate which silently
					    required user to expand the notice first. */}
					{isComplete && onRetry && (
						<Button
							variant="ghost"
							size="sm"
							className="mt-2 h-6 px-2 text-xs text-amber-700 dark:text-amber-300 hover:bg-amber-100 dark:hover:bg-amber-900/30"
							onClick={handleRetry}
						>
							<RefreshCw className="h-3 w-3 mr-1" />
							Retry failed sources
						</Button>
					)}
				</div>

				{/* Expand/collapse toggle */}
				<button
					className="shrink-0 text-amber-600 dark:text-amber-400 hover:text-amber-800 dark:hover:text-amber-200 transition-colors"
					onClick={handleToggleExpand}
					aria-label={expanded ? "Collapse degradation details" : "Expand degradation details"}
				>
					{expanded ? (
						<ChevronUp className="h-3.5 w-3.5" />
					) : (
						<ChevronDown className="h-3.5 w-3.5" />
					)}
				</button>
			</AlertDescription>
		</Alert>
	);
}
