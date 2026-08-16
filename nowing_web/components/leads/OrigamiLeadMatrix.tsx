"use client";

import { useAtom } from "jotai";
import {
	AlertTriangle,
	Check,
	ChevronDown,
	ChevronRight,
	Columns,
	Filter,
	Globe,
	Maximize2,
	Minimize2,
	Network,
	RefreshCw,
	Search,
	Sparkles,
} from "lucide-react";
import type React from "react";
import { useEffect, useMemo, useRef, useState } from "react";
import {
	activeDrawerLeadAtom,
	chatHighlightedRowIdsAtom,
	isMatrixFullscreenAtom,
	selectedLeadContextAtom,
	selectedLeadIdsAtom,
} from "@/atoms/leads/leads-canvas.atoms";
import type { Lead } from "@/contracts/types/leads.types";
import { cn } from "@/lib/utils";
import { PhoneCopyPill } from "./PhoneCopyPill";
import { SendExportDropdown } from "./send-export-dropdown";
import { ZaloOutreachButton } from "./zalo-outreach-button";

export interface OrigamiLeadMatrixProps {
	leads: Lead[];
	isLoading?: boolean;
	workspaceId?: string | number;
	sourceFilter: string;
	onSourceFilterChange: (source: string) => void;
	statusFilter: string;
	onStatusFilterChange: (status: string) => void;
	searchQuery: string;
	onSearchQueryChange: (query: string) => void;
	onRefresh: () => void;
	onOpenReverseIcp?: () => void;
	onOpenCompanyGraph?: (companyName: string) => void;
	className?: string;
}

const SOURCE_OPTIONS: Array<{ id: string; label: string; icon: string }> = [
	{ id: "all", label: "Tất cả nguồn tìm kiếm", icon: "🔍" },
	{ id: "batdongsan", label: "Batdongsan.com.vn", icon: "🏠" },
	{ id: "chotot", label: "Chợ Tốt (BĐS & Mua bán)", icon: "🛒" },
	{ id: "facebook", label: "Facebook Groups", icon: "👥" },
	{ id: "telegram", label: "Telegram Channels", icon: "✈️" },
	{ id: "topcv", label: "TopCV / ITviec", icon: "💼" },
	{ id: "tender", label: "Cổng Đấu Thầu (Mua Sắm Công)", icon: "🏛️" },
	{ id: "linkedin", label: "LinkedIn Search", icon: "🌐" },
];

const STATUS_OPTIONS: Array<{ id: string; label: string; dotColor: string }> = [
	{ id: "all", label: "Tất cả trạng thái", dotColor: "bg-muted-foreground" },
	{ id: "new", label: "Mới", dotColor: "bg-emerald-500" },
	{ id: "contacted", label: "Đã liên hệ", dotColor: "bg-blue-500" },
	{ id: "qualified", label: "Tiềm năng", dotColor: "bg-purple-500" },
];

