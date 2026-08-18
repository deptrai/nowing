"use client";

import {
	Activity,
	AlertCircle,
	ChevronDown,
	Clock,
	Cpu,
	Database,
	Network,
	Search,
	X,
} from "lucide-react";
import type React from "react";
import { useState } from "react";
import type { DshMission, DshMissionControl } from "@/contracts/types/dsh.types";
import { cn } from "@/lib/utils";

export interface MissionControlWidgetProps {
	workspaceId?: number | string;
	className?: string;
	latestMission?: DshMission | null;
	missionControl?: DshMissionControl | null;
	loading?: boolean;
	error?: string | null;
}

const STEPS = ["Crawl", "Reasoning", "Extraction", "Ingestion"];

const PHASE_TO_STEP: Record<string, number> = {
	crawl: 0,
	reasoning: 1,
	extraction: 2,
	ingest: 3,
	ingestion: 3,
	terminal: 3,
	success: 3,
};

const formatElapsed = (start?: string | null, end?: string | null) => {
	if (!start) return null;
	const startMs = new Date(start).getTime();
	const endMs = end ? new Date(end).getTime() : Date.now();
	const diff = Math.max(0, endMs - startMs);
	const seconds = Math.floor(diff / 1000);
	if (seconds < 60) return `${seconds}s`;
	const minutes = Math.floor(seconds / 60);
	const rem = seconds % 60;
	return `${minutes}m ${rem}s`;
};

