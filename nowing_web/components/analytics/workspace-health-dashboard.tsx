"use client";

import { useQuery } from "@tanstack/react-query";
import {
	Activity,
	AlertCircle,
	ArrowDownRight,
	ArrowUpRight,
	ChevronRight,
	Database,
	DollarSign,
	Download,
	Lock,
	Plus,
	RefreshCw,
	Search,
	Sparkles,
	TrendingUp,
	Users,
	Zap,
} from "lucide-react";
import Link from "next/link";
import { useMemo, useState } from "react";
import { toast } from "sonner";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import {
	DropdownMenu,
	DropdownMenuContent,
	DropdownMenuItem,
	DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Input } from "@/components/ui/input";
import { Spinner } from "@/components/ui/spinner";
import {
	Table,
	TableBody,
	TableCell,
	TableHead,
	TableHeader,
	TableRow,
} from "@/components/ui/table";
import type { WorkspaceHealthRange } from "@/contracts/types/workspace-health.types";
import { workspaceHealthApiService } from "@/lib/apis/workspace-health-api.service";
import { cacheKeys } from "@/lib/query-client/cache-keys";
import { cn } from "@/lib/utils";
import { CoverageGapDrawer } from "./coverage-gap-drawer";
import { SourceDrilldownSheet } from "./source-drilldown-sheet";
import { Sparkline } from "./sparkline";

interface WorkspaceHealthDashboardProps {
	workspaceId: number | string;
}

function formatUsd(micros: number | null | undefined): string {
	if (micros === null || micros === undefined) return "—";
	const dollars = micros / 1_000_000;
	if (dollars === 0) return "$0.00";
	if (dollars < 0.01) return `< $0.01`;
	return `$${dollars.toFixed(2)}`;
}

function formatCompactNumber(value: number | null | undefined): string {
	if (value === null || value === undefined) return "—";
	return new Intl.NumberFormat(undefined, { notation: "compact" }).format(value);
}

function renderChangeBadge(changePct: number | null | undefined) {
	if (changePct === null || changePct === undefined) {
		return <span className="text-xs text-muted-foreground">—</span>;
	}
	const isPositive = changePct > 0;
	const isZero = changePct === 0;

	return (
		<span
			className={cn(
				"inline-flex items-center text-xs font-medium",
				isPositive
					? "text-emerald-600 dark:text-emerald-400"
					: isZero
						? "text-muted-foreground"
						: "text-rose-600 dark:text-rose-400"
			)}
		>
			{isPositive ? (
				<ArrowUpRight className="h-3 w-3 mr-0.5" />
			) : isZero ? null : (
				<ArrowDownRight className="h-3 w-3 mr-0.5" />
			)}
			{isPositive ? "+" : ""}
			{changePct.toFixed(1)}% (7d)
		</span>
	);
}

