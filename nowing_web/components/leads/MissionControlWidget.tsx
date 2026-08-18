"use client";

import { Activity, Cpu, Database, Network, Search } from "lucide-react";
import type React from "react";
import { useDshMissionControl } from "@/lib/hooks/use-dsh-mission-control";
import { cn } from "@/lib/utils";

export interface MissionControlWidgetProps {
	workspaceId?: number | string;
	className?: string;
}

const STEPS = ["Crawl", "Reasoning", "Extraction", "Ingest"];

export const MissionControlWidget: React.FC<MissionControlWidgetProps> = ({
	workspaceId,
	className,
}) => {
	const { missionControl, latestMission, loading } = useDshMissionControl(workspaceId);

	const phase = missionControl?.phase ?? latestMission?.phase ?? "idle";
	const progressPercent = missionControl?.progress_percent ?? latestMission?.progress_percent ?? 0;
	const status = latestMission?.status ?? "idle";
	const tokenVelocity = missionControl?.token_velocity;

	const activeStepIndex = STEPS.findIndex((s) => s.toLowerCase() === (phase ?? "").toLowerCase());

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
				<span
					data-testid="mission-control-phase"
					className={cn(
						"px-2 py-0.5 rounded-md text-[10px] font-semibold uppercase tracking-wide",
						status === "running" || status === "success"
							? "bg-emerald-500/15 text-emerald-600 dark:text-emerald-400"
							: "bg-muted text-muted-foreground"
					)}
				>
					{phase ?? "idle"}
				</span>
			</div>

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
							style={{ width: `${Math.min(100, Math.max(0, progressPercent ?? 0))}%` }}
						/>
					</div>
				</div>

				<div data-testid="mission-control-stepper" className="grid grid-cols-4 gap-2">
					{STEPS.map((step, index) => {
						const isActive = index <= activeStepIndex;
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
					className="mt-4 grid grid-cols-2 gap-2 rounded-lg border border-border bg-muted/40 p-2.5"
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
			</div>
		</div>
	);
};
