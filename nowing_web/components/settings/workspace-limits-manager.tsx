"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Calendar, ExternalLink, ShieldAlert, Sparkles, Undo2 } from "lucide-react";
import { useTranslations } from "next-intl";
import { useState } from "react";
import { toast } from "sonner";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import {
	Dialog,
	DialogContent,
	DialogDescription,
	DialogFooter,
	DialogHeader,
	DialogTitle,
} from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
import { Progress } from "@/components/ui/progress";
import { Skeleton } from "@/components/ui/skeleton";
import { Switch } from "@/components/ui/switch";
import {
	Table,
	TableBody,
	TableCell,
	TableHead,
	TableHeader,
	TableRow,
} from "@/components/ui/table";
import type {
	PlanDefinition,
	SubscriptionChangeConflictDetail,
} from "@/contracts/types/workspace.types";
import { workspacesApiService } from "@/lib/apis/workspaces-api.service";
import { AppError } from "@/lib/error";
import { cacheKeys } from "@/lib/query-client/cache-keys";

function formatNumber(value: number): string {
	return new Intl.NumberFormat().format(value);
}

function formatBytes(value: number): string {
	if (value <= 0) return "0 B";
	const units = ["B", "KB", "MB", "GB", "TB"];
	const i = Math.floor(Math.log10(value) / 3);
	const unit = units[Math.min(i, units.length - 1)];
	const scaled = value / 10 ** (i * 3);
	return `${scaled.toFixed(1)} ${unit}`;
}

function formatCurrency(priceMicros: number | null | undefined, currency = "USD"): string {
	if (!priceMicros || priceMicros <= 0) return "Free";
	const amount = priceMicros / 1_000_000;
	return new Intl.NumberFormat(undefined, {
		style: "currency",
		currency,
		maximumFractionDigits: 0,
	}).format(amount);
}

function formatDate(dateStr: string): string {
	try {
		return new Date(dateStr).toLocaleDateString(undefined, {
			year: "numeric",
			month: "short",
			day: "numeric",
		});
	} catch {
		return dateStr;
	}
}

interface LimitBarProps {
	title: string;
	used: number;
	limit: number | null;
	formatter?: (value: number) => string;
}

function LimitBar({ title, used, limit, formatter = formatNumber }: LimitBarProps) {
	const t = useTranslations("workspaceSettings");
	const unlimited = limit === null;
	const percentage = unlimited ? 0 : limit > 0 ? Math.min(100, (used / limit) * 100) : 0;
	const nearLimit = !unlimited && percentage >= 80;

	return (
		<div className="space-y-2">
			<div className="flex items-center justify-between text-sm">
				<span className="font-medium">{title}</span>
				<span className="text-muted-foreground">
					{unlimited
						? `${formatter(used)} / ${t("limits_unlimited")}`
						: `${formatter(used)} / ${formatter(limit)}`}
				</span>
			</div>
			{!unlimited && <Progress value={percentage} />}
			{nearLimit && (
				<p className="text-xs text-amber-600 dark:text-amber-400">{t("limits_near_limit")}</p>
			)}
		</div>
	);
}

interface WorkspaceLimitsManagerProps {
	workspaceId: string;
}

