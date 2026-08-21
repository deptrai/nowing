"use client";

import {
	Activity,
	AlertCircle,
	ChevronDown,
	ChevronRight,
	Clock,
	Cpu,
	Database,
	Download,
	FileImage,
	FileSpreadsheet,
	FileText,
	Network,
	Search,
	X,
} from "lucide-react";
import type React from "react";
import { useEffect, useMemo, useState } from "react";
import { toast } from "sonner";
import type {
	DshMission,
	DshMissionControl,
	DshMissionDeliverable,
	DshMissionSubtask,
} from "@/contracts/types/dsh.types";
import { dshApiService } from "@/lib/apis/dsh-api.service";
import { cn } from "@/lib/utils";

export interface MissionControlWidgetProps {
	workspaceId?: number | string;
	className?: string;
	latestMission?: DshMission | null;
	missionControl?: DshMissionControl | null;
	loading?: boolean;
	error?: string | null;
	totalBudgetMicros?: number;
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

const PHASE_LABELS: Record<string, string> = {
	crawl: "Crawl",
	reasoning: "Lý luận",
	extraction: "Trích xuất",
	ingest: "Nạp dữ liệu",
	ingestion: "Nạp dữ liệu",
	terminal: "Hoàn thành",
	success: "Hoàn thành",
	error: "Lỗi",
	pending: "Chờ",
	running: "Đang chạy",
	cancelled: "Đã hủy",
	dlq: "DLQ",
};

const STATUS_LABELS: Record<string, string> = {
	pending: "Chờ",
	running: "Đang chạy",
	success: "Hoàn thành",
	error: "Lỗi",
	cancelled: "Đã hủy",
	dlq: "DLQ",
};

const SUBTASK_STATUS_LABELS: Record<string, string> = {
	pending: "Chờ",
	running: "Đang chạy",
	success: "Hoàn thành",
	error: "Lỗi",
	skipped: "Bỏ qua",
};

// 1 credit = $0.01 = 10_000 micro-USD.
const CREDIT_TO_MICROS = 10_000;

const formatBytes = (bytes: number): string => {
	if (bytes === 0) return "0 B";
	const k = 1024;
	const sizes = ["B", "KB", "MB", "GB"];
	const i = Math.floor(Math.log(bytes) / Math.log(k));
	return `${parseFloat((bytes / k ** i).toFixed(1))} ${sizes[i]}`;
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

const formatCost = (costMicros: number) => {
	const credits = costMicros / CREDIT_TO_MICROS;
	const dollars = costMicros / 1_000_000;
	return {
		credits: credits,
		dollars,
		label: `${credits.toFixed(1)} credits ≈ $${dollars.toFixed(3)}`,
	};
};

const formatBudgetPercent = (costMicros: number, totalBudgetMicros?: number) => {
	if (!totalBudgetMicros || totalBudgetMicros <= 0) return null;
	const percent = (costMicros / (costMicros + totalBudgetMicros)) * 100;
	return Math.min(100, Math.max(0, percent));
};

const estimateRemainingCredits = (costMicros: number, progressPercent: number) => {
	if (progressPercent <= 0 || progressPercent >= 100) return null;
	const credits = costMicros / CREDIT_TO_MICROS;
	const estimatedTotal = credits / (progressPercent / 100);
	return Math.max(0, estimatedTotal - credits);
};

const getPhaseLabel = (phase?: string | null, status?: string | null) => {
	if (phase && PHASE_LABELS[phase.toLowerCase()]) {
		return PHASE_LABELS[phase.toLowerCase()];
	}
	if (status && STATUS_LABELS[status.toLowerCase()]) {
		return STATUS_LABELS[status.toLowerCase()];
	}
	return "idle";
};

const getStepStatus = (index: number, activeStepIndex: number, status: string) => {
	if (index < activeStepIndex) return "completed";
	if (index === activeStepIndex) {
		return status === "running" ? "running" : "current";
	}
	return "pending";
};

const getDeliverableIcon = (type: string) => {
	if (type === "xlsx" || type === "csv") return FileSpreadsheet;
	if (["png", "jpg", "jpeg", "gif", "webp"].includes(type)) return FileImage;
	return FileText;
};

const getDeliverableMetadata = (d: DshMissionDeliverable) => {
	const parts: string[] = [];
	if (d.sources_count && d.sources_count > 0) {
		parts.push(`${d.sources_count} nguồn`);
	}
	if (d.topics_count && d.topics_count > 0) {
		parts.push(`${d.topics_count} khía cạnh`);
	}
	parts.push(formatBytes(d.size));
	return parts.join(" · ");
};

// ponytail: naive sparkline from subtask tokens_used, not a real time-series.
// Upgrade path: feed checkpoint timestamps from the worker when available.
function TokenSparkline({ subtasks }: { subtasks: DshMissionSubtask[] }) {
	const { path, viewBox } = useMemo(() => {
		const values = subtasks.map((s) => s.tokens_used);
		const width = 120;
		const height = 32;
		const padding = 2;
		const max = Math.max(1, ...values);

		if (values.length < 2) {
			// Flat line at baseline when only one datapoint.
			return {
				path: `M 0 ${height - padding} L ${width} ${height - padding}`,
				viewBox: `0 0 ${width} ${height}`,
			};
		}

		const points = values.map((v, i) => {
			const x = (i / (values.length - 1)) * width;
			const y = height - padding - (v / max) * (height - 2 * padding);
			return [x, y];
		});

		const d = points.reduce(
			(acc, [x, y], i) => (i === 0 ? `M ${x} ${y}` : `${acc} L ${x} ${y}`),
			""
		);
		return { path: d, viewBox: `0 0 ${width} ${height}` };
	}, [subtasks]);

	return (
		<svg
			viewBox={viewBox}
			preserveAspectRatio="none"
			role="img"
			aria-label="Token usage sparkline"
			className="h-8 w-full overflow-visible"
		>
			<path
				d={path}
				fill="none"
				stroke="currentColor"
				strokeWidth="2"
				className="text-emerald-500"
			/>
			<circle cx="120" cy="16" r="2" className="fill-emerald-500 opacity-0" />
		</svg>
	);
}

export const MissionControlWidget: React.FC<MissionControlWidgetProps> = ({
	workspaceId,
	className,
	latestMission,
	missionControl,
	loading,
	error,
	totalBudgetMicros,
}) => {
	const [expandedSubtasks, setExpandedSubtasks] = useState<Set<string>>(() => {
		const initial = new Set<string>();
		if (missionControl?.current_subtask_id) {
			initial.add(missionControl.current_subtask_id);
		}
		return initial;
	});
	const [expandedReasoning, setExpandedReasoning] = useState<Set<string>>(new Set());

	// Re-expand the current subtask when it changes.
	useEffect(() => {
		if (missionControl?.current_subtask_id) {
			setExpandedSubtasks((prev) => new Set([...prev, missionControl.current_subtask_id].filter((id): id is string => typeof id === "string")));
		}
	}, [missionControl?.current_subtask_id]);

	const phase = missionControl?.phase ?? latestMission?.phase ?? "idle";
	const rawProgress = missionControl?.progress_percent ?? latestMission?.progress_percent ?? 0;
	const progressPercent = Number.isFinite(rawProgress)
		? Math.min(100, Math.max(0, rawProgress))
		: 0;
	const status = latestMission?.status ?? "idle";
	const tokenVelocity = missionControl?.token_velocity;
	const deliverables = missionControl?.deliverables ?? [];
	const query = missionControl?.query;

	const activeStepIndex = PHASE_TO_STEP[phase?.toLowerCase() ?? ""] ?? -1;

	const elapsed = formatElapsed(
		missionControl?.subtasks?.[0]?.started_at,
		latestMission?.updated_at
	);

	const phaseLabel = getPhaseLabel(phase, status);
	const isRunning = status === "running";

	const tokenVelocityDisplay = useMemo(() => {
		if (!tokenVelocity) return null;
		return {
			tokensPerSecond: `${tokenVelocity.tokens_per_second || 0} tokens/sec`,
			tokensTotal: tokenVelocity.tokens_total ?? 0,
			cost: formatCost(tokenVelocity.cost_micros ?? 0),
			budgetPercent: formatBudgetPercent(tokenVelocity.cost_micros ?? 0, totalBudgetMicros),
			remainingCredits: estimateRemainingCredits(tokenVelocity.cost_micros ?? 0, progressPercent),
		};
	}, [tokenVelocity, totalBudgetMicros, progressPercent]);

	const handleDownload = (d: DshMissionDeliverable) => (e: React.MouseEvent) => {
		const href = latestMission
			? dshApiService.downloadDeliverableUrl(
					workspaceId ?? latestMission.workspace_id,
					latestMission.id,
					d.filename
				)
			: undefined;
		if (!href) {
			e.preventDefault();
			toast.error("Không thể tải xuống: link không khả dụng");
			return;
		}
		toast.success(`Đã tải xuống ${d.filename} (${formatBytes(d.size)})`);
	};

	const toggleSubtask = (id: string) => {
		setExpandedSubtasks((prev) => {
			const next = new Set(prev);
			if (next.has(id)) {
				next.delete(id);
			} else {
				next.add(id);
			}
			return next;
		});
	};

	const toggleReasoning = (id: string) => {
		setExpandedReasoning((prev) => {
			const next = new Set(prev);
			if (next.has(id)) {
				next.delete(id);
			} else {
				next.add(id);
			}
			return next;
		});
	};

	if (!loading && status === "idle" && !latestMission) {
		return null;
	}

	return (
		<div
			data-testid="mission-control-widget"
			className={cn("rounded-xl border border-border bg-card/90 p-4 shadow-sm", className)}
		>
			<div className="flex items-center justify-between pb-3 border-b border-border">
				<div className="flex items-center gap-2 min-w-0">
					<div className="p-1.5 rounded-lg bg-emerald-500/10 text-emerald-600 dark:text-emerald-400">
						<Activity className="w-4 h-4" />
					</div>
					<div className="min-w-0">
						<h3 className="text-sm font-semibold text-foreground">Trợ lý tìm lead</h3>
						<p className="text-xs text-muted-foreground truncate">
							{query ? `“${query}”` : "Glass Box tiến trình tìm lead"}
						</p>
					</div>
				</div>
				<div className="flex items-center gap-2 shrink-0">
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
							isRunning
								? "bg-emerald-500/15 text-emerald-600 dark:text-emerald-400"
								: status === "error" || status === "dlq"
									? "bg-red-500/15 text-red-600 dark:text-red-400"
									: status === "success" || status === "cancelled"
										? "bg-muted text-muted-foreground"
										: "bg-amber-500/15 text-amber-600 dark:text-amber-400"
						)}
					>
						{phaseLabel}
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

			<div className="py-4 space-y-4">
				<div>
					<div className="flex items-center justify-between mb-1.5">
						<span className="text-xs font-medium text-foreground">Tiến độ</span>
						<span className="text-xs font-mono text-muted-foreground">{progressPercent}%</span>
					</div>
					<div
						data-testid="mission-control-progress"
						className="h-2 w-full rounded-full bg-muted overflow-hidden"
					>
						<div
							className={cn(
								"h-full rounded-full bg-gradient-to-r from-indigo-500 to-emerald-500 transition-all duration-500",
								isRunning && "animate-pulse"
							)}
							style={{ width: `${progressPercent}%` }}
						/>
					</div>
				</div>

				<div data-testid="mission-control-stepper" className="grid grid-cols-4 gap-2">
					{STEPS.map((step, index) => {
						const stepStatus = getStepStatus(index, activeStepIndex, status);
						const isCurrent = stepStatus === "running" || stepStatus === "current";
						const icons = [Search, Cpu, Network, Database];
						const Icon = icons[index];
						return (
							<div
								key={step}
								className={cn(
									"flex flex-col items-center gap-1 p-2 rounded-lg border text-center transition-colors",
									stepStatus === "completed"
										? "border-emerald-500/40 bg-emerald-500/10 text-emerald-700 dark:text-emerald-300"
										: isCurrent
											? "border-emerald-500/60 bg-emerald-500/15 text-emerald-700 dark:text-emerald-300 ring-1 ring-emerald-500/50"
											: "border-border bg-muted/40 text-muted-foreground"
								)}
							>
								<Icon className={cn("w-3.5 h-3.5", stepStatus === "running" && "animate-spin")} />
								<span className="text-[10px] font-medium leading-tight">{step}</span>
							</div>
						);
					})}
				</div>

				<div
					data-testid="mission-control-token-velocity"
					className="grid grid-cols-3 gap-2 rounded-lg border border-border bg-muted/40 p-2.5"
				>
					<div>
						<p className="text-[10px] text-muted-foreground uppercase">Tốc độ xử lý</p>
						<p
							data-testid="token-velocity-value"
							className="text-sm font-mono font-semibold text-foreground"
						>
							{tokenVelocityDisplay?.tokensPerSecond ?? "0 tokens/sec"}
						</p>
					</div>
					<div className="text-center">
						<p className="text-[10px] text-muted-foreground uppercase">Tổng tokens</p>
						<p
							data-testid="token-velocity-total"
							className="text-sm font-mono font-semibold text-foreground"
						>
							{tokenVelocityDisplay?.tokensTotal ?? 0}
						</p>
					</div>
					<div className="text-right">
						<p className="text-[10px] text-muted-foreground uppercase">Chi phí đã dùng</p>
						<p
							data-testid="token-velocity-cost"
							className="text-sm font-mono font-semibold text-emerald-600 dark:text-emerald-400"
						>
							{tokenVelocityDisplay?.cost.label ?? "0 credits"}
						</p>
					</div>
					{tokenVelocityDisplay && tokenVelocityDisplay.budgetPercent != null && (
						<div className="col-span-3 mt-1">
							<div className="flex items-center justify-between text-[10px] text-muted-foreground mb-1">
								<span>
									Đã dùng {tokenVelocityDisplay.budgetPercent.toFixed(0)}% ngân sách tháng
								</span>
								{tokenVelocityDisplay.remainingCredits != null && (
									<span>
										Ước tính còn ~{tokenVelocityDisplay.remainingCredits.toFixed(1)} credits
									</span>
								)}
							</div>
							<div className="h-1.5 w-full rounded-full bg-muted overflow-hidden">
								<div
									className="h-full rounded-full bg-emerald-500 transition-all duration-500"
									style={{ width: `${tokenVelocityDisplay.budgetPercent}%` }}
								/>
							</div>
						</div>
					)}
				</div>

				{deliverables.length > 0 && (
					<div className="space-y-1.5" data-testid="mission-control-deliverables">
						<p className="text-[10px] text-muted-foreground uppercase">Kết quả xuất ra</p>
						{deliverables.map((d: DshMissionDeliverable) => {
							const href = latestMission
								? dshApiService.downloadDeliverableUrl(
										workspaceId ?? latestMission.workspace_id,
										latestMission.id,
										d.filename
									)
								: undefined;
							const FileIcon = getDeliverableIcon(d.type);
							return (
								<a
									key={d.filename}
									href={href}
									download
									data-testid={`mission-control-download-${d.filename}`}
									onClick={handleDownload(d)}
									className={cn(
										"flex items-center gap-2 rounded-md border border-border bg-muted/30 px-2.5 py-1.5 text-xs transition-colors",
										href
											? "hover:bg-muted text-foreground"
											: "pointer-events-none opacity-50 text-muted-foreground"
									)}
								>
									<FileIcon className="w-3.5 h-3.5 text-emerald-500 shrink-0" />
									<span className="flex-1 truncate">{d.filename}</span>
									<span className="text-[10px] text-muted-foreground shrink-0">
										{getDeliverableMetadata(d)}
									</span>
									{d.include_pii && (
										<span
											className="text-[10px] font-medium text-amber-600 dark:text-amber-400 bg-amber-500/10 px-1.5 py-0.5 rounded shrink-0"
											title="Dữ liệu chứa PII — tải xuống có trách nhiệm"
										>
											PII
										</span>
									)}
									<Download className="w-3.5 h-3.5 text-muted-foreground shrink-0" />
								</a>
							);
						})}
					</div>
				)}

				{missionControl?.subtasks && missionControl.subtasks.length > 0 && (
					<div className="space-y-1.5">
						<p className="text-[10px] text-muted-foreground uppercase">Tiêu thụ tokens theo bước</p>
						<TokenSparkline subtasks={missionControl.subtasks} />
					</div>
				)}

				{missionControl?.subtasks && missionControl.subtasks.length > 0 && (
					<div className="space-y-1.5">
						<div className="flex items-center justify-between">
							<p className="text-[10px] text-muted-foreground uppercase">Lý luận (CoT)</p>
							<button
								type="button"
								onClick={() =>
									setExpandedSubtasks(
										new Set(
											expandedSubtasks.size === missionControl.subtasks.length
												? []
												: missionControl.subtasks.map((s) => s.id)
										)
									)
								}
								className="text-[10px] text-muted-foreground hover:text-foreground transition-colors"
							>
								{expandedSubtasks.size === missionControl.subtasks.length
									? "Thu gọn tất cả"
									: "Mở rộng tất cả"}
							</button>
						</div>
						<div className="max-h-60 overflow-y-auto rounded-lg border border-border/60 bg-muted/20 p-2 space-y-1">
							{missionControl.subtasks.map((subtask) => {
								const isExpanded = expandedSubtasks.has(subtask.id);
								const reasoningExpanded = expandedReasoning.has(subtask.id);
								const subtaskCost = formatCost(subtask.cost_micros);
								return (
									<div key={subtask.id} className="text-[10px] text-muted-foreground">
										<button
											type="button"
											onClick={() => toggleSubtask(subtask.id)}
											className="w-full flex items-center gap-1.5 text-left hover:text-foreground transition-colors"
										>
											{isExpanded ? (
												<ChevronDown className="w-3 h-3 shrink-0" />
											) : (
												<ChevronRight className="w-3 h-3 shrink-0" />
											)}
											<span className="font-medium text-foreground truncate">{subtask.title}</span>
											<span
												className={cn(
													"shrink-0 px-1 py-0.5 rounded text-[9px] font-semibold",
													subtask.status === "success"
														? "bg-emerald-500/10 text-emerald-600"
														: subtask.status === "error"
															? "bg-red-500/10 text-red-600"
															: subtask.status === "running"
																? "bg-amber-500/10 text-amber-600"
																: "bg-muted text-muted-foreground"
												)}
											>
												{SUBTASK_STATUS_LABELS[subtask.status] ?? subtask.status}
											</span>
											{subtask.tokens_used > 0 && (
												<span className="shrink-0 text-[9px] text-muted-foreground">
													{subtask.tokens_used} tokens · {subtaskCost.label}
												</span>
											)}
										</button>
										{isExpanded && (
											<div className="mt-1 pl-4">
												{subtask.reasoning_content ? (
													<div className="space-y-1">
														<p
															className={cn(
																"whitespace-pre-wrap",
																!reasoningExpanded && "line-clamp-3"
															)}
														>
															{subtask.reasoning_content}
														</p>
														{subtask.reasoning_content.length > 120 && (
															<button
																type="button"
																onClick={() => toggleReasoning(subtask.id)}
																className="text-[10px] text-emerald-600 dark:text-emerald-400 hover:underline"
															>
																{reasoningExpanded ? "Thu gọn" : "Xem thêm"}
															</button>
														)}
													</div>
												) : (
													<p className="italic">Chưa có lý luận</p>
												)}
											</div>
										)}
									</div>
								);
							})}
						</div>
					</div>
				)}
			</div>
		</div>
	);
};
