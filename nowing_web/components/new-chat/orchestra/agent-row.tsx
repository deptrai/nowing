"use client";

import { useEffect, useRef, useState } from "react";
import { CheckCircle2, Loader2, XCircle } from "lucide-react";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { type OrchestraAgent } from "@/atoms/chat/orchestra.atom";
import { cn } from "@/lib/utils";

interface AgentRowProps {
	agent: OrchestraAgent;
}

const STATUS_LABELS: Record<OrchestraAgent["status"], string> = {
	idle: "Chờ",
	queued: "Xếp hàng",
	running: "Đang chạy",
	done: "Hoàn thành",
	failed: "Thất bại",
	cancelled: "Đã huỷ",
};

/**
 * Single agent status row inside `<OrchestraStrip />`.
 * Handles 5 visual states + running→done emerald glow transition (AC2, AC3, AC4, AC15).
 */
export function AgentRow({ agent }: AgentRowProps) {
	const { agentId, agentName, status, elapsedMs, summary, estimatedP50Ms, toolsCount } = agent;
	const prevStatusRef = useRef(status);
	const [showGlow, setShowGlow] = useState(false);

	// One-shot emerald glow on running→done transition (AC15: 600ms)
	useEffect(() => {
		if (prevStatusRef.current === "running" && status === "done") {
			setShowGlow(true);
			const timer = setTimeout(() => setShowGlow(false), 600);
			prevStatusRef.current = status;
			return () => clearTimeout(timer);
		}
		prevStatusRef.current = status;
	}, [status]);

	const tooltipText = [
		estimatedP50Ms ? `ETA ~${estimatedP50Ms}ms` : null,
		toolsCount ? `${toolsCount} tools` : null,
	]
		.filter(Boolean)
		.join(" · ");

	return (
		<div
			className={cn(
				"flex items-center gap-2 rounded-md px-2 py-1 text-xs",
				"transition-shadow duration-[600ms]",
				showGlow && "shadow-[0_0_8px_2px_rgba(16,185,129,0.4)]",
				status === "failed" || status === "cancelled"
					? "text-muted-foreground"
					: "text-foreground"
			)}
			data-agent-id={agentId}
			data-status={status}
		>
			{/* Status icon — max 1 spinner per row (AC15) */}
			<StatusIcon status={status} />

			{/* Agent name + tooltip */}
			<Tooltip>
				<TooltipTrigger asChild>
					<span className="min-w-0 truncate font-medium">{agentName}</span>
				</TooltipTrigger>
				{tooltipText && (
					<TooltipContent side="top" className="text-xs">
						{tooltipText}
					</TooltipContent>
				)}
			</Tooltip>

			{/* Elapsed time */}
			{elapsedMs > 0 && (
				<span className="ml-auto shrink-0 tabular-nums text-muted-foreground/70">
					{elapsedMs >= 1000 ? `${(elapsedMs / 1000).toFixed(1)}s` : `${elapsedMs}ms`}
				</span>
			)}

			{/* Done: fact count + source chips */}
			{status === "done" && summary && (
				<span className="ml-1 shrink-0 text-muted-foreground/70">
					{summary.factCount} facts · {summary.sources.length} src
				</span>
			)}

			{/* Failed: amber dot indicator (AC3 — NOT red) */}
			{(status === "failed" || status === "cancelled") && (
				<span
					className="ml-auto size-1.5 shrink-0 rounded-full bg-amber-500"
					aria-label={STATUS_LABELS[status]}
				/>
			)}
		</div>
	);
}

function StatusIcon({ status }: { status: OrchestraAgent["status"] }) {
	switch (status) {
		case "running":
			return (
				<Loader2
					className="size-3.5 shrink-0 animate-spin text-muted-foreground"
					aria-label="Running"
					aria-hidden="true"
				/>
			);
		case "done":
			return (
				<CheckCircle2
					className="size-3.5 shrink-0 text-emerald-500"
					aria-label="Done"
					aria-hidden="true"
				/>
			);
		case "failed":
		case "cancelled":
			return (
				<XCircle
					className="size-3.5 shrink-0 text-muted-foreground/50"
					aria-label={status === "failed" ? "Failed" : "Cancelled"}
					aria-hidden="true"
				/>
			);
		default:
			// idle / queued: neutral dot
			return (
				<div
					className="size-3.5 shrink-0 rounded-full bg-muted"
					aria-label={STATUS_LABELS[status]}
					aria-hidden="true"
				/>
			);
	}
}
