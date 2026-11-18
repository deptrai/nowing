"use client";

import { useQuery } from "@tanstack/react-query";
import {
	Archive,
	ArrowLeft,
	CalendarClock,
	ChevronLeft,
	ChevronRight,
	Pause,
	Play,
	RefreshCw,
} from "lucide-react";
import Link from "next/link";
import { useTranslations } from "next-intl";
import { useState } from "react";
import { toast } from "sonner";

import { CampaignScheduleDialog } from "@/components/leads/campaigns/CampaignScheduleDialog";
import {
	AlertDialog,
	AlertDialogAction,
	AlertDialogCancel,
	AlertDialogContent,
	AlertDialogDescription,
	AlertDialogFooter,
	AlertDialogHeader,
	AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import {
	Table,
	TableBody,
	TableCell,
	TableHead,
	TableHeader,
	TableRow,
} from "@/components/ui/table";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import type {
	CampaignLeadItem,
	CampaignRun,
	CampaignStatus,
} from "@/contracts/types/campaign.types";
import { leadsApiService } from "@/lib/apis/leads-api.service";
import { AppError } from "@/lib/error";

const PAGE_SIZE = 20;

// Badge variant theo status — giữ đồng nhất với CampaignList (45.1).
const STATUS_BADGE: Record<
	CampaignStatus,
	{ variant: "default" | "secondary" | "destructive" | "outline"; className?: string }
> = {
	draft: { variant: "outline" },
	scheduled: { variant: "secondary" },
	running: { variant: "default" },
	paused: { variant: "secondary" },
	completed: { variant: "default" },
	failed: { variant: "destructive" },
	archived: { variant: "secondary", className: "text-muted-foreground" },
};

const RUN_STATUS_BADGE: Record<
	string,
	{ variant: "default" | "secondary" | "destructive" | "outline" }
> = {
	queued: { variant: "outline" },
	running: { variant: "default" },
	succeeded: { variant: "default" },
	failed: { variant: "destructive" },
};

const fmtDateTime = (iso?: string | null) => (iso ? new Date(iso).toLocaleString("vi-VN") : "-");

// campaignLeadItemSchema passthrough → field ngoài typed core là unknown.
const asStr = (v: unknown) => (typeof v === "string" && v ? v : "-");

const joinArr = (v: unknown) =>
	Array.isArray(v) && v.length ? v.map((x) => String(x)).join(", ") : "-";

// Leads/run — key thực tế finalize_campaign_run ghi (44.1): accepted_lead_count.
const runLeadCount = (run: CampaignRun) => {
	const s = run.stats;
	if (!s) return "-";
	const v = s.accepted_lead_count ?? s.accepted ?? s.total_accepted;
	return typeof v === "number" ? String(v) : "-";
};

function ConfigRow({ label, value }: { label: string; value: React.ReactNode }) {
	return (
		<div className="flex flex-col gap-0.5 sm:flex-row sm:gap-4">
			<span className="w-48 shrink-0 text-sm text-muted-foreground">{label}</span>
			<span className="text-sm">{value}</span>
		</div>
	);
}

function Pager({
	page,
	total,
	onPrev,
	onNext,
}: {
	page: number;
	total: number;
	onPrev: () => void;
	onNext: () => void;
}) {
	const t = useTranslations("leads");
	const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));
	return (
		<div className="flex items-center justify-between">
			<span className="text-sm text-muted-foreground">
				{t("campaigns_page_of", { page, total: totalPages })}
			</span>
			<div className="flex gap-2">
				<Button variant="outline" size="sm" disabled={page <= 1} onClick={onPrev}>
					<ChevronLeft className="mr-1 h-4 w-4" />
					{t("campaigns_prev")}
				</Button>
				<Button variant="outline" size="sm" disabled={page >= totalPages} onClick={onNext}>
					{t("campaigns_next")}
					<ChevronRight className="ml-1 h-4 w-4" />
				</Button>
			</div>
		</div>
	);
}

