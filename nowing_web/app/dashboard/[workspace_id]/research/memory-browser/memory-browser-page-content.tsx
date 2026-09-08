"use client";

import { format, subDays, subHours } from "date-fns";
import { ChevronDown, ChevronUp, ExternalLink, Flag, Search, X } from "lucide-react";
import { useTranslations } from "next-intl";
import { useCallback, useEffect, useState } from "react";
import { usePermissionGate } from "@/atoms/members/members-query.atoms";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
	Dialog,
	DialogContent,
	DialogDescription,
	DialogFooter,
	DialogHeader,
	DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
	Select,
	SelectContent,
	SelectItem,
	SelectTrigger,
	SelectValue,
} from "@/components/ui/select";
import { Slider } from "@/components/ui/slider";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Textarea } from "@/components/ui/textarea";
import type {
	MemoryBrowserDetailResponse,
	MemoryBrowserListItem,
	MemoryBrowserTimelineResponse,
} from "@/contracts/types/memory-browser.types";
import { memoryBrowserApiService } from "@/lib/apis/memory-browser-api.service";

// Source types hiển thị trong filter — kết hợp MemorySourceType + connector aliases
// (connector-* ánh xạ sang document phía server theo CONNECTOR_SOURCE_TYPE_ALIASES).
const SOURCE_TYPE_OPTIONS = [
	"document",
	"chat_message",
	"scraper_run",
	"manual",
	"signal",
	"lead",
	"lead_score",
	"enrichment",
	"crm_connection",
	"crm_sync",
	"sequence_event",
	"outcome_event",
	"unknown",
	"luma_connector",
	"elasticsearch_connector",
	"webcrawler_connector",
	"bookstack_connector",
	"circleback_connector",
	"obsidian_connector",
	"mcp_connector",
	"exa_mcp_connector",
	"dropbox_connector",
	"composio_google_drive_connector",
	"composio_gmail_connector",
	"composio_google_calendar_connector",
	"rss_feed",
] as const;

const PAGE_SIZE_OPTIONS = [25, 50, 100] as const;

type ViewMode = "list" | "timeline";
type DatePreset = "24h" | "7d" | "30d" | "90d" | "custom";

interface MemoryBrowserPageContentProps {
	workspaceId: number;
}