export function WorkspaceLimitsManager({ workspaceId }: WorkspaceLimitsManagerProps) {
	const t = useTranslations("workspaceSettings");
	const numericId = Number(workspaceId);
	const queryClient = useQueryClient();

	const [isChangeModalOpen, setIsChangeModalOpen] = useState(false);
	const [selectedPlanTier, setSelectedPlanTier] = useState<string | null>(null);
	const [immediateUpgrade, setImmediateUpgrade] = useState(false);
	const [conflictData, setConflictData] = useState<Record<
		string,
		SubscriptionChangeConflictDetail
	> | null>(null);

	// Fetch Subscription & Effective Limits
	const { data: subscriptionData, isLoading: isSubLoading } = useQuery({
		queryKey: cacheKeys.workspaces.subscription(numericId),
		queryFn: () => workspacesApiService.getWorkspaceSubscription(numericId),
		enabled: Number.isFinite(numericId) && numericId > 0,
	});

	// Fetch Subscription Changes History
	const { data: historyData, isLoading: isHistoryLoading } = useQuery({
		queryKey: cacheKeys.workspaces.subscriptionChanges(numericId),
		queryFn: () => workspacesApiService.listSubscriptionChanges(numericId),
		enabled: Number.isFinite(numericId) && numericId > 0,
	});

	const effectiveLimits = subscriptionData?.effective_limits;
	const currentPlanDef = subscriptionData?.plan_definition;
	const availablePlans = subscriptionData?.available_plans ?? [];
	const pendingChange = subscriptionData?.pending_change;
	const activeChange = subscriptionData?.active_change;

	const isReversible = Boolean(
		activeChange?.reversible_until && new Date(activeChange.reversible_until) > new Date()
	);

	// Mutation: Create Subscription Change
	const createChangeMutation = useMutation({
		mutationFn: (vars: { toPlan: string; immediate: boolean }) =>
			workspacesApiService.createSubscriptionChange(numericId, {
				to_plan: vars.toPlan,
				immediate: vars.immediate,
			}),
		onSuccess: (res) => {
			queryClient.invalidateQueries({ queryKey: cacheKeys.workspaces.subscription(numericId) });
			queryClient.invalidateQueries({ queryKey: cacheKeys.workspaces.limits(numericId) });
			queryClient.invalidateQueries({
				queryKey: cacheKeys.workspaces.subscriptionChanges(numericId),
			});
			setIsChangeModalOpen(false);
			setSelectedPlanTier(null);
			setImmediateUpgrade(false);
			toast.success(
				res.status === "active"
					? `Plan upgraded to ${res.to_plan} immediately.`
					: `Plan change to ${res.to_plan} scheduled for ${formatDate(res.effective_at)}.`
			);
		},
		onError: (err: unknown) => {
			if (err instanceof AppError && err.status === 409) {
				const detail = (
					err as unknown as {
						data?: { detail?: { conflicts?: Record<string, SubscriptionChangeConflictDetail> } };
					}
				)?.data?.detail;
				if (detail?.conflicts) {
					setConflictData(detail.conflicts);
					return;
				}
			}
			toast.error(err instanceof Error ? err.message : "Failed to change subscription plan");
		},
	});

	// Mutation: Cancel Subscription Change
	const cancelChangeMutation = useMutation({
		mutationFn: (changeId: string) =>
			workspacesApiService.cancelSubscriptionChange(numericId, changeId),
		onSuccess: () => {
			queryClient.invalidateQueries({ queryKey: cacheKeys.workspaces.subscription(numericId) });
			queryClient.invalidateQueries({
				queryKey: cacheKeys.workspaces.subscriptionChanges(numericId),
			});
			toast.success("Scheduled plan change cancelled.");
		},
		onError: (err: unknown) => {
			toast.error(err instanceof Error ? err.message : "Failed to cancel change");
		},
	});

	// Mutation: Revert Subscription Change
	const revertChangeMutation = useMutation({
		mutationFn: (changeId: string) =>
			workspacesApiService.revertSubscriptionChange(numericId, changeId),
		onSuccess: () => {
			queryClient.invalidateQueries({ queryKey: cacheKeys.workspaces.subscription(numericId) });
			queryClient.invalidateQueries({ queryKey: cacheKeys.workspaces.limits(numericId) });
			queryClient.invalidateQueries({
				queryKey: cacheKeys.workspaces.subscriptionChanges(numericId),
			});
			toast.success("Plan reverted successfully.");
		},
		onError: (err: unknown) => {
			toast.error(err instanceof Error ? err.message : "Failed to revert plan change");
		},
	});

	const upgradeUrl = process.env.NEXT_PUBLIC_UPGRADE_URL;

	const limits = [
		{
			key: "documents",
			title: t("limits_documents"),
			used: effectiveLimits?.usage.documents ?? 0,
			limit: effectiveLimits?.max_documents ?? null,
		},
		{
			key: "members",
			title: t("limits_members"),
			used: effectiveLimits?.usage.members ?? 0,
			limit: effectiveLimits?.max_members ?? null,
		},
		{
			key: "runs",
			title: t("limits_runs"),
			used: effectiveLimits?.usage.runs ?? 0,
			limit: effectiveLimits?.max_runs ?? null,
		},
		{
			key: "storage",
			title: t("limits_storage"),
			used: effectiveLimits?.usage.storage_bytes ?? 0,
			limit: effectiveLimits?.max_storage_bytes ?? null,
			formatter: formatBytes,
		},
		{
			key: "memories",
			title: t("limits_memories"),
			used: effectiveLimits?.usage.memory_count ?? 0,
			limit: effectiveLimits?.max_memory_count ?? null,
		},
		{
			key: "memory_storage",
			title: t("limits_memory_storage"),
			used: effectiveLimits?.usage.memory_bytes ?? 0,
			limit: effectiveLimits?.max_memory_bytes ?? null,
			formatter: formatBytes,
		},
		{
			key: "sources",
			title: t("limits_sources"),
			used: effectiveLimits?.usage.sources ?? 0,
			limit: effectiveLimits?.max_sources ?? null,
		},
		{
			key: "monthly_credits",
			title: t("limits_monthly_credits"),
			used: 0,
			limit: effectiveLimits?.max_monthly_credits ?? null,
		},
	];

	const showUpgradeCta =
		!!upgradeUrl &&
		limits.some(
			(item) => item.limit !== null && item.limit > 0 && (item.used / item.limit) * 100 >= 80
		);

	if (!Number.isFinite(numericId) || numericId <= 0) {
		return (
			<div className="flex min-h-[20rem] items-center justify-center">
				<p className="text-muted-foreground">{t("limits_invalid_workspace")}</p>
			</div>
		);
	}

	return (
		<div className="space-y-6">
			<div>
				<h1 className="font-serif text-2xl sm:text-3xl font-normal tracking-tight text-foreground">
					{t("limits_title")}
				</h1>
				<p className="text-xs sm:text-sm text-muted-foreground font-sans">
					{t("limits_description")}
				</p>
			</div>

			{/* Pending Change Banner */}
			{pendingChange && (
				<Alert className="border-amber-500/50 bg-amber-50/50 dark:bg-amber-950/20 text-amber-900 dark:text-amber-200">
					<Calendar className="h-5 w-5 text-amber-600 dark:text-amber-400" />
					<div className="flex flex-col sm:flex-row sm:items-center sm:justify-between w-full gap-3">
						<div>
							<AlertTitle className="font-semibold text-sm">
								{t("limits_scheduled_notice", {
									plan: pendingChange.to_plan.toUpperCase(),
									date: formatDate(pendingChange.effective_at),
								})}
							</AlertTitle>
							<AlertDescription className="text-xs text-amber-800 dark:text-amber-300">
								Your workspace will transition to the new plan on this date. You can cancel at any
								time before activation.
							</AlertDescription>
						</div>
						<Button
							variant="outline"
							size="sm"
							className="border-amber-600/30 hover:bg-amber-100 dark:hover:bg-amber-900/40 text-xs self-start sm:self-auto"
							onClick={() => cancelChangeMutation.mutate(pendingChange.id)}
							disabled={cancelChangeMutation.isPending}
						>
							{cancelChangeMutation.isPending ? "Cancelling..." : t("limits_cancel_change")}
						</Button>
					</div>
				</Alert>
			)}

			{/* Reversible Change Banner */}
			{activeChange && isReversible && (
				<Alert className="border-blue-500/50 bg-blue-50/50 dark:bg-blue-950/20 text-blue-900 dark:text-blue-200">
					<Undo2 className="h-5 w-5 text-blue-600 dark:text-blue-400" />
					<div className="flex flex-col sm:flex-row sm:items-center sm:justify-between w-full gap-3">
						<div>
							<AlertTitle className="font-semibold text-sm">
								{t("limits_revert_notice", {
									plan: (activeChange.from_plan || "previous").toUpperCase(),
									date: formatDate(activeChange.reversible_until || ""),
								})}
							</AlertTitle>
							<AlertDescription className="text-xs text-blue-800 dark:text-blue-300">
								7-day rollback protection active. You can safely return to your previous tier
								without losing limits.
							</AlertDescription>
						</div>
						<Button
							variant="outline"
							size="sm"
							className="border-blue-600/30 hover:bg-blue-100 dark:hover:bg-blue-900/40 text-xs self-start sm:self-auto"
							onClick={() => revertChangeMutation.mutate(activeChange.id)}
							disabled={revertChangeMutation.isPending}
						>
							{revertChangeMutation.isPending ? "Reverting..." : t("limits_revert_plan")}
						</Button>
					</div>
				</Alert>
			)}

			{/* Main Plan & Limits Card */}
			<Card>
				<CardHeader className="flex flex-col sm:flex-row sm:items-center sm:justify-between pb-4 gap-4">
					<div>
						<CardTitle className="text-base font-medium">{t("limits_plan_label")}</CardTitle>
						<CardDescription className="text-xs">
							{currentPlanDef?.support_level
								? `Support level: ${currentPlanDef.support_level}`
								: "Plan details"}
							{currentPlanDef?.price_micros !== undefined &&
								` • ${formatCurrency(currentPlanDef?.price_micros, currentPlanDef?.currency)}/month`}
						</CardDescription>
					</div>
					<div className="flex items-center gap-3">
						{isSubLoading ? (
							<Skeleton className="h-6 w-20" aria-hidden="true" />
						) : (
							<Badge variant="secondary" className="uppercase font-semibold tracking-wider text-xs">
								{effectiveLimits?.plan_tier ?? t("limits_plan_unknown")}
							</Badge>
						)}
						<Button variant="default" size="sm" onClick={() => setIsChangeModalOpen(true)}>
							<Sparkles className="mr-2 h-4 w-4" />
							{t("limits_change_plan")}
						</Button>
					</div>
				</CardHeader>
				<CardContent className="space-y-6">
					{isSubLoading
						? ["documents", "members", "runs", "storage"].map((key) => (
								<div key={key} className="space-y-2">
									<Skeleton className="h-4 w-32" aria-hidden="true" />
									<Skeleton className="h-4 w-full" />
								</div>
							))
						: limits.map((item) => (
								<LimitBar
									key={item.key}
									title={item.title}
									used={item.used}
									limit={item.limit}
									formatter={item.formatter}
								/>
							))}

					{showUpgradeCta && (
						<Button asChild variant="outline" className="w-full sm:w-auto">
							<a href={upgradeUrl} target="_blank" rel="noopener noreferrer">
								{t("limits_upgrade_cta")}
								<ExternalLink className="ml-2 h-4 w-4" aria-hidden="true" />
							</a>
						</Button>
					)}
				</CardContent>
			</Card>

			{/* Subscription Change History */}
			<Card>
				<CardHeader>
					<CardTitle className="text-base font-medium">{t("limits_history_title")}</CardTitle>
					<CardDescription className="text-xs">
						Audit trail of plan upgrades, downgrades, and cancellations.
					</CardDescription>
				</CardHeader>
				<CardContent>
					{isHistoryLoading ? (
						<div className="space-y-2">
							<Skeleton className="h-8 w-full" />
							<Skeleton className="h-8 w-full" />
						</div>
					) : !historyData || historyData.length === 0 ? (
						<p className="text-sm text-muted-foreground py-4 text-center">
							{t("limits_history_empty")}
						</p>
					) : (
						<Table>
							<TableHeader>
								<TableRow>
									<TableHead>From</TableHead>
									<TableHead>To</TableHead>
									<TableHead>Status</TableHead>
									<TableHead>Effective Date</TableHead>
									<TableHead>Requested</TableHead>
									<TableHead className="text-right">Action</TableHead>
								</TableRow>
							</TableHeader>
							<TableBody>
								{historyData.map((change) => {
									const isRowPending = change.status === "pending";
									const isRowReversible =
										change.status === "active" &&
										change.reversible_until &&
										new Date(change.reversible_until) > new Date();

									return (
										<TableRow key={change.id}>
											<TableCell className="uppercase font-medium text-xs">
												{change.from_plan || "—"}
											</TableCell>
											<TableCell className="uppercase font-medium text-xs">
												{change.to_plan}
											</TableCell>
											<TableCell>
												<Badge
													variant={
														change.status === "active"
															? "default"
															: change.status === "pending"
																? "secondary"
																: "outline"
													}
													className="capitalize text-xs"
												>
													{change.status}
												</Badge>
											</TableCell>
											<TableCell className="text-xs text-muted-foreground">
												{formatDate(change.effective_at)}
											</TableCell>
											<TableCell className="text-xs text-muted-foreground">
												{formatDate(change.created_at)}
											</TableCell>
											<TableCell className="text-right">
												{isRowPending && (
													<Button
														variant="ghost"
														size="sm"
														className="text-xs text-destructive hover:text-destructive"
														onClick={() => cancelChangeMutation.mutate(change.id)}
														disabled={cancelChangeMutation.isPending}
													>
														Cancel
													</Button>
												)}
												{isRowReversible && (
													<Button
														variant="ghost"
														size="sm"
														className="text-xs text-blue-600 hover:text-blue-700"
														onClick={() => revertChangeMutation.mutate(change.id)}
														disabled={revertChangeMutation.isPending}
													>
														Revert
													</Button>
												)}
											</TableCell>
										</TableRow>
									);
								})}
							</TableBody>
						</Table>
					)}
				</CardContent>
			</Card>

			{/* Plan Selection Modal */}
			<Dialog open={isChangeModalOpen} onOpenChange={setIsChangeModalOpen}>
				<DialogContent className="max-w-3xl">
					<DialogHeader>
						<DialogTitle>{t("limits_select_plan")}</DialogTitle>
						<DialogDescription>
							Choose the plan that best matches your team's workflow and intelligence requirements.
						</DialogDescription>
					</DialogHeader>

					<div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 py-4">
						{availablePlans.map((plan: PlanDefinition) => {
							const isCurrent =
								(effectiveLimits?.plan_tier || "").toLowerCase() === plan.plan_tier.toLowerCase();
							const isSelected = selectedPlanTier === plan.plan_tier;

							return (
								<Card
									key={plan.plan_tier}
									className={`cursor-pointer transition-all border ${
										isSelected
											? "border-primary ring-2 ring-primary/20 bg-accent/30"
											: isCurrent
												? "border-muted bg-muted/20"
												: "hover:border-primary/50"
									}`}
									onClick={() => !isCurrent && setSelectedPlanTier(plan.plan_tier)}
								>
									<CardHeader className="p-4 pb-2">
										<div className="flex items-center justify-between">
											<CardTitle className="text-sm font-semibold uppercase tracking-wider">
												{plan.plan_tier}
											</CardTitle>
											{isCurrent && (
												<Badge variant="outline" className="text-[10px] px-1.5 py-0">
													Current
												</Badge>
											)}
										</div>
										<div className="text-lg font-bold text-foreground mt-1">
											{formatCurrency(plan.price_micros, plan.currency)}
											<span className="text-xs font-normal text-muted-foreground">/mo</span>
										</div>
									</CardHeader>
									<CardContent className="p-4 pt-2 text-xs space-y-1.5 text-muted-foreground">
										<div>
											Docs:{" "}
											<span className="text-foreground font-medium">
												{plan.max_documents ?? "Unlimited"}
											</span>
										</div>
										<div>
											Members:{" "}
											<span className="text-foreground font-medium">
												{plan.max_members ?? "Unlimited"}
											</span>
										</div>
										<div>
											Runs:{" "}
											<span className="text-foreground font-medium">
												{plan.max_runs ?? "Unlimited"}
											</span>
										</div>
										<div>
											Storage:{" "}
											<span className="text-foreground font-medium">
												{plan.max_storage_bytes ? formatBytes(plan.max_storage_bytes) : "Unlimited"}
											</span>
										</div>
										{plan.support_level && (
											<div className="pt-2 text-[11px] text-primary font-medium">
												{plan.support_level} support
											</div>
										)}
									</CardContent>
								</Card>
							);
						})}
					</div>

					<div className="flex items-center justify-between border-t pt-4 px-1">
						<div className="space-y-0.5">
							<Label htmlFor="immediate-upgrade" className="text-sm font-medium">
								{t("limits_immediate_upgrade")}
							</Label>
							<p className="text-xs text-muted-foreground">{t("limits_immediate_upgrade_desc")}</p>
						</div>
						<Switch
							id="immediate-upgrade"
							checked={immediateUpgrade}
							onCheckedChange={setImmediateUpgrade}
						/>
					</div>

					<DialogFooter className="gap-2 sm:gap-0">
						<Button variant="outline" onClick={() => setIsChangeModalOpen(false)}>
							Cancel
						</Button>
						<Button
							disabled={!selectedPlanTier || createChangeMutation.isPending}
							onClick={() => {
								if (selectedPlanTier) {
									createChangeMutation.mutate({
										toPlan: selectedPlanTier,
										immediate: immediateUpgrade,
									});
								}
							}}
						>
							{createChangeMutation.isPending ? "Updating..." : "Confirm Plan"}
						</Button>
					</DialogFooter>
				</DialogContent>
			</Dialog>

			{/* Quota Conflict Dialog */}
			<Dialog open={Boolean(conflictData)} onOpenChange={(open) => !open && setConflictData(null)}>
				<DialogContent className="max-w-md">
					<DialogHeader>
						<div className="flex items-center gap-2 text-destructive">
							<ShieldAlert className="h-5 w-5" />
							<DialogTitle>{t("limits_quota_conflict_title")}</DialogTitle>
						</div>
						<DialogDescription className="text-xs">
							{t("limits_quota_conflict_desc")}
						</DialogDescription>
					</DialogHeader>

					<div className="py-2 space-y-3">
						{conflictData &&
							Object.entries(conflictData).map(([metric, detail]) => (
								<div
									key={metric}
									className="flex items-center justify-between p-3 rounded-md bg-destructive/10 border border-destructive/20 text-xs"
								>
									<span className="font-semibold capitalize">{metric}</span>
									<span className="text-destructive font-mono">
										Current:{" "}
										{metric.includes("bytes")
											? formatBytes(detail.current)
											: formatNumber(detail.current)}{" "}
										/ Limit:{" "}
										{metric.includes("bytes")
											? formatBytes(detail.limit)
											: formatNumber(detail.limit)}
									</span>
								</div>
							))}
					</div>

					<DialogFooter>
						<Button variant="default" onClick={() => setConflictData(null)}>
							Understood
						</Button>
					</DialogFooter>
				</DialogContent>
			</Dialog>
		</div>
	);
}