export function WorkspaceHealthDashboard({ workspaceId }: WorkspaceHealthDashboardProps) {
	const [range, setRange] = useState<WorkspaceHealthRange>("30d");
	const [customStartDate, setCustomStartDate] = useState("");
	const [customEndDate, setCustomEndDate] = useState("");
	const [selectedSourceType, setSelectedSourceType] = useState<string | null>(null);
	const [isDrilldownOpen, setIsDrilldownOpen] = useState(false);
	const [isGapsDrawerOpen, setIsGapsDrawerOpen] = useState(false);
	const [isExporting, setIsExporting] = useState(false);

	const numericWorkspaceId = Number(workspaceId);

	// Fetch Summary
	const {
		data: summary,
		isLoading,
		isError,
		refetch,
	} = useQuery({
		queryKey: cacheKeys.workspaces.health.summary(
			workspaceId,
			range,
			range === "custom" ? customStartDate : undefined,
			range === "custom" ? customEndDate : undefined
		),
		queryFn: () =>
			workspaceHealthApiService.getHealthMetrics(
				workspaceId,
				range,
				range === "custom" ? customStartDate : undefined,
				range === "custom" ? customEndDate : undefined
			),
		enabled: !Number.isNaN(numericWorkspaceId) && numericWorkspaceId > 0,
	});

	// Fetch Gaps
	const { data: gapsData } = useQuery({
		queryKey: cacheKeys.workspaces.health.coverageGaps(workspaceId),
		queryFn: () => workspaceHealthApiService.getCoverageGaps(workspaceId),
		enabled: !Number.isNaN(numericWorkspaceId) && numericWorkspaceId > 0,
	});

	const handleExport = async (format: "csv" | "json") => {
		try {
			setIsExporting(true);
			await workspaceHealthApiService.downloadHealthExport(
				workspaceId,
				format,
				range,
				range === "custom" ? customStartDate : undefined,
				range === "custom" ? customEndDate : undefined
			);
			toast.success(`Exported health metrics (${format.toUpperCase()})`);
		} catch (_err) {
			toast.error("Failed to export metrics. Please try again.");
		} finally {
			setIsExporting(false);
		}
	};

	const isEmptyState = useMemo(() => {
		if (!summary) return false;
		const totalMems = summary.total_memories?.current_value ?? 0;
		const totalQueries = summary.query_volume?.current_value ?? 0;
		return totalMems === 0 && totalQueries === 0;
	}, [summary]);

	if (isLoading) {
		return (
			<div className="flex h-96 items-center justify-center">
				<Spinner className="h-8 w-8 text-primary" />
			</div>
		);
	}

	if (isError || !summary) {
		return (
			<div className="p-8 text-center border rounded-xl bg-card space-y-3">
				<AlertCircle className="h-10 w-10 text-destructive mx-auto" />
				<h3 className="font-semibold text-lg">Unable to load workspace health analytics</h3>
				<p className="text-sm text-muted-foreground max-w-md mx-auto">
					Ensure you have the required workspace permissions (ANALYTICS_READ or MEMORY_READ).
				</p>
				<Button onClick={() => refetch()} variant="outline" size="sm">
					<RefreshCw className="h-4 w-4 mr-2" />
					Retry
				</Button>
			</div>
		);
	}

	return (
		<div className="space-y-6 pb-12">
			{/* Public Snapshot Notice */}
			{summary.is_public_snapshot && (
				<div className="flex items-center justify-between gap-3 p-3.5 rounded-lg border border-amber-500/20 bg-amber-500/10 text-amber-900 dark:text-amber-200 text-xs">
					<div className="flex items-center gap-2">
						<Lock className="h-4 w-4 text-amber-600 dark:text-amber-400 shrink-0" />
						<span>
							<strong>Public Snapshot Mode:</strong> Financial metrics (credit burn, cost-per-turn)
							and individual member identities are masked. Contact a workspace owner for full
							access.
						</span>
					</div>
					<Badge
						variant="outline"
						className="border-amber-500/40 text-destructive dark:text-destructive-foreground text-[10px]"
					>
						INV-29.3 Read Only
					</Badge>
				</div>
			)}

			{/* Top Header Bar */}
			<div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
				<div>
					<div className="flex items-center gap-2.5">
						<div className="flex h-9 w-9 items-center justify-center rounded-lg bg-primary/10 text-primary">
							<Activity className="h-5 w-5" />
						</div>
						<div>
							<h1 className="text-xl sm:text-2xl font-semibold tracking-tight">
								Workspace Health & Adoption
							</h1>
							<p className="text-xs text-muted-foreground">
								Real-time adoption sparklines, knowledge coverage, and quota telemetry
							</p>
						</div>
					</div>
				</div>

				<div className="flex flex-wrap items-center gap-2.5">
					{/* Range Selector */}
					<div className="flex items-center rounded-lg border bg-muted/40 p-1 text-xs">
						{(["7d", "30d", "90d", "custom"] as const).map((r) => (
							<button
								key={r}
								type="button"
								onClick={() => setRange(r)}
								className={cn(
									"px-2.5 py-1 rounded-md font-medium transition-all uppercase text-[11px]",
									range === r
										? "bg-background text-foreground shadow-sm"
										: "text-muted-foreground hover:text-foreground"
								)}
							>
								{r}
							</button>
						))}
					</div>

					{range === "custom" && (
						<div className="flex items-center gap-1.5 text-xs">
							<Input
								type="date"
								value={customStartDate}
								onChange={(e) => setCustomStartDate(e.target.value)}
								className="h-8 text-xs w-32"
								placeholder="Start date"
							/>
							<span className="text-muted-foreground">to</span>
							<Input
								type="date"
								value={customEndDate}
								onChange={(e) => setCustomEndDate(e.target.value)}
								className="h-8 text-xs w-32"
								placeholder="End date"
							/>
						</div>
					)}

					{/* Export Dropdown */}
					<DropdownMenu>
						<DropdownMenuTrigger asChild>
							<Button variant="outline" size="sm" className="h-8 text-xs" disabled={isExporting}>
								<Download className="h-3.5 w-3.5 mr-1.5" />
								{isExporting ? "Exporting..." : "Export"}
							</Button>
						</DropdownMenuTrigger>
						<DropdownMenuContent align="end">
							<DropdownMenuItem onClick={() => handleExport("csv")}>
								Export CSV (.csv)
							</DropdownMenuItem>
							<DropdownMenuItem onClick={() => handleExport("json")}>
								Export JSON (.json)
							</DropdownMenuItem>
						</DropdownMenuContent>
					</DropdownMenu>
				</div>
			</div>

			{/* Empty State Onboarding Guidance (AC-6.7) */}
			{isEmptyState ? (
				<Card className="border-dashed">
					<CardContent className="flex flex-col items-center justify-center p-12 text-center space-y-4">
						<div className="flex h-14 w-14 items-center justify-center rounded-full bg-primary/10 text-primary">
							<Sparkles className="h-7 w-7" />
						</div>
						<div className="space-y-1 max-w-md">
							<h3 className="font-semibold text-lg">No Health Activity Yet</h3>
							<p className="text-sm text-muted-foreground">
								Start by connecting your workspace data sources or having conversations with agents
								to populate memories and queries.
							</p>
						</div>
						<div className="flex items-center gap-3 pt-2">
							<Button asChild size="sm">
								<Link href={`/dashboard/${workspaceId}/connectors`}>
									<Plus className="h-4 w-4 mr-1.5" />
									Connect Sources
								</Link>
							</Button>
							<Button asChild variant="outline" size="sm">
								<Link href={`/dashboard/${workspaceId}/new-chat`}>Start New Chat</Link>
							</Button>
						</div>
					</CardContent>
				</Card>
			) : (
				<>
					{/* HD-1: 6 Metric Cards with 14-Day Sparklines */}
					<div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
						{/* 1. Active Members (DAU / WAU) */}
						<Card className="shadow-none">
							<CardHeader className="p-4 pb-2 flex flex-row items-center justify-between space-y-0">
								<CardTitle className="text-xs font-medium text-muted-foreground">
									Active Members
								</CardTitle>
								<Users className="h-4 w-4 text-muted-foreground" />
							</CardHeader>
							<CardContent className="p-4 pt-1 space-y-2">
								{summary.is_public_snapshot || !summary.active_members_dau ? (
									<div className="flex items-center gap-1.5 py-1">
										<Lock className="h-4 w-4 text-muted-foreground" />
										<span className="text-sm text-muted-foreground italic font-medium">
											Protected (Masked)
										</span>
									</div>
								) : (
									<>
										<div className="flex items-baseline justify-between">
											<div className="text-2xl font-bold">
												{summary.active_members_dau.current_value ?? 0}
												<span className="text-xs font-normal text-muted-foreground ml-1.5">
													DAU
												</span>
											</div>
											{renderChangeBadge(summary.active_members_dau.change_pct)}
										</div>
										<div className="text-[11px] text-muted-foreground">
											Trailing 7-Day Active (WAU):{" "}
											<span className="font-semibold text-foreground">
												{summary.active_members_wau?.current_value ?? 0}
											</span>
										</div>
										<Sparkline
											values={summary.active_members_dau.sparkline}
											colorClassName="text-blue-500"
											className="h-7 w-full pt-1"
										/>
									</>
								)}
							</CardContent>
						</Card>

						{/* 1.5. Total Members */}
						<Card className="shadow-none">
							<CardHeader className="p-4 pb-2 flex flex-row items-center justify-between space-y-0">
								<CardTitle className="text-xs font-medium text-muted-foreground">
									Total Members
								</CardTitle>
								<Users className="h-4 w-4 text-muted-foreground" />
							</CardHeader>
							<CardContent className="p-4 pt-1 space-y-2">
								<div className="flex items-baseline justify-between">
									<div className="text-2xl font-bold">
										{formatCompactNumber(summary.total_members.current_value)}
									</div>
									{renderChangeBadge(summary.total_members.change_pct)}
								</div>
								<div className="text-[11px] text-muted-foreground">
									Total workspace members as of selected period
								</div>
								<Sparkline
									values={summary.total_members.sparkline}
									colorClassName="text-sky-500"
									className="h-7 w-full pt-1"
								/>
							</CardContent>
						</Card>

						{/* 2. Total Memories */}
						<Card className="shadow-none">
							<CardHeader className="p-4 pb-2 flex flex-row items-center justify-between space-y-0">
								<CardTitle className="text-xs font-medium text-muted-foreground">
									Total Memories
								</CardTitle>
								<Database className="h-4 w-4 text-muted-foreground" />
							</CardHeader>
							<CardContent className="p-4 pt-1 space-y-2">
								<div className="flex items-baseline justify-between">
									<div className="text-2xl font-bold">
										{formatCompactNumber(summary.total_memories.current_value)}
									</div>
									{renderChangeBadge(summary.total_memories.change_pct)}
								</div>
								<div className="text-[11px] text-muted-foreground">
									Total retained workspace knowledge assets
								</div>
								<Sparkline
									values={summary.total_memories.sparkline}
									colorClassName="text-emerald-500"
									className="h-7 w-full pt-1"
								/>
							</CardContent>
						</Card>

						{/* 3. Memory Growth Rate */}
						<Card className="shadow-none">
							<CardHeader className="p-4 pb-2 flex flex-row items-center justify-between space-y-0">
								<CardTitle className="text-xs font-medium text-muted-foreground">
									Memory Growth Rate
								</CardTitle>
								<TrendingUp className="h-4 w-4 text-muted-foreground" />
							</CardHeader>
							<CardContent className="p-4 pt-1 space-y-2">
								<div className="flex items-baseline justify-between">
									<div className="text-2xl font-bold">
										+{formatCompactNumber(summary.memory_growth_count.current_value)}
									</div>
									{renderChangeBadge(summary.memory_growth_count.change_pct)}
								</div>
								<div className="text-[11px] text-muted-foreground">
									New memories extracted in selected period
								</div>
								<Sparkline
									values={summary.memory_growth_count.sparkline}
									colorClassName="text-indigo-500"
									className="h-7 w-full pt-1"
								/>
							</CardContent>
						</Card>

						{/* 4. Query Volume */}
						<Card className="shadow-none">
							<CardHeader className="p-4 pb-2 flex flex-row items-center justify-between space-y-0">
								<CardTitle className="text-xs font-medium text-muted-foreground">
									Query Volume
								</CardTitle>
								<Search className="h-4 w-4 text-muted-foreground" />
							</CardHeader>
							<CardContent className="p-4 pt-1 space-y-2">
								<div className="flex items-baseline justify-between">
									<div className="text-2xl font-bold">
										{formatCompactNumber(summary.query_volume.current_value)}
									</div>
									{renderChangeBadge(summary.query_volume.change_pct)}
								</div>
								<div className="flex items-center gap-2 text-[11px] text-muted-foreground">
									<span>
										Recall: <strong>{summary.recall_queries}</strong>
									</span>
									<span>•</span>
									<span>
										Research: <strong>{summary.research_queries}</strong>
									</span>
								</div>
								<Sparkline
									values={summary.query_volume.sparkline}
									colorClassName="text-violet-500"
									className="h-7 w-full pt-1"
								/>
							</CardContent>
						</Card>

						{/* 5. Credits Consumed */}
						<Card className="shadow-none">
							<CardHeader className="p-4 pb-2 flex flex-row items-center justify-between space-y-0">
								<CardTitle className="text-xs font-medium text-muted-foreground">
									Credits Consumed
								</CardTitle>
								<Zap className="h-4 w-4 text-muted-foreground" />
							</CardHeader>
							<CardContent className="p-4 pt-1 space-y-2">
								{summary.is_public_snapshot || !summary.credits_consumed_micros ? (
									<div className="flex items-center gap-1.5 py-1">
										<Lock className="h-4 w-4 text-muted-foreground" />
										<span className="text-sm text-muted-foreground italic font-medium">
											Protected (Owner only)
										</span>
									</div>
								) : (
									<>
										<div className="flex items-baseline justify-between">
											<div className="text-2xl font-bold">
												{formatUsd(summary.credits_consumed_micros.current_value)}
											</div>
											{renderChangeBadge(summary.credits_consumed_micros.change_pct)}
										</div>
										<div className="text-[11px] text-muted-foreground">
											Burn across agents and background pipelines
										</div>
										<Sparkline
											values={summary.credits_consumed_micros.sparkline}
											colorClassName="text-amber-500"
											className="h-7 w-full pt-1"
										/>
									</>
								)}
							</CardContent>
						</Card>

						{/* 6. Cost Per Turn */}
						<Card className="shadow-none">
							<CardHeader className="p-4 pb-2 flex flex-row items-center justify-between space-y-0">
								<CardTitle className="text-xs font-medium text-muted-foreground">
									Cost Per Turn
								</CardTitle>
								<DollarSign className="h-4 w-4 text-muted-foreground" />
							</CardHeader>
							<CardContent className="p-4 pt-1 space-y-2">
								{summary.is_public_snapshot || !summary.cost_per_turn_micros ? (
									<div className="flex items-center gap-1.5 py-1">
										<Lock className="h-4 w-4 text-muted-foreground" />
										<span className="text-sm text-muted-foreground italic font-medium">
											Protected (Owner only)
										</span>
									</div>
								) : (
									<>
										<div className="flex items-baseline justify-between">
											<div className="text-2xl font-bold">
												{formatUsd(summary.cost_per_turn_micros.current_value)}
											</div>
											{renderChangeBadge(summary.cost_per_turn_micros.change_pct)}
										</div>
										<div className="text-[11px] text-muted-foreground">
											Average credits per agent execution turn
										</div>
										<Sparkline
											values={summary.cost_per_turn_micros.sparkline}
											colorClassName="text-teal-500"
											className="h-7 w-full pt-1"
										/>
									</>
								)}
							</CardContent>
						</Card>
					</div>

					{/* HD-2: Quota Progress Bars with Advisory Thresholds */}
					{summary.quota_progress && summary.quota_progress.length > 0 && (
						<Card className="shadow-none border-border/80">
							<CardHeader className="p-4 pb-3 flex flex-row items-center justify-between space-y-0">
								<div>
									<CardTitle className="text-sm font-semibold flex items-center gap-2">
										<span>Quota Utilization & Plan Progression</span>
										<Badge variant="outline" className="text-[10px] font-normal">
											Advisory
										</Badge>
									</CardTitle>
									<CardDescription className="text-xs mt-0.5">
										Monitor usage limits against your workspace plan. Operations are never blocked.
									</CardDescription>
								</div>
								<Button asChild size="sm" variant="outline" className="h-7 text-xs">
									<Link href={`/dashboard/${workspaceId}/workspace-settings/limits`}>
										Upgrade Plan
									</Link>
								</Button>
							</CardHeader>

							<CardContent className="p-4 pt-1 space-y-4">
								<div className="grid grid-cols-1 md:grid-cols-3 gap-4">
									{summary.quota_progress.map((item) => {
										const pct = item.utilization_pct ?? 0;
										const isAlert = item.status === "alert";
										const isWarning = item.status === "warning";

										return (
											<div key={item.metric} className="p-3 rounded-lg border bg-card/60 space-y-2">
												<div className="flex items-center justify-between text-xs">
													<span className="font-medium text-foreground">{item.label}</span>
													{isAlert ? (
														<Badge
															variant="destructive"
															className="text-[10px] px-1.5 py-0 uppercase"
														>
															Quota Exceeded
														</Badge>
													) : isWarning ? (
														<Badge className="bg-amber-500 text-white text-[10px] px-1.5 py-0 uppercase">
															Warning (80%+)
														</Badge>
													) : (
														<span className="text-[11px] text-muted-foreground font-medium">
															{pct.toFixed(0)}%
														</span>
													)}
												</div>

												{/* Progress Bar */}
												<div className="relative h-2 w-full overflow-hidden rounded-full bg-secondary">
													<div
														className={cn(
															"h-full transition-all duration-300",
															isAlert ? "bg-destructive" : isWarning ? "bg-amber-500" : "bg-primary"
														)}
														style={{ width: `${Math.min(100, Math.max(0, pct))}%` }}
													/>
												</div>

												<div className="flex items-center justify-between text-[11px] text-muted-foreground">
													<span>
														{item.metric.includes("credit")
															? formatUsd(item.current_value)
															: formatCompactNumber(item.current_value)}
													</span>
													<span>
														Limit:{" "}
														{item.limit_value !== null && item.limit_value !== undefined
															? item.metric.includes("credit")
																? formatUsd(item.limit_value)
																: formatCompactNumber(item.limit_value)
															: "Unlimited"}
													</span>
												</div>

												{/* Advisory Banner */}
												{(isWarning || isAlert) && item.recommended_tier && (
													<div className="pt-1 text-[11px] text-destructive dark:text-destructive-foreground">
														Recommended tier:{" "}
														<strong className="capitalize">{item.recommended_tier}</strong>
													</div>
												)}
											</div>
										);
									})}
								</div>
							</CardContent>
						</Card>
					)}

					{/* HD-3: Top Sources Ranked Table */}
					<Card className="shadow-none">
						<CardHeader className="p-4 pb-3 flex flex-row items-center justify-between space-y-0">
							<div>
								<CardTitle className="text-sm font-semibold">Knowledge & Scraper Sources</CardTitle>
								<CardDescription className="text-xs mt-0.5">
									Ranked contribution of memories, citations, and coverage health
								</CardDescription>
							</div>

							<Button
								size="sm"
								variant="outline"
								onClick={() => setIsGapsDrawerOpen(true)}
								className="h-8 text-xs relative"
							>
								<AlertCircle className="h-3.5 w-3.5 mr-1.5 text-amber-500" />
								<span>Coverage Gaps</span>
								{summary.source_coverage_gap_count > 0 && (
									<Badge className="ml-1.5 px-1.5 py-0 text-[10px] bg-amber-500 text-white">
										{summary.source_coverage_gap_count}
									</Badge>
								)}
							</Button>
						</CardHeader>

						<CardContent className="p-0 border-t">
							{summary.top_sources.length === 0 ? (
								<div className="p-8 text-center text-xs text-muted-foreground">
									No sources detected for this period.
								</div>
							) : (
								<Table>
									<TableHeader>
										<TableRow className="text-xs">
											<TableHead className="w-12 text-center">#</TableHead>
											<TableHead>Source Type</TableHead>
											<TableHead className="text-right">Memories</TableHead>
											<TableHead className="text-right">Query Citations</TableHead>
											<TableHead className="text-right">Cost Attribution</TableHead>
											<TableHead className="text-center">Status</TableHead>
											<TableHead className="w-10"></TableHead>
										</TableRow>
									</TableHeader>
									<TableBody>
										{summary.top_sources.map((src, idx) => {
											const isGap = src.memory_count === 0;

											return (
												<TableRow
													key={src.source_type}
													onClick={() => {
														setSelectedSourceType(src.source_type);
														setIsDrilldownOpen(true);
													}}
													className="cursor-pointer text-xs hover:bg-muted/40 transition-colors"
												>
													<TableCell className="text-center font-mono text-muted-foreground">
														{idx + 1}
													</TableCell>
													<TableCell className="font-semibold capitalize">
														{src.source_type.replace(/_/g, " ")}
													</TableCell>
													<TableCell className="text-right font-mono">
														{src.memory_count.toLocaleString()}
													</TableCell>
													<TableCell className="text-right font-mono">
														{src.query_count.toLocaleString()}
													</TableCell>
													<TableCell className="text-right font-mono">
														{summary.is_public_snapshot || src.cost_micros === null
															? "Protected"
															: formatUsd(src.cost_micros)}
													</TableCell>
													<TableCell className="text-center">
														{isGap ? (
															<Badge
																variant="outline"
																className="text-amber-600 border-amber-500/40 text-[10px]"
															>
																Gap Detected
															</Badge>
														) : (
															<Badge
																variant="secondary"
																className="text-emerald-600 dark:text-emerald-400 text-[10px]"
															>
																Active
															</Badge>
														)}
													</TableCell>
													<TableCell>
														<ChevronRight className="h-4 w-4 text-muted-foreground" />
													</TableCell>
												</TableRow>
											);
										})}
									</TableBody>
								</Table>
							)}
						</CardContent>
					</Card>
				</>
			)}

			{/* HD-4: Coverage Gap Drawer */}
			<CoverageGapDrawer
				isOpen={isGapsDrawerOpen}
				onClose={() => setIsGapsDrawerOpen(false)}
				gaps={gapsData?.gaps || []}
				workspaceId={workspaceId}
			/>

			{/* HD-5: Source Drill-Down Sheet */}
			<SourceDrilldownSheet
				workspaceId={workspaceId}
				sourceType={selectedSourceType}
				isOpen={isDrilldownOpen}
				onClose={() => {
					setIsDrilldownOpen(false);
					setSelectedSourceType(null);
				}}
				isPublicSnapshot={summary.is_public_snapshot}
			/>
		</div>
	);
}