export function CampaignDetail({
	workspaceId,
	campaignId,
}: {
	workspaceId: string;
	campaignId: string;
}) {
	const t = useTranslations("leads");
	const [tab, setTab] = useState<"runs" | "leads">("runs");
	const [runsPage, setRunsPage] = useState(1);
	const [leadsPage, setLeadsPage] = useState(1);
	// 45.3: lifecycle actions — schedule dialog + confirm dialog + pending flag.
	const [scheduleOpen, setScheduleOpen] = useState(false);
	const [confirmAction, setConfirmAction] = useState<"archive" | "pause" | null>(null);
	const [actionPending, setActionPending] = useState(false);

	const campaignQuery = useQuery({
		queryKey: ["leads-campaign", workspaceId, campaignId],
		queryFn: () => leadsApiService.getCampaign(workspaceId, campaignId),
		retry: 1,
		enabled: !!workspaceId && !!campaignId,
	});

	// Fetch song song campaign + tab mặc định (runs); leads lazy khi mở tab.
	const runsQuery = useQuery({
		queryKey: ["leads-campaign-runs", workspaceId, campaignId, runsPage],
		queryFn: () =>
			leadsApiService.listCampaignRuns(workspaceId, campaignId, {
				page: runsPage,
				page_size: PAGE_SIZE,
			}),
		enabled: !!campaignId,
	});

	const leadsQuery = useQuery({
		queryKey: ["leads-campaign-leads", workspaceId, campaignId, leadsPage],
		queryFn: () =>
			leadsApiService.getCampaignLeads(workspaceId, campaignId, {
				page: leadsPage,
				page_size: PAGE_SIZE,
			}),
		enabled: !!campaignId && tab === "leads",
	});

	const campaign = campaignQuery.data;

	// ------------------------------------------------------------------
	// Error / loading states
	// ------------------------------------------------------------------
	if (campaignQuery.isPending) {
		return (
			<div className="space-y-3">
				<Skeleton className="h-8 w-64" />
				<Skeleton className="h-4 w-96" />
				<Skeleton className="h-40 w-full" />
			</div>
		);
	}

	if (campaignQuery.isError) {
		const err = campaignQuery.error;
		const status = err instanceof AppError ? err.status : undefined;
		return (
			<div className="flex flex-col items-start gap-3 py-10">
				<p className="text-sm text-muted-foreground">
					{status === 404
						? t("campaign_detail_not_found")
						: status === 403
							? t("campaigns_error_forbidden")
							: t("campaign_detail_error_load")}
				</p>
				<div className="flex gap-2">
					<Button variant="outline" asChild>
						<Link href={`/dashboard/${workspaceId}/leads/campaigns`}>
							<ArrowLeft className="mr-1 h-4 w-4" />
							{t("campaign_detail_back")}
						</Link>
					</Button>
					{status !== 404 && status !== 403 ? (
						<Button variant="outline" onClick={() => campaignQuery.refetch()}>
							{t("campaigns_retry")}
						</Button>
					) : null}
				</div>
			</div>
		);
	}

	if (!campaign) return null;

	const badge = STATUS_BADGE[campaign.status] ?? { variant: "outline" as const };
	const isSupply = campaign.direction === "supply";
	const skipped = campaign.skipped_by_quota ?? 0;

	const refreshActive = () => {
		campaignQuery.refetch();
		if (tab === "runs") runsQuery.refetch();
		else leadsQuery.refetch();
	};

	// 45.3: chạy action → toast success / error (409/422/429 → detail từ
	// backend, đã map sẵn vào AppError.message) → refetch.
	const runAction = async (fn: () => Promise<unknown>, successKey: string) => {
		try {
			setActionPending(true);
			await fn();
			toast.success(t(successKey));
			refreshActive();
		} catch (err) {
			toast.error(
				err instanceof AppError && err.message ? err.message : t("campaign_actions_error")
			);
		} finally {
			setActionPending(false);
		}
	};

	const doLaunch = () =>
		runAction(
			() => leadsApiService.launchCampaign(workspaceId, campaignId),
			"campaign_actions_launched"
		);
	const doPause = () =>
		runAction(
			() => leadsApiService.pauseCampaign(workspaceId, campaignId),
			"campaign_actions_paused"
		);
	const doResume = () =>
		runAction(
			() =>
				leadsApiService.updateCampaign(workspaceId, campaignId, {
					status: "scheduled",
				}),
			"campaign_actions_resumed"
		);
	const doArchive = () =>
		runAction(
			() =>
				leadsApiService.updateCampaign(workspaceId, campaignId, {
					status: "archived",
				}),
			"campaign_actions_archived"
		);

	return (
		<div className="space-y-4">
			{/* Header */}
			<div className="flex items-start justify-between gap-4">
				<div className="space-y-1">
					<Link
						href={`/dashboard/${workspaceId}/leads/campaigns`}
						className="inline-flex items-center text-sm text-muted-foreground hover:underline"
					>
						<ArrowLeft className="mr-1 h-4 w-4" />
						{t("campaign_detail_back")}
					</Link>
					<div className="flex flex-wrap items-center gap-2">
						<h1 className="text-2xl font-semibold">{campaign.name}</h1>
						<Badge variant={badge.variant} className={badge.className}>
							{t(`campaigns_status_${campaign.status}`)}
						</Badge>
						<Badge variant="outline">
							{isSupply ? t("campaigns_dir_supply") : t("campaigns_dir_demand")}
						</Badge>
						{campaign.source && campaign.source !== "created" ? (
							<Badge variant="outline" className="text-muted-foreground">
								{t("campaigns_auto_badge")}
							</Badge>
						) : null}
					</div>
					<div className="flex flex-wrap gap-x-6 gap-y-1 text-sm text-muted-foreground">
						<span>
							{t("campaign_detail_meta_created")}: {fmtDateTime(campaign.created_at)}
						</span>
						<span>
							{t("campaign_detail_meta_last_run")}: {fmtDateTime(campaign.last_run_at)}
						</span>
						{campaign.next_run_at ? (
							<span>
								{t("campaign_detail_meta_next_run")}: {fmtDateTime(campaign.next_run_at)}
							</span>
						) : null}
						<span>
							{t("campaign_detail_meta_leads")}: {campaign.collected_leads_count}
						</span>
						{skipped > 0 ? (
							<span>{t("campaign_detail_meta_skipped_quota", { count: skipped })}</span>
						) : null}
					</div>
				</div>
				{/* 45.3: action buttons theo status (matrix spec) */}
				<div className="flex flex-wrap items-center justify-end gap-2">
					{campaign.status === "draft" && (
						<>
							<Button size="sm" onClick={doLaunch} disabled={actionPending}>
								<Play className="mr-1 h-4 w-4" />
								{t("campaign_actions_launch")}
							</Button>
							<Button
								variant="outline"
								size="sm"
								onClick={() => setScheduleOpen(true)}
								disabled={actionPending}
							>
								<CalendarClock className="mr-1 h-4 w-4" />
								{t("campaign_actions_schedule")}
							</Button>
						</>
					)}
					{campaign.status === "scheduled" && (
						<>
							<Button variant="outline" size="sm" onClick={doPause} disabled={actionPending}>
								<Pause className="mr-1 h-4 w-4" />
								{t("campaign_actions_pause")}
							</Button>
							<Button
								variant="outline"
								size="sm"
								onClick={() => setScheduleOpen(true)}
								disabled={actionPending}
							>
								<CalendarClock className="mr-1 h-4 w-4" />
								{t("campaign_actions_edit_schedule")}
							</Button>
							<Button
								variant="outline"
								size="sm"
								onClick={() => setConfirmAction("archive")}
								disabled={actionPending}
							>
								<Archive className="mr-1 h-4 w-4" />
								{t("campaign_actions_archive")}
							</Button>
						</>
					)}
					{campaign.status === "running" && (
						<Button
							variant="outline"
							size="sm"
							onClick={() => setConfirmAction("pause")}
							disabled={actionPending}
						>
							<Pause className="mr-1 h-4 w-4" />
							{t("campaign_actions_pause")}
						</Button>
					)}
					{campaign.status === "paused" && (
						<>
							<Button size="sm" onClick={doResume} disabled={actionPending}>
								<Play className="mr-1 h-4 w-4" />
								{t("campaign_actions_resume")}
							</Button>
							<Button
								variant="outline"
								size="sm"
								onClick={() => setConfirmAction("archive")}
								disabled={actionPending}
							>
								<Archive className="mr-1 h-4 w-4" />
								{t("campaign_actions_archive")}
							</Button>
						</>
					)}
					{(campaign.status === "completed" || campaign.status === "failed") && (
						<>
							<Button size="sm" onClick={doLaunch} disabled={actionPending}>
								<Play className="mr-1 h-4 w-4" />
								{t("campaign_actions_relaunch")}
							</Button>
							<Button
								variant="outline"
								size="sm"
								onClick={() => setConfirmAction("archive")}
								disabled={actionPending}
							>
								<Archive className="mr-1 h-4 w-4" />
								{t("campaign_actions_archive")}
							</Button>
						</>
					)}
					<Button
						variant="ghost"
						size="icon"
						onClick={refreshActive}
						aria-label={t("campaign_detail_refresh")}
					>
						<RefreshCw className="h-4 w-4" />
					</Button>
				</div>
			</div>

			{/* Config card theo direction */}
			<Card>
				<CardHeader>
					<CardTitle className="text-base">{t("campaign_detail_config_title")}</CardTitle>
				</CardHeader>
				<CardContent className="space-y-2">
					{isSupply && campaign.supply_criteria ? (
						<>
							<ConfigRow
								label={t("campaign_detail_cfg_categories")}
								value={joinArr(campaign.supply_criteria.categories)}
							/>
							<ConfigRow
								label={t("campaign_detail_cfg_locations")}
								value={joinArr(campaign.supply_criteria.locations)}
							/>
							<ConfigRow
								label={t("campaign_detail_cfg_require_tax_id")}
								value={
									campaign.supply_criteria.require_tax_id
										? t("campaign_detail_yes")
										: t("campaign_detail_no")
								}
							/>
							<ConfigRow
								label={t("campaign_detail_cfg_min_rating")}
								value={campaign.supply_criteria.min_rating}
							/>
							<ConfigRow
								label={t("campaign_detail_cfg_require_verified")}
								value={
									campaign.supply_criteria.require_verified
										? t("campaign_detail_yes")
										: t("campaign_detail_no")
								}
							/>
						</>
					) : (
						<>
							<ConfigRow
								label={t("campaign_detail_cfg_industries")}
								value={joinArr(campaign.icp_config?.target_industries)}
							/>
							<ConfigRow
								label={t("campaign_detail_cfg_locations")}
								value={joinArr(campaign.icp_config?.locations)}
							/>
							<ConfigRow
								label={t("campaign_detail_cfg_intents")}
								value={joinArr(campaign.icp_config?.intents)}
							/>
							<ConfigRow
								label={t("campaign_detail_cfg_negative_keywords")}
								value={joinArr(campaign.icp_config?.negative_keywords)}
							/>
							<ConfigRow
								label={t("campaign_detail_cfg_tech_stack")}
								value={joinArr(campaign.icp_config?.tech_stack)}
							/>
							<ConfigRow
								label={t("campaign_detail_cfg_min_fit_score")}
								value={campaign.source_budget_config?.min_fit_score ?? "-"}
							/>
						</>
					)}
					<ConfigRow
						label={t("campaign_detail_cfg_launch")}
						value={
							campaign.launch_config?.schedule_type === "recurring"
								? t("campaign_detail_launch_recurring")
								: t("campaign_detail_launch_once")
						}
					/>
					{campaign.schedule_frequency || campaign.schedule_cron ? (
						<ConfigRow
							label={t("campaign_detail_cfg_schedule")}
							value={campaign.schedule_frequency ?? campaign.schedule_cron}
						/>
					) : null}
					{campaign.max_runs ? (
						<ConfigRow label={t("campaign_detail_cfg_max_runs")} value={campaign.max_runs} />
					) : null}
				</CardContent>
			</Card>

			{/* Tabs Runs / Leads — server-paginated */}
			<Tabs value={tab} onValueChange={(v) => setTab(v as "runs" | "leads")}>
				<TabsList>
					<TabsTrigger value="runs">{t("campaign_detail_tab_runs")}</TabsTrigger>
					<TabsTrigger value="leads">{t("campaign_detail_tab_leads")}</TabsTrigger>
				</TabsList>

				<TabsContent value="runs" className="space-y-3">
					{runsQuery.isPending ? (
						<Skeleton className="h-40 w-full" />
					) : runsQuery.isError ? (
						<p className="py-6 text-sm text-muted-foreground">{t("campaign_detail_error_load")}</p>
					) : runsQuery.data && runsQuery.data.total === 0 ? (
						<p className="py-6 text-sm text-muted-foreground">{t("campaign_detail_runs_empty")}</p>
					) : (
						<>
							<Table>
								<TableHeader>
									<TableRow>
										<TableHead>{t("campaign_detail_col_status")}</TableHead>
										<TableHead>{t("campaign_detail_col_trigger")}</TableHead>
										<TableHead>{t("campaign_detail_col_started")}</TableHead>
										<TableHead>{t("campaign_detail_col_finished")}</TableHead>
										<TableHead className="text-right">{t("campaign_detail_col_leads")}</TableHead>
										<TableHead className="text-right">{t("campaign_detail_col_usage")}</TableHead>
										<TableHead>{t("campaign_detail_col_error")}</TableHead>
									</TableRow>
								</TableHeader>
								<TableBody>
									{(runsQuery.data?.items ?? []).map((run) => {
										const rb = RUN_STATUS_BADGE[run.status] ?? { variant: "secondary" as const };
										return (
											<TableRow key={run.id}>
												<TableCell>
													<Badge variant={rb.variant}>{run.status}</Badge>
												</TableCell>
												<TableCell>{run.trigger}</TableCell>
												<TableCell>{fmtDateTime(run.started_at)}</TableCell>
												<TableCell>{fmtDateTime(run.finished_at)}</TableCell>
												<TableCell className="text-right">{runLeadCount(run)}</TableCell>
												<TableCell className="text-right">{run.cost_micros ?? "-"}</TableCell>
												<TableCell className="text-muted-foreground">
													<span className="block max-w-48 truncate" title={run.error ?? undefined}>
														{run.error ?? "-"}
													</span>
												</TableCell>
											</TableRow>
										);
									})}
								</TableBody>
							</Table>
							<Pager
								page={runsPage}
								total={runsQuery.data?.total ?? 0}
								onPrev={() => setRunsPage((p) => Math.max(1, p - 1))}
								onNext={() => setRunsPage((p) => p + 1)}
							/>
						</>
					)}
				</TabsContent>

				<TabsContent value="leads" className="space-y-3">
					{leadsQuery.isPending ? (
						<Skeleton className="h-40 w-full" />
					) : leadsQuery.isError ? (
						<p className="py-6 text-sm text-muted-foreground">{t("campaign_detail_error_load")}</p>
					) : leadsQuery.data && leadsQuery.data.total === 0 ? (
						<p className="py-6 text-sm text-muted-foreground">{t("campaign_detail_leads_empty")}</p>
					) : (
						<>
							<Table>
								<TableHeader>
									<TableRow>
										<TableHead>{t("campaign_detail_col_company")}</TableHead>
										<TableHead>{t("campaign_detail_col_role")}</TableHead>
										<TableHead>{t("campaign_detail_col_source")}</TableHead>
										<TableHead>{t("campaign_detail_col_added")}</TableHead>
									</TableRow>
								</TableHeader>
								<TableBody>
									{(leadsQuery.data?.items ?? []).map((item: CampaignLeadItem) => (
										<TableRow key={item.id}>
											<TableCell className="font-medium">{asStr(item.company_name)}</TableCell>
											<TableCell>
												<Badge variant="outline">{item.lead_role}</Badge>
											</TableCell>
											<TableCell>{asStr(item.source)}</TableCell>
											<TableCell>{fmtDateTime(item.added_at)}</TableCell>
										</TableRow>
									))}
								</TableBody>
							</Table>
							<Pager
								page={leadsPage}
								total={leadsQuery.data?.total ?? 0}
								onPrev={() => setLeadsPage((p) => Math.max(1, p - 1))}
								onNext={() => setLeadsPage((p) => p + 1)}
							/>
						</>
					)}
				</TabsContent>
			</Tabs>

			{/* 45.3: schedule editor + confirm dialogs */}
			<CampaignScheduleDialog
				workspaceId={workspaceId}
				campaign={campaign}
				open={scheduleOpen}
				onOpenChange={setScheduleOpen}
				onSaved={refreshActive}
			/>
			<AlertDialog
				open={confirmAction !== null}
				onOpenChange={(open) => {
					if (!open) setConfirmAction(null);
				}}
			>
				<AlertDialogContent>
					<AlertDialogHeader>
						<AlertDialogTitle>
							{confirmAction === "pause"
								? t("campaign_actions_confirm_pause_title")
								: t("campaign_actions_confirm_archive_title")}
						</AlertDialogTitle>
						<AlertDialogDescription>
							{confirmAction === "pause"
								? t("campaign_actions_confirm_pause_desc")
								: t("campaign_actions_confirm_archive_desc")}
						</AlertDialogDescription>
					</AlertDialogHeader>
					<AlertDialogFooter>
						<AlertDialogCancel>{t("campaign_actions_confirm_cancel")}</AlertDialogCancel>
						<AlertDialogAction
							disabled={actionPending}
							onClick={() => {
								const action = confirmAction;
								setConfirmAction(null);
								if (action === "pause") doPause();
								else if (action === "archive") doArchive();
							}}
						>
							{t("campaign_actions_confirm_ok")}
						</AlertDialogAction>
					</AlertDialogFooter>
				</AlertDialogContent>
			</AlertDialog>
		</div>
	);
}