export const OrigamiLeadMatrix: React.FC<OrigamiLeadMatrixProps> = ({
	leads = [],
	isLoading = false,
	workspaceId = "1",
	sourceFilter,
	onSourceFilterChange,
	statusFilter,
	onStatusFilterChange,
	searchQuery,
	onSearchQueryChange,
	onRefresh,
	onOpenReverseIcp,
	onOpenCompanyGraph,
	className,
}) => {
	const [selectedLeadIds, setSelectedLeadIds] = useAtom(selectedLeadIdsAtom);
	const [selectedLeadContext, setSelectedLeadContext] = useAtom(selectedLeadContextAtom);
	const [, setActiveDrawerLead] = useAtom(activeDrawerLeadAtom);
	const [highlightedRowIds] = useAtom(chatHighlightedRowIdsAtom);
	const [isFullscreen, setIsFullscreen] = useAtom(isMatrixFullscreenAtom);

	const [isSourceOpen, setIsSourceOpen] = useState(false);
	const [isStatusOpen, setIsStatusOpen] = useState(false);
	const sourceDropdownRef = useRef<HTMLDivElement>(null);
	const statusDropdownRef = useRef<HTMLDivElement>(null);

	// Close popovers on click outside
	useEffect(() => {
		const handleClickOutside = (event: MouseEvent) => {
			if (sourceDropdownRef.current && !sourceDropdownRef.current.contains(event.target as Node)) {
				setIsSourceOpen(false);
			}
			if (statusDropdownRef.current && !statusDropdownRef.current.contains(event.target as Node)) {
				setIsStatusOpen(false);
			}
		};
		document.addEventListener("mousedown", handleClickOutside);
		return () => document.removeEventListener("mousedown", handleClickOutside);
	}, []);

	const allIds = useMemo(() => leads.map((l) => l.id), [leads]);
	const isAllSelected = leads.length > 0 && leads.every((l) => selectedLeadIds.includes(l.id));

	const handleSelectAll = () => {
		if (isAllSelected) {
			setSelectedLeadIds((prev) => prev.filter((id) => !allIds.includes(id)));
		} else {
			setSelectedLeadIds((prev) => Array.from(new Set([...prev, ...allIds])));
		}
	};

	const handleToggleLead = (id: string, e?: React.SyntheticEvent) => {
		e?.stopPropagation();
		setSelectedLeadIds((prev) =>
			prev.includes(id) ? prev.filter((item) => item !== id) : [...prev, id]
		);
	};

	const handleRowClick = (lead: Lead) => {
		setSelectedLeadContext(lead);
		setActiveDrawerLead(lead);
	};

	const handleDownloadCsv = async () => {
		const headers = ["Company", "Phone", "Fit Score", "Source", "Location"];
		const rows = leads.map((l) => [
			`"${l.company_name}"`,
			`"${l.phone || ""}"`,
			`"${l.fit_score || 0}"`,
			`"${l.source}"`,
			`"${l.location || ""}"`,
		]);
		const csvContent = [headers.join(","), ...rows.map((r) => r.join(","))].join("\n");
		const blob = new Blob([csvContent], { type: "text/csv;charset=utf-8;" });
		const url = URL.createObjectURL(blob);
		const link = document.createElement("a");
		link.setAttribute("href", url);
		link.setAttribute("download", `leads_export_${Date.now()}.csv`);
		document.body.appendChild(link);
		link.click();
		document.body.removeChild(link);
	};

	const handleOpenLarkSync = () => {
		window.open("https://open.larksuite.com/", "_blank");
	};

	const handleOpenGoogleSheetsSync = () => {
		window.open("https://sheets.google.com/", "_blank");
	};

	const handleShareLink = async () => {
		if (typeof window !== "undefined") {
			await navigator.clipboard.writeText(window.location.href);
		}
	};

	const currentSourceOption = useMemo(() => {
		return SOURCE_OPTIONS.find((s) => s.id === sourceFilter) || SOURCE_OPTIONS[0];
	}, [sourceFilter]);

	const currentStatusOption = useMemo(() => {
		return STATUS_OPTIONS.find((s) => s.id === statusFilter) || STATUS_OPTIONS[0];
	}, [statusFilter]);

	return (
		<div
			data-testid="origami-lead-matrix"
			className={cn(
				"h-full flex flex-col bg-background text-foreground overflow-hidden font-sans",
				isFullscreen && "fixed inset-0 z-50",
				className
			)}
		>
			{/* Row 1: Slim Action Bar (Matching Origami.chat exactly) */}
			<div className="h-10 px-3 border-b border-border/80 bg-background flex items-center justify-between gap-2 shrink-0">
				<div className="flex items-center gap-2">
					{/* Custom Source Combobox */}
					<div className="relative" ref={sourceDropdownRef}>
						<button
							type="button"
							onClick={() => {
								setIsSourceOpen((prev) => !prev);
								setIsStatusOpen(false);
							}}
							className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg border border-border/80 bg-background hover:bg-muted/60 text-xs font-medium text-foreground transition-all cursor-pointer shadow-2xs focus:outline-none"
						>
							<span className="text-xs">{currentSourceOption.icon}</span>
							<span className="truncate max-w-[140px]">{currentSourceOption.label}</span>
							<ChevronDown
								className={cn(
									"w-3 h-3 text-muted-foreground transition-transform duration-150 ml-0.5",
									isSourceOpen && "rotate-180"
								)}
							/>
						</button>

						{isSourceOpen && (
							<div className="absolute left-0 top-full mt-1 w-60 rounded-xl border border-border bg-popover p-1 shadow-lg z-50 animate-in fade-in zoom-in-95 duration-100">
								<div className="px-2 py-1 text-[10px] font-bold uppercase tracking-wider text-muted-foreground">
									Nguồn dữ liệu
								</div>
								{SOURCE_OPTIONS.map((opt) => (
									<button
										key={opt.id}
										type="button"
										onClick={() => {
											onSourceFilterChange(opt.id);
											setIsSourceOpen(false);
										}}
										className={cn(
											"w-full flex items-center justify-between px-2.5 py-1.5 rounded-lg text-xs font-medium text-left transition-colors cursor-pointer",
											sourceFilter === opt.id
												? "bg-emerald-500/10 text-emerald-700 dark:text-emerald-300 font-semibold"
												: "text-muted-foreground hover:text-foreground hover:bg-muted/60"
										)}
									>
										<div className="flex items-center gap-2">
											<span>{opt.icon}</span>
											<span>{opt.label}</span>
										</div>
										{sourceFilter === opt.id && (
											<Check className="w-3.5 h-3.5 text-emerald-600 dark:text-emerald-400" />
										)}
									</button>
								))}
							</div>
						)}
					</div>
				</div>

				<div className="flex items-center gap-2">
					{onOpenReverseIcp && (
						<button
							type="button"
							onClick={onOpenReverseIcp}
							className="inline-flex items-center gap-1.5 px-2.5 py-1 text-xs font-medium rounded-lg border border-border/80 bg-background hover:bg-muted text-foreground transition-all cursor-pointer shadow-2xs"
						>
							<Search className="w-3.5 h-3.5 text-muted-foreground" />
							<span>Find similar leads</span>
						</button>
					)}

					<SendExportDropdown
						totalLeadsCount={leads.length}
						onDownloadCsv={handleDownloadCsv}
						onOpenLarkSync={handleOpenLarkSync}
						onOpenGoogleSheetsSync={handleOpenGoogleSheetsSync}
						onShareLink={handleShareLink}
					/>
				</div>
			</div>

			{/* Row 2: Campaigns & Filters Bar (Slim 32px) */}
			<div className="h-8 px-3 border-b border-border/60 bg-muted/20 flex items-center justify-between gap-3 text-xs shrink-0 select-none">
				<div className="flex items-center gap-3 overflow-x-auto no-scrollbar">
					<div className="flex items-center gap-1.5 shrink-0">
						<span className="text-[10px] font-bold tracking-wider text-muted-foreground uppercase">
							Campaigns:
						</span>
						<span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-amber-500/10 text-amber-700 dark:text-amber-400 border border-amber-500/20 text-[10px] font-medium shrink-0">
							<AlertTriangle className="w-2.5 h-2.5" />
							Not sending yet — connect a campaign
						</span>
					</div>

					<div className="flex items-center gap-1.5 shrink-0">
						<span className="text-[10px] font-bold tracking-wider text-muted-foreground uppercase">
							Filters:
						</span>
						<div className="relative" ref={statusDropdownRef}>
							<button
								type="button"
								onClick={() => {
									setIsStatusOpen((prev) => !prev);
									setIsSourceOpen(false);
								}}
								className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-md border border-border/80 bg-background hover:bg-muted/60 text-[10px] text-foreground focus:outline-none cursor-pointer shadow-2xs shrink-0"
							>
								<span className={cn("w-1.5 h-1.5 rounded-full", currentStatusOption.dotColor)} />
								<span>{currentStatusOption.label}</span>
								<ChevronDown
									className={cn(
										"w-2.5 h-2.5 text-muted-foreground transition-transform duration-150 ml-0.5",
										isStatusOpen && "rotate-180"
									)}
								/>
							</button>

							{isStatusOpen && (
								<div className="absolute left-0 top-full mt-1 w-40 rounded-xl border border-border bg-popover p-1 shadow-lg z-50 animate-in fade-in zoom-in-95 duration-100">
									{STATUS_OPTIONS.map((opt) => (
										<button
											key={opt.id}
											type="button"
											onClick={() => {
												onStatusFilterChange(opt.id);
												setIsStatusOpen(false);
											}}
											className={cn(
												"w-full flex items-center justify-between px-2 py-1 rounded-lg text-xs font-medium text-left transition-colors cursor-pointer",
												statusFilter === opt.id
													? "bg-muted text-foreground font-semibold"
													: "text-muted-foreground hover:text-foreground hover:bg-muted/60"
											)}
										>
											<div className="flex items-center gap-1.5">
												<span className={cn("w-1.5 h-1.5 rounded-full", opt.dotColor)} />
												<span className="text-xs">{opt.label}</span>
											</div>
											{statusFilter === opt.id && (
												<Check className="w-3 h-3 text-emerald-600 dark:text-emerald-400" />
											)}
										</button>
									))}
								</div>
							)}
						</div>
					</div>
				</div>

				<div className="flex items-center gap-2 shrink-0">
					<div className="relative">
						<Search className="w-3 h-3 text-muted-foreground absolute left-2 top-1/2 -translate-y-1/2 pointer-events-none" />
						<input
							type="text"
							value={searchQuery}
							onChange={(e) => onSearchQueryChange(e.target.value)}
							placeholder="Tìm trong bảng..."
							className="pl-6 pr-2 py-0.5 h-6 rounded-full border border-border/80 bg-background text-[10px] text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-emerald-500/50 w-36"
						/>
					</div>
				</div>
			</div>

			{/* Row 3: Metrics & View Customization Bar (Slim 28px) */}
			<div className="h-7 px-3 border-b border-border/60 bg-background flex items-center justify-between text-xs shrink-0 select-none">
				<div className="flex items-center gap-3">
					<span className="font-mono text-xs font-bold text-foreground">
						Leads {leads.length} <ChevronDown className="w-3 h-3 inline text-muted-foreground" />
					</span>
					<span className="text-[10px] text-muted-foreground font-mono">
						Projected price: <span className="font-bold text-foreground">1.5 credits</span> ($0.022)
						per lead ⌄
					</span>
				</div>

				<div className="flex items-center gap-1.5">
					<button
						type="button"
						className="inline-flex items-center gap-1 px-2 py-0.5 text-[10px] font-medium text-muted-foreground hover:text-foreground rounded border border-border/60 hover:bg-muted/40 transition-colors"
					>
						<span>8 cols</span>
						<ChevronDown className="w-2.5 h-2.5" />
					</button>
					<button
						type="button"
						title="Lọc nâng cao"
						className="p-1 text-muted-foreground hover:text-foreground rounded hover:bg-muted/40 transition-colors"
					>
						<Filter className="w-3 h-3" />
					</button>
					<button
						type="button"
						title="Tùy chỉnh cột"
						className="p-1 text-muted-foreground hover:text-foreground rounded hover:bg-muted/40 transition-colors"
					>
						<Columns className="w-3 h-3" />
					</button>
					<button
						type="button"
						onClick={onRefresh}
						disabled={isLoading}
						title="Làm mới"
						className="p-1 text-muted-foreground hover:text-foreground rounded hover:bg-muted/40 transition-colors"
					>
						<RefreshCw
							className={cn(
								"w-3 h-3",
								isLoading && "animate-spin text-emerald-600 dark:text-emerald-400"
							)}
						/>
					</button>
					<button
						type="button"
						onClick={() => setIsFullscreen((prev) => !prev)}
						title={isFullscreen ? "Thu nhỏ" : "Toàn màn hình"}
						className="p-1 text-muted-foreground hover:text-foreground rounded hover:bg-muted/40 transition-colors"
					>
						{isFullscreen ? <Minimize2 className="w-3 h-3" /> : <Maximize2 className="w-3 h-3" />}
					</button>
				</div>
			</div>

			{/* Main High-Density Data Matrix Grid */}
			<div className="flex-1 overflow-auto bg-background/50 relative scrollbar-thin">
				{leads.length === 0 ? (
					<div className="flex flex-col items-center justify-center h-full p-8 text-center select-none">
						<div className="w-10 h-10 rounded-2xl bg-emerald-500/10 border border-emerald-500/20 flex items-center justify-center mb-3">
							<Sparkles className="w-5 h-5 text-emerald-600 dark:text-emerald-400" />
						</div>
						<div className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full bg-emerald-500/10 text-emerald-700 dark:text-emerald-300 text-[11px] font-semibold mb-2 border border-emerald-500/20">
							🎯 Bảng Săn Lead Sống Đa Kênh
						</div>
						<h3 className="text-sm font-bold text-foreground">Sẵn sàng Săn Lead với AI Co-pilot</h3>
						<p className="text-xs text-muted-foreground mt-1 max-w-md">
							Hãy nhập lệnh tìm kiếm trong khung AI Chat bên trái. Hệ thống sẽ tự động điều phối cào
							dữ liệu sống từ 5+ nền tảng (BĐS, Chợ Tốt, TopCV, Đấu Thầu...) và đổ trực tiếp vào ma
							trận bảng này.
						</p>
					</div>
				) : (
					<table className="w-full text-left border-collapse text-xs">
						{/* Table Header Row (Compact 28px) */}
						<thead className="sticky top-0 z-10 bg-muted/60 backdrop-blur-md border-b border-border/80 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground/90 select-none">
							<tr className="h-7">
								<th className="w-8 px-2 text-center">
									<input
										type="checkbox"
										checked={isAllSelected}
										onChange={handleSelectAll}
										className="rounded border-border text-emerald-600 focus:ring-emerald-500 size-3.5 cursor-pointer align-middle"
									/>
								</th>
								<th className="w-8 px-1.5 font-mono text-center">#</th>
								<th className="px-2.5 w-28">FIT SCORE &gt;</th>
								<th className="px-3 min-w-[200px]">TÊN DOANH NGHIỆP</th>
								<th className="px-3 w-44">WEBSITE</th>
								<th className="px-3 w-32">NGÀNH</th>
								<th className="px-3 w-32">ĐIỆN THOẠI</th>
								<th className="w-24 px-2 text-right">HÀNH ĐỘNG</th>
							</tr>
						</thead>

						{/* Table Body Rows (High Density 34px - 36px) */}
						<tbody className="divide-y divide-border/40 font-sans">
							{leads.map((lead, idx) => {
								const isSelected = selectedLeadIds.includes(lead.id);
								const isContextActive = selectedLeadContext?.id === lead.id;
								const isHighlighted = highlightedRowIds.includes(lead.id);

								return (
									<tr
										key={lead.id}
										onClick={() => handleRowClick(lead)}
										className={cn(
											"h-9 group hover:bg-muted/40 transition-colors cursor-pointer text-[11.5px]",
											isSelected && "bg-emerald-500/5 hover:bg-emerald-500/10",
											isContextActive && "bg-muted/70",
											isHighlighted && "animate-pulse bg-emerald-500/10"
										)}
									>
										{/* Checkbox */}
										<td
											className="w-8 px-2 text-center"
											onClick={(e) => handleToggleLead(lead.id, e)}
											onKeyDown={(e) => {
												if (e.key === "Enter" || e.key === " ") {
													handleToggleLead(lead.id, e);
												}
											}}
										>
											<input
												type="checkbox"
												checked={isSelected}
												onChange={() => {}}
												className="rounded border-border text-emerald-600 focus:ring-emerald-500 size-3.5 cursor-pointer align-middle"
											/>
										</td>

										{/* Index # */}
										<td className="w-8 px-1.5 font-mono text-[11px] text-muted-foreground text-center">
											{idx + 1}
										</td>

										{/* Fit Score Badge [🟩 95 >] */}
										<td className="px-2.5">
											<div className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-md bg-emerald-500/10 text-emerald-700 dark:text-emerald-300 border border-emerald-500/20 font-mono text-[10px] font-bold">
												<span className="w-1.5 h-1.5 rounded-full bg-emerald-500" />
												<span>{lead.fit_score ?? 85}</span>
												<ChevronRight className="w-2.5 h-2.5 text-emerald-600/70" />
											</div>
										</td>

										{/* Company Name */}
										<td className="px-3 font-medium text-foreground">
											<div className="flex items-center gap-1.5 truncate max-w-[240px]">
												<span className="truncate">{lead.company_name}</span>
												{lead.source === "chat_scraper" && (
													<span className="px-1 py-0.2 rounded bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 text-[9px] font-bold uppercase shrink-0">
														✨ Mới
													</span>
												)}
											</div>
										</td>

										{/* Website */}
										<td className="px-3 text-muted-foreground">
											{lead.domain || lead.source_url ? (
												<a
													href={lead.source_url || `https://${lead.domain}`}
													target="_blank"
													rel="noopener noreferrer"
													onClick={(e) => e.stopPropagation()}
													className="inline-flex items-center gap-1 text-muted-foreground hover:text-foreground hover:underline transition-colors truncate max-w-[150px] text-[11px]"
												>
													<Globe className="w-3 h-3 text-muted-foreground/70 shrink-0" />
													<span className="truncate">{lead.domain || lead.source_url}</span>
												</a>
											) : (
												<span className="text-muted-foreground/40 text-[10px]">—</span>
											)}
										</td>

										{/* Industry */}
										<td className="px-3 text-muted-foreground text-[11px]">
											<span className="truncate block max-w-[120px]">
												{lead.industry || "Bất động sản"}
											</span>
										</td>

										{/* Phone Pill */}
										<td
											className="px-3"
											onClick={(e) => e.stopPropagation()}
											onKeyDown={(e) => e.stopPropagation()}
										>
											<PhoneCopyPill phone={lead.phone || ""} />
										</td>

										{/* Actions */}
										<td
											className="w-24 px-2 text-right"
											onClick={(e) => e.stopPropagation()}
											onKeyDown={(e) => e.stopPropagation()}
										>
											<div className="inline-flex items-center justify-end gap-1 opacity-80 group-hover:opacity-100 transition-opacity">
												<ZaloOutreachButton
													leadId={lead.id}
													phone={lead.phone}
													companyName={lead.company_name}
													workspaceId={workspaceId}
													size="sm"
												/>
												{onOpenCompanyGraph && (
													<button
														type="button"
														onClick={() => onOpenCompanyGraph(lead.company_name)}
														title="Xem sơ đồ liên kết doanh nghiệp"
														className="p-1 rounded text-muted-foreground hover:text-foreground hover:bg-muted transition-colors cursor-pointer"
													>
														<Network className="w-3 h-3" />
													</button>
												)}
											</div>
										</td>
									</tr>
								);
							})}
						</tbody>
					</table>
				)}
			</div>
		</div>
	);
};