export const MissionControlWidget: React.FC<MissionControlWidgetProps> = ({
	className,
	latestMission,
	missionControl,
	loading,
	error,
}) => {
	const [showReasoning, setShowReasoning] = useState(false);

	const phase = missionControl?.phase ?? latestMission?.phase ?? "idle";
	const rawProgress = missionControl?.progress_percent ?? latestMission?.progress_percent ?? 0;
	const progressPercent = Number.isFinite(rawProgress)
		? Math.min(100, Math.max(0, rawProgress))
		: 0;
	const status = latestMission?.status ?? "idle";
	const tokenVelocity = missionControl?.token_velocity;

	const activeStepIndex = PHASE_TO_STEP[phase?.toLowerCase() ?? ""] ?? -1;

	const elapsed = formatElapsed(
		missionControl?.subtasks?.[0]?.started_at,
		latestMission?.updated_at
	);

	if (!loading && status === "idle" && !latestMission) {
		return null;
	}

	return (
		<div
			data-testid="mission-control-widget"
			className={cn("rounded-xl border border-border bg-card/90 p-4 shadow-sm", className)}
		>
			<div className="flex items-center justify-between pb-3 border-b border-border">
				<div className="flex items-center gap-2">
					<div className="p-1.5 rounded-lg bg-indigo-500/10 text-indigo-600 dark:text-indigo-400">
						<Activity className="w-4 h-4" />
					</div>
					<div>
						<h3 className="text-sm font-semibold text-foreground">DSH Mission Control</h3>
						<p className="text-xs text-muted-foreground">Glass Box tiến trình tìm lead</p>
					</div>
				</div>
				<div className="flex items-center gap-2">
					{elapsed && (
						<span className="flex items-center gap-1 text-[10px] text-muted-foreground">
							<Clock className="w-3 h-3" />
							{elapsed}
						</span>
					)}
					<span
						data-testid="mission-control-phase"
						className={cn(
							"px-2 py-0.5 rounded-md text-[10px] font-semibold uppercase tracking-wide",
							status === "running" || status === "success"
								? "bg-emerald-500/15 text-emerald-600 dark:text-emerald-400"
								: status === "error"
									? "bg-red-500/15 text-red-600 dark:text-red-400"
									: "bg-muted text-muted-foreground"
						)}
					>
						{phase ?? status ?? "idle"}
					</span>
					{/* Cancel is UI-only / out of scope per spec (FR-38 real cancel deferred) */}
					<button
						type="button"
						disabled
						title="Hủy nhiệm vụ (chưa hỗ trợ)"
						className="p-1 rounded-md hover:bg-muted text-muted-foreground disabled:opacity-40 disabled:cursor-not-allowed"
					>
						<X className="w-3.5 h-3.5" />
					</button>
				</div>
			</div>

			{error && (
				<div className="mt-3 flex items-start gap-2 rounded-lg border border-red-500/20 bg-red-500/10 p-2.5 text-xs text-red-700 dark:text-red-300">
					<AlertCircle className="w-4 h-4 shrink-0" />
					<span>{error}</span>
				</div>
			)}

			<div className="py-4">
				<div className="mb-4">
					<div className="flex items-center justify-between mb-1.5">
						<span className="text-xs font-medium text-foreground">Tiến độ</span>
						<span className="text-xs font-mono text-muted-foreground">{progressPercent}%</span>
					</div>
					<div
						data-testid="mission-control-progress"
						className="h-2 w-full rounded-full bg-muted overflow-hidden"
					>
						<div
							className="h-full rounded-full bg-gradient-to-r from-indigo-500 to-emerald-500 transition-all duration-500"
							style={{ width: `${progressPercent}%` }}
						/>
					</div>
				</div>

				<div data-testid="mission-control-stepper" className="grid grid-cols-4 gap-2">
					{STEPS.map((step, index) => {
						const isActive = activeStepIndex >= 0 && index <= activeStepIndex;
						const isCurrent = index === activeStepIndex;
						const icons = [Search, Cpu, Network, Database];
						const Icon = icons[index];
						return (
							<div
								key={step}
								className={cn(
									"flex flex-col items-center gap-1 p-2 rounded-lg border text-center transition-colors",
									isActive
										? "border-emerald-500/40 bg-emerald-500/10 text-emerald-700 dark:text-emerald-300"
										: "border-border bg-muted/40 text-muted-foreground",
									isCurrent && "ring-1 ring-emerald-500/50"
								)}
							>
								<Icon className="w-3.5 h-3.5" />
								<span className="text-[10px] font-medium leading-tight">{step}</span>
							</div>
						);
					})}
				</div>

				<div
					data-testid="mission-control-token-velocity"
					className="mt-4 grid grid-cols-3 gap-2 rounded-lg border border-border bg-muted/40 p-2.5"
				>
					<div>
						<p className="text-[10px] text-muted-foreground uppercase">Token velocity</p>
						<p
							data-testid="token-velocity-value"
							className="text-sm font-mono font-semibold text-foreground"
						>
							{tokenVelocity
								? `${tokenVelocity.tokens_per_second || 0} tokens/sec`
								: "0 tokens/sec"}
						</p>
					</div>
					<div className="text-center">
						<p className="text-[10px] text-muted-foreground uppercase">Tổng tokens</p>
						<p
							data-testid="token-velocity-total"
							className="text-sm font-mono font-semibold text-foreground"
						>
							{tokenVelocity ? (tokenVelocity.tokens_total ?? 0) : 0}
						</p>
					</div>
					<div className="text-right">
						<p className="text-[10px] text-muted-foreground uppercase">Chi phí đã dùng</p>
						<p
							data-testid="token-velocity-cost"
							className="text-sm font-mono font-semibold text-emerald-600 dark:text-emerald-400"
						>
							{tokenVelocity ? `${tokenVelocity.cost_credits ?? 0} credits` : "0 credits"}
						</p>
					</div>
				</div>

				{missionControl?.subtasks && missionControl.subtasks.length > 0 && (
					<div className="mt-3">
						<button
							type="button"
							onClick={() => setShowReasoning((v) => !v)}
							className="flex items-center gap-1 text-[10px] font-medium text-muted-foreground hover:text-foreground transition-colors"
						>
							<span>Lý luận (CoT)</span>
							<ChevronDown
								className={cn("w-3.5 h-3.5 transition-transform", showReasoning && "rotate-180")}
							/>
						</button>
						{showReasoning && (
							<div className="mt-2 space-y-2 max-h-40 overflow-y-auto rounded-lg border border-border/60 bg-muted/20 p-2">
								{missionControl.subtasks.map((subtask, idx) => (
									<div key={subtask.id || idx} className="text-[10px] text-muted-foreground">
										<p className="font-medium text-foreground">{subtask.title}</p>
										{subtask.reasoning_content ? (
											<p className="line-clamp-3 mt-0.5">{subtask.reasoning_content}</p>
										) : (
											<p className="italic">Chưa có lý luận</p>
										)}
									</div>
								))}
							</div>
						)}
					</div>
				)}
			</div>
		</div>
	);
};