export function isAffordanceDisabled(
	limits:
		| {
				max_members?: number | null;
				max_documents?: number | null;
				max_storage_bytes?: number | null;
				usage?: { members?: number; documents?: number; storage_bytes?: number };
		  }
		| null
		| undefined,
	affordance: "invite_member" | "upload_document"
): { disabled: boolean; reason?: string } {
	if (!limits) return { disabled: false };
	if (affordance === "invite_member") {
		if (
			typeof limits.max_members === "number" &&
			limits.max_members > 0 &&
			(limits.usage?.members ?? 0) >= limits.max_members
		) {
			return { disabled: true, reason: "Member limit reached for this workspace plan" };
		}
	}
	if (affordance === "upload_document") {
		if (
			typeof limits.max_documents === "number" &&
			limits.max_documents > 0 &&
			(limits.usage?.documents ?? 0) >= limits.max_documents
		) {
			return { disabled: true, reason: "Document limit reached for this workspace plan" };
		}
		if (
			typeof limits.max_storage_bytes === "number" &&
			limits.max_storage_bytes > 0 &&
			(limits.usage?.storage_bytes ?? 0) >= limits.max_storage_bytes
		) {
			return { disabled: true, reason: "Storage limit reached for this workspace plan" };
		}
	}
	return { disabled: false };
}