export function MemoryBrowserPageContent({ workspaceId }: MemoryBrowserPageContentProps) {
	const t = useTranslations("MemoryBrowser");
	const canUpdateMemory = usePermissionGate("memory:update");

	// ---- Data state ----
	const [items, setItems] = useState<MemoryBrowserListItem[]>([]);
	const [total, setTotal] = useState(0);
	const [timeline, setTimeline] = useState<MemoryBrowserTimelineResponse | null>(null);
	const [creators, setCreators] = useState<{ id: string; email?: string | null }[]>([]);
	const [selected, setSelected] = useState<MemoryBrowserDetailResponse | null>(null);

	// ---- Filter / pagination state ----
	const [view, setView] = useState<ViewMode>("list");
	const [page, setPage] = useState(1);
	const [pageSize, setPageSize] = useState<number>(50);
	const [keyword, setKeyword] = useState("");
	const [selectedSourceTypes, setSelectedSourceTypes] = useState<Set<string>>(new Set());
	const [confidenceRange, setConfidenceRange] = useState<[number, number]>([0, 1]);
	const [datePreset, setDatePreset] = useState<DatePreset | "">("");
	const [customFrom, setCustomFrom] = useState("");
	const [customTo, setCustomTo] = useState("");
	const [createdBy, setCreatedBy] = useState<string>("");

	// ---- UI state ----
	const [loading, setLoading] = useState(false);
	const [error, setError] = useState<string | null>(null);
	const [flagDialogOpen, setFlagDialogOpen] = useState(false);
	const [flagTarget, setFlagTarget] = useState<MemoryBrowserListItem | null>(null);
	const [flagReason, setFlagReason] = useState("");
	const [flagSubmitting, setFlagSubmitting] = useState(false);
	const [detailExpanded, setDetailExpanded] = useState(false);
	const [filtersOpen, setFiltersOpen] = useState(false);

	// ---- Date helpers ----
	const resolveDateRange = useCallback((): { after?: string; before?: string } => {
		if (!datePreset) return {};
		if (datePreset === "custom") {
			return {
				after: customFrom ? new Date(customFrom).toISOString() : undefined,
				before: customTo ? new Date(customTo).toISOString() : undefined,
			};
		}
		const now = new Date();
		let after: Date;
		switch (datePreset) {
			case "24h":
				after = subHours(now, 24);
				break;
			case "7d":
				after = subDays(now, 7);
				break;
			case "30d":
				after = subDays(now, 30);
				break;
			case "90d":
				after = subDays(now, 90);
				break;
		}
		return { after: after.toISOString(), before: now.toISOString() };
	}, [datePreset, customFrom, customTo]);

	// ---- Data fetching ----
	const fetchList = useCallback(async () => {
		setLoading(true);
		setError(null);
		try {
			const { after, before } = resolveDateRange();
			const res = await memoryBrowserApiService.listMemories(workspaceId, {
				page,
				page_size: pageSize,
				source_types: selectedSourceTypes.size
					? Array.from(selectedSourceTypes).join(",")
					: undefined,
				confidence_min: confidenceRange[0],
				confidence_max: confidenceRange[1],
				created_after: after,
				created_before: before,
				created_by: createdBy || undefined,
				keyword: keyword || undefined,
			});
			setItems(res.items);
			setTotal(res.total);
		} catch (err) {
			setError(err instanceof Error ? err.message : t("error"));
		} finally {
			setLoading(false);
		}
	}, [
		workspaceId,
		page,
		pageSize,
		selectedSourceTypes,
		confidenceRange,
		resolveDateRange,
		createdBy,
		keyword,
		t,
	]);

	const fetchTimeline = useCallback(async () => {
		setLoading(true);
		setError(null);
		try {
			const res = await memoryBrowserApiService.getTimeline(workspaceId);
			setTimeline(res);
		} catch (err) {
			setError(err instanceof Error ? err.message : t("error"));
		} finally {
			setLoading(false);
		}
	}, [workspaceId, t]);

	const fetchCreators = useCallback(async () => {
		try {
			const res = await memoryBrowserApiService.listCreators(workspaceId);
			setCreators(res.items);
		} catch {
			// Silently fail — creators filter just won't populate
		}
	}, [workspaceId]);

	// ---- Effects ----
	useEffect(() => {
		if (view === "list") {
			fetchList();
		} else {
			fetchTimeline();
		}
	}, [view, fetchList, fetchTimeline]);

	useEffect(() => {
		fetchCreators();
	}, [fetchCreators]);

	// Reset page when filters change
	// biome-ignore lint/correctness/useExhaustiveDependencies: intentionally reset page on any filter change
	useEffect(() => {
		setPage(1);
	}, [
		selectedSourceTypes,
		confidenceRange,
		datePreset,
		customFrom,
		customTo,
		createdBy,
		keyword,
		pageSize,
	]);

	// ---- Handlers ----
	const handleSearch = () => {
		setPage(1);
		fetchList();
	};

	const handleSourceTypeToggle = (sourceType: string) => {
		setSelectedSourceTypes((prev) => {
			const next = new Set(prev);
			if (next.has(sourceType)) {
				next.delete(sourceType);
			} else {
				next.add(sourceType);
			}
			return next;
		});
	};

	const handleView = async (memoryId: number) => {
		try {
			const detail = await memoryBrowserApiService.getMemoryDetail(workspaceId, memoryId);
			setSelected(detail);
			setDetailExpanded(false);
		} catch (err) {
			setError(err instanceof Error ? err.message : t("error"));
		}
	};

	const openFlagDialog = (item: MemoryBrowserListItem) => {
		setFlagTarget(item);
		setFlagReason("");
		setFlagDialogOpen(true);
	};

	const handleFlagSubmit = async () => {
		if (!flagTarget || !flagReason.trim()) return;
		setFlagSubmitting(true);
		try {
			await memoryBrowserApiService.flagForReview(workspaceId, flagTarget.id, flagReason.trim());
			setFlagDialogOpen(false);
			setFlagTarget(null);
			setFlagReason("");
			fetchList();
		} catch (err) {
			setError(err instanceof Error ? err.message : t("error"));
		} finally {
			setFlagSubmitting(false);
		}
	};

	const clearFilters = () => {
		setSelectedSourceTypes(new Set());
		setConfidenceRange([0, 1]);
		setDatePreset("");
		setCustomFrom("");
		setCustomTo("");
		setCreatedBy("");
		setKeyword("");
		setPage(1);
	};

	const hasActiveFilters =
		selectedSourceTypes.size > 0 ||
		confidenceRange[0] > 0 ||
		confidenceRange[1] < 1 ||
		datePreset !== "" ||
		createdBy !== "" ||
		keyword !== "";

	const totalPages = Math.ceil(total / pageSize);
	const startItem = total === 0 ? 0 : (page - 1) * pageSize + 1;
	const endItem = Math.min(page * pageSize, total);

	// ---- Render helpers ----
	const renderSourceBadge = (item: MemoryBrowserListItem) => {
		const label = item.source_url ? (
			<a
				href={item.source_url}
				className="text-primary hover:underline inline-flex items-center gap-1"
				target="_blank"
				rel="noopener noreferrer"
			>
				{item.source_type}
				<ExternalLink className="h-3 w-3" aria-hidden="true" />
			</a>
		) : (
			item.source_type
		);
		return label;
	};

	const renderItemRow = (item: MemoryBrowserListItem) => (
		<tr key={item.id} className="border-t">
			<td className="px-4 py-2">
				<div className="flex items-center gap-2">
					{item.content_snippet}
					{item.relation_marker && (
						<Badge
							variant="outline"
							className="text-xs"
							aria-label={t("relationMarker", { type: item.relation_marker })}
						>
							{item.relation_marker}
						</Badge>
					)}
				</div>
			</td>
			<td className="px-4 py-2">{renderSourceBadge(item)}</td>
			<td className="px-4 py-2">{item.confidence != null ? item.confidence.toFixed(2) : "—"}</td>
			<td className="px-4 py-2">{format(new Date(item.created_at), "MMM d, yyyy")}</td>
			<td className="px-4 py-2">{item.version_count}</td>
			<td className="px-4 py-2 space-x-2">
				<Button
					size="sm"
					variant="outline"
					onClick={() => handleView(item.id)}
					aria-label={t("view")}
				>
					{t("view")}
				</Button>
				{canUpdateMemory && (
					<Button
						size="sm"
						variant="secondary"
						onClick={() => openFlagDialog(item)}
						aria-label={t("flag")}
					>
						<Flag className="h-3 w-3 mr-1" aria-hidden="true" />
						{t("flag")}
					</Button>
				)}
			</td>
		</tr>
	);

	const renderTimelineItem = (item: MemoryBrowserListItem) => (
		<div key={item.id} className="border rounded-lg p-4 space-y-2">
			<div className="flex items-start justify-between">
				<div className="flex-1">
					<p className="text-sm">{item.content_snippet}</p>
					<div className="flex items-center gap-2 mt-2 text-xs text-muted-foreground">
						<span>{format(new Date(item.created_at), "MMM d, yyyy HH:mm")}</span>
						<span>•</span>
						<span>{item.source_type}</span>
						{item.confidence != null && (
							<>
								<span>•</span>
								<span>{item.confidence.toFixed(2)}</span>
							</>
						)}
						{item.relation_marker && (
							<>
								<span>•</span>
								<Badge variant="secondary" className="text-xs">
									{item.relation_marker}
								</Badge>
							</>
						)}
					</div>
				</div>
				<div className="flex gap-2 ml-4">
					<Button
						size="sm"
						variant="outline"
						onClick={() => handleView(item.id)}
						aria-label={t("view")}
					>
						{t("view")}
					</Button>
					{canUpdateMemory && (
						<Button
							size="sm"
							variant="secondary"
							onClick={() => openFlagDialog(item)}
							aria-label={t("flag")}
						>
							<Flag className="h-3 w-3" aria-hidden="true" />
						</Button>
					)}
				</div>
			</div>
		</div>
	);

	const renderCitationSource = (detail: MemoryBrowserDetailResponse) => {
		const c = detail.citations;
		if (!c) return null;

		const hasSourceInfo =
			c.source_run_id ||
			c.source_uuid ||
			c.source_entity_type ||
			c.source_capability ||
			c.source_input;

		if (!hasSourceInfo) return null;

		return (
			<div className="border rounded-lg p-4 space-y-3">
				<div className="flex items-center justify-between">
					<h4 className="font-semibold">{t("citations")}</h4>
					<Button
						size="sm"
						variant="ghost"
						onClick={() => setDetailExpanded(!detailExpanded)}
						aria-expanded={detailExpanded}
						aria-label={detailExpanded ? t("collapse") : t("expand")}
					>
						{detailExpanded ? (
							<ChevronUp className="h-4 w-4" />
						) : (
							<ChevronDown className="h-4 w-4" />
						)}
					</Button>
				</div>
				{detailExpanded && (
					<div className="space-y-2 text-sm">
						{c.source_run_id && (
							<div>
								<span className="font-medium">{t("sourceRun")}: </span>
								<code className="text-xs bg-muted px-1 py-0.5 rounded">{c.source_run_id}</code>
							</div>
						)}
						{c.source_uuid && (
							<div>
								<span className="font-medium">UUID: </span>
								<code className="text-xs bg-muted px-1 py-0.5 rounded">{c.source_uuid}</code>
							</div>
						)}
						{c.source_entity_type && (
							<div>
								<span className="font-medium">{t("sourceType")}: </span>
								<Badge variant="outline">{c.source_entity_type}</Badge>
							</div>
						)}
						{c.source_capability && (
							<div>
								<span className="font-medium">{t("capability")}: </span>
								<code className="text-xs bg-muted px-1 py-0.5 rounded">{c.source_capability}</code>
							</div>
						)}
						{c.source_input && (
							<div>
								<span className="font-medium">{t("sourceInput")}: </span>
								<pre className="text-xs bg-muted p-2 rounded mt-1 overflow-auto max-h-40">
									{JSON.stringify(c.source_input, null, 2)}
								</pre>
							</div>
						)}
					</div>
				)}
			</div>
		);
	};

	return (
		<div className="space-y-4">
			<Card>
				<CardHeader>
					<CardTitle>{t("title")}</CardTitle>
				</CardHeader>
				<CardContent className="space-y-4">
					{/* Search + View Toggle */}
					<div className="flex items-center gap-4">
						<div className="flex-1 flex items-center gap-2">
							<div className="relative flex-1">
								<Search
									className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground"
									aria-hidden="true"
								/>
								<Input
									placeholder={t("searchPlaceholder")}
									value={keyword}
									onChange={(e) => setKeyword(e.target.value)}
									onKeyDown={(e) => e.key === "Enter" && handleSearch()}
									className="pl-9"
									aria-label={t("search")}
								/>
							</div>
							<Button onClick={handleSearch} disabled={loading} aria-label={t("search")}>
								{t("search")}
							</Button>
						</div>

						<Tabs value={view} onValueChange={(v) => setView(v as ViewMode)}>
							<TabsList>
								<TabsTrigger value="list" aria-label={t("viewList")}>
									{t("viewList")}
								</TabsTrigger>
								<TabsTrigger value="timeline" aria-label={t("viewTimeline")}>
									{t("viewTimeline")}
								</TabsTrigger>
							</TabsList>
						</Tabs>
					</div>

					{/* Filters */}
					<div className="border rounded-lg">
						<button
							type="button"
							onClick={() => setFiltersOpen(!filtersOpen)}
							className="w-full flex items-center justify-between px-4 py-3 text-left hover:bg-muted/50 transition-colors"
							aria-expanded={filtersOpen}
							aria-controls="filters-panel"
						>
							<div className="flex items-center gap-2">
								<span className="font-medium">{t("filters")}</span>
								{hasActiveFilters && (
									<Badge variant="secondary" className="text-xs">
										{selectedSourceTypes.size +
											(confidenceRange[0] > 0 || confidenceRange[1] < 1 ? 1 : 0) +
											(datePreset ? 1 : 0) +
											(createdBy ? 1 : 0) +
											(keyword ? 1 : 0)}
									</Badge>
								)}
							</div>
							{filtersOpen ? (
								<ChevronUp className="h-4 w-4" />
							) : (
								<ChevronDown className="h-4 w-4" />
							)}
						</button>

						{filtersOpen && (
							<div id="filters-panel" className="border-t p-4 space-y-4">
								{/* Source Type Multi-Select */}
								<div className="space-y-2">
									<Label id="source-types-label">{t("sourceType")}</Label>
									<fieldset className="flex flex-wrap gap-2" aria-labelledby="source-types-label">
										{SOURCE_TYPE_OPTIONS.map((st) => (
											<Badge
												key={st}
												variant={selectedSourceTypes.has(st) ? "default" : "outline"}
												className="cursor-pointer"
												onClick={() => handleSourceTypeToggle(st)}
												onKeyDown={(e) => {
													if (e.key === "Enter" || e.key === " ") {
														e.preventDefault();
														handleSourceTypeToggle(st);
													}
												}}
												tabIndex={0}
												role="checkbox"
												aria-checked={selectedSourceTypes.has(st)}
												aria-label={`${t("sourceType")}: ${st}`}
											>
												{st}
											</Badge>
										))}
									</fieldset>
								</div>

								{/* Confidence Range */}
								<div className="space-y-2">
									<Label id="confidence-label">{t("confidenceRange")}</Label>
									<div className="px-2">
										<Slider
											value={confidenceRange}
											onValueChange={(v) => setConfidenceRange(v as [number, number])}
											min={0}
											max={1}
											step={0.05}
											aria-labelledby="confidence-label"
											aria-label={t("confidenceRange")}
										/>
										<div className="flex justify-between text-xs text-muted-foreground mt-1">
											<span>{confidenceRange[0].toFixed(2)}</span>
											<span>{confidenceRange[1].toFixed(2)}</span>
										</div>
									</div>
								</div>

								{/* Date Range */}
								<div className="grid grid-cols-2 gap-4">
									<div className="space-y-2">
										<Label htmlFor="date-preset">{t("datePresets")}</Label>
										<Select
											value={datePreset}
											onValueChange={(v) => setDatePreset(v as DatePreset | "")}
										>
											<SelectTrigger id="date-preset" aria-label={t("datePresets")}>
												<SelectValue placeholder={t("datePresets")} />
											</SelectTrigger>
											<SelectContent>
												<SelectItem value="24h">{t("preset24h")}</SelectItem>
												<SelectItem value="7d">{t("preset7d")}</SelectItem>
												<SelectItem value="30d">{t("preset30d")}</SelectItem>
												<SelectItem value="90d">{t("preset90d")}</SelectItem>
												<SelectItem value="custom">{t("custom")}</SelectItem>
											</SelectContent>
										</Select>
									</div>

									{datePreset === "custom" && (
										<>
											<div className="space-y-2">
												<Label htmlFor="custom-from">{t("fromDate")}</Label>
												<Input
													id="custom-from"
													type="datetime-local"
													value={customFrom}
													onChange={(e) => setCustomFrom(e.target.value)}
													aria-label={t("fromDate")}
												/>
											</div>
											<div className="space-y-2">
												<Label htmlFor="custom-to">{t("toDate")}</Label>
												<Input
													id="custom-to"
													type="datetime-local"
													value={customTo}
													onChange={(e) => setCustomTo(e.target.value)}
													aria-label={t("toDate")}
												/>
											</div>
										</>
									)}
								</div>

								{/* Created By */}
								<div className="space-y-2">
									<Label htmlFor="created-by">{t("createdBy")}</Label>
									<Select value={createdBy} onValueChange={setCreatedBy}>
										<SelectTrigger id="created-by" aria-label={t("createdBy")}>
											<SelectValue placeholder={t("allCreators")} />
										</SelectTrigger>
										<SelectContent>
											<SelectItem value="">{t("allCreators")}</SelectItem>
											{creators.map((c) => (
												<SelectItem key={c.id} value={c.id}>
													{c.email || c.id}
												</SelectItem>
											))}
										</SelectContent>
									</Select>
								</div>

								{hasActiveFilters && (
									<Button
										variant="outline"
										size="sm"
										onClick={clearFilters}
										aria-label={t("clearFilters")}
									>
										<X className="h-4 w-4 mr-1" aria-hidden="true" />
										{t("clearFilters")}
									</Button>
								)}
							</div>
						)}
					</div>

					{error && (
						<p className="text-red-500 text-sm" role="alert">
							{error}
						</p>
					)}

					{/* Content */}
					<Tabs value={view} className="w-full">
						<TabsContent value="list" className="space-y-4">
							{/* Page Size Selector */}
							<div className="flex items-center justify-between">
								<Label htmlFor="page-size" className="text-sm">
									{t("pageSize")}
								</Label>
								<Select value={String(pageSize)} onValueChange={(v) => setPageSize(Number(v))}>
									<SelectTrigger id="page-size" className="w-20" aria-label={t("pageSize")}>
										<SelectValue />
									</SelectTrigger>
									<SelectContent>
										{PAGE_SIZE_OPTIONS.map((size) => (
											<SelectItem key={size} value={String(size)}>
												{size}
											</SelectItem>
										))}
									</SelectContent>
								</Select>
							</div>

							<div className="rounded-md border">
								<table className="min-w-full text-sm" aria-label={t("title")}>
									<thead className="bg-muted">
										<tr>
											<th className="px-4 py-2 text-left" scope="col">
												{t("content")}
											</th>
											<th className="px-4 py-2 text-left" scope="col">
												{t("source")}
											</th>
											<th className="px-4 py-2 text-left" scope="col">
												{t("confidence")}
											</th>
											<th className="px-4 py-2 text-left" scope="col">
												{t("created")}
											</th>
											<th className="px-4 py-2 text-left" scope="col">
												{t("versions")}
											</th>
											<th className="px-4 py-2 text-left" scope="col">
												{t("actions")}
											</th>
										</tr>
									</thead>
									<tbody>{items.map(renderItemRow)}</tbody>
								</table>
							</div>

							{/* Pagination */}
							<div className="flex items-center justify-between">
								<p className="text-sm text-muted-foreground">
									{t("showing", { startEnd: `${startItem}-${endItem}`, total })}
								</p>
								<div className="flex items-center gap-2">
									<Button
										size="sm"
										variant="outline"
										disabled={page <= 1 || loading}
										onClick={() => setPage(page - 1)}
										aria-label={t("previous")}
									>
										{t("previous")}
									</Button>
									<span className="text-sm" aria-live="polite" aria-atomic="true">
										{page} / {totalPages || 1}
									</span>
									<Button
										size="sm"
										variant="outline"
										disabled={page >= totalPages || loading}
										onClick={() => setPage(page + 1)}
										aria-label={t("next")}
									>
										{t("next")}
									</Button>
								</div>
							</div>
						</TabsContent>

						<TabsContent value="timeline" className="space-y-4">
							{timeline && (
								<>
									{timeline.threads.length > 0 && (
										<div className="space-y-6">
											{timeline.threads.map((thread) => (
												<div key={thread.id} className="border-l-4 border-primary pl-4 space-y-4">
													<h3 className="font-semibold text-lg">
														{t("researchThreadGroup")}: {thread.title}
													</h3>
													<div className="space-y-3">{thread.memories.map(renderTimelineItem)}</div>
												</div>
											))}
										</div>
									)}

									{timeline.unthreaded && timeline.unthreaded.length > 0 && (
										<div className="space-y-4">
											<h3 className="font-semibold text-lg text-muted-foreground">
												{t("unthreaded")}
											</h3>
											<div className="space-y-3">{timeline.unthreaded.map(renderTimelineItem)}</div>
										</div>
									)}

									{timeline.threads.length === 0 &&
										(!timeline.unthreaded || timeline.unthreaded.length === 0) && (
											<p className="text-sm text-muted-foreground text-center py-8">
												{t("noResults")}
											</p>
										)}
								</>
							)}
						</TabsContent>
					</Tabs>
				</CardContent>
			</Card>

			{/* Detail Dialog */}
			{selected && (
				<Dialog open onOpenChange={(open) => !open && setSelected(null)}>
					<DialogContent
						className="max-w-3xl max-h-[80vh] overflow-y-auto"
						aria-describedby="detail-description"
					>
						<DialogHeader>
							<DialogTitle>{t("detailTitle")}</DialogTitle>
							<DialogDescription id="detail-description">
								{format(new Date(selected.created_at), "PPpp")} • {selected.source_type}
							</DialogDescription>
						</DialogHeader>
						<div className="space-y-4 text-sm">
							<div>
								<p className="whitespace-pre-wrap">{selected.content}</p>
							</div>

							{renderCitationSource(selected)}

							{selected.research_thread && (
								<div>
									<h4 className="font-semibold mb-2">{t("researchThread")}</h4>
									<Badge variant="secondary">{selected.research_thread.title}</Badge>
								</div>
							)}

							{selected.versions.length > 0 && (
								<div>
									<h4 className="font-semibold mb-2">{t("versions")}</h4>
									<div className="space-y-2">
										{selected.versions.map((v, idx) => (
											<div key={idx} className="border-l-2 border-muted pl-3 py-1">
												<p className="text-xs text-muted-foreground">
													{format(new Date(v.created_at), "MMM d, yyyy HH:mm")}
													{v.corrected_by && ` • ${v.corrected_by.email || v.corrected_by.id}`}
												</p>
												<p className="mt-1">
													<span className="line-through text-muted-foreground">
														{v.previous_content}
													</span>
													{" → "}
													<span className="font-medium">{v.corrected_content}</span>
												</p>
											</div>
										))}
									</div>
								</div>
							)}

							{selected.relations.length > 0 && (
								<div>
									<h4 className="font-semibold mb-2">{t("relations")}</h4>
									<div className="flex flex-wrap gap-2">
										{selected.relations.map((r, idx) => (
											<Badge key={`${r.relation_type}-${r.to_memory_id}-${idx}`} variant="outline">
												{r.relation_type} → #{r.to_memory_id}
												{r.weight != null && ` (${r.weight.toFixed(2)})`}
											</Badge>
										))}
									</div>
								</div>
							)}
						</div>
					</DialogContent>
				</Dialog>
			)}

			{/* Flag Dialog */}
			<Dialog open={flagDialogOpen} onOpenChange={setFlagDialogOpen}>
				<DialogContent aria-describedby="flag-description">
					<DialogHeader>
						<DialogTitle>{t("flagDialogTitle")}</DialogTitle>
						<DialogDescription id="flag-description">
							{flagTarget?.content_snippet}
						</DialogDescription>
					</DialogHeader>
					<div className="space-y-4">
						<div className="space-y-2">
							<Label htmlFor="flag-reason">{t("flagReason")}</Label>
							<Textarea
								id="flag-reason"
								placeholder={t("flagReasonPlaceholder")}
								value={flagReason}
								onChange={(e) => setFlagReason(e.target.value)}
								rows={4}
								aria-label={t("flagReason")}
								aria-required="true"
							/>
						</div>
					</div>
					<DialogFooter>
						<Button
							variant="outline"
							onClick={() => setFlagDialogOpen(false)}
							disabled={flagSubmitting}
						>
							{t("close")}
						</Button>
						<Button onClick={handleFlagSubmit} disabled={!flagReason.trim() || flagSubmitting}>
							{flagSubmitting ? t("submitting") : t("submit")}
						</Button>
					</DialogFooter>
				</DialogContent>
			</Dialog>
		</div>
	);
}
