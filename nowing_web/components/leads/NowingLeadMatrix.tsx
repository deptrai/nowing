"use client";

import { useAtom, useAtomValue } from "jotai";
import {
	AlertTriangle,
	Check,
	ChevronDown,
	ChevronRight,
	Globe,
	Maximize2,
	Minimize2,
	Network,
	RefreshCw,
	Search,
	ShieldAlert,
	Sparkles,
} from "lucide-react";
import type React from "react";
import { useEffect, useMemo, useRef, useState } from "react";
import {
	activeDrawerLeadAtom,
	canvasHighlightTriggerAtom,
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

export interface NowingLeadMatrixProps {
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
	onOpenDnc?: () => void;
	onOpenCompanyGraph?: (companyName: string) => void;
	className?: string;
}

const SOURCE_OPTIONS: Array<{ id: string; label: string; icon: string }> = [
	{ id: "all", label: "Tất cả nguồn", icon: "🔍" },
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

export const NowingLeadMatrix: React.FC<NowingLeadMatrixProps> = ({
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
	onOpenDnc,
	onOpenCompanyGraph,
	className,
}) => {
	const [selectedLeadIds, setSelectedLeadIds] = useAtom(selectedLeadIdsAtom);
	const [selectedLeadContext, setSelectedLeadContext] = useAtom(selectedLeadContextAtom);
	const [, setActiveDrawerLead] = useAtom(activeDrawerLeadAtom);
	const [highlightedRowIds] = useAtom(chatHighlightedRowIdsAtom);
	const [isFullscreen, setIsFullscreen] = useAtom(isMatrixFullscreenAtom);
	const pingTrigger = useAtomValue(canvasHighlightTriggerAtom);

	const [isSourceOpen, setIsSourceOpen] = useState(false);
	const [isStatusOpen, setIsStatusOpen] = useState(false);
	const [isPingActive, setIsPingActive] = useState(false);
	const sourceDropdownRef = useRef<HTMLDivElement>(null);
	const statusDropdownRef = useRef<HTMLDivElement>(null);

	// Pulse highlight right panel when pinged from chat card
	useEffect(() => {
		if (!pingTrigger) return;
		setIsPingActive(true);
		const timer = setTimeout(() => {
			setIsPingActive(false);
		}, 1200);
		return () => clearTimeout(timer);
	}, [pingTrigger]);

	// Close dropdowns on outside click
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

	// Filter leads locally
	const filteredLeads = useMemo(() => {
		return leads.filter((lead) => {
			// Source filter
			if (sourceFilter !== "all") {
				if (sourceFilter === "batdongsan" && !lead.source.includes("batdongsan")) return false;
				if (sourceFilter === "chotot" && !lead.source.includes("chotot")) return false;
				if (sourceFilter === "facebook" && !lead.source.includes("facebook")) return false;
				if (sourceFilter === "telegram" && !lead.source.includes("telegram")) return false;
				if (
					sourceFilter === "topcv" &&
					!lead.source.includes("topcv") &&
					!lead.source.includes("itviec")
				)
					return false;
				if (sourceFilter === "tender" && !lead.source.includes("muasamcong")) return false;
				if (sourceFilter === "linkedin" && !lead.source.includes("linkedin")) return false;
			}
			// Status filter
			if (statusFilter !== "all" && lead.status !== statusFilter) {
				return false;
			}
			// Text search
			if (searchQuery.trim()) {
				const q = searchQuery.toLowerCase();
				const matchName = lead.company_name.toLowerCase().includes(q);
				const matchDomain = lead.domain?.toLowerCase().includes(q);
				const matchPhone = lead.phone?.toLowerCase().includes(q);
				const matchIndustry = lead.industry?.toLowerCase().includes(q);
				if (!matchName && !matchDomain && !matchPhone && !matchIndustry) return false;
			}
			return true;
		});
	}, [leads, sourceFilter, statusFilter, searchQuery]);

	const isAllSelected =
		filteredLeads.length > 0 && filteredLeads.every((lead) => selectedLeadIds.includes(lead.id));

	const handleSelectAll = () => {
		if (isAllSelected) {
			setSelectedLeadIds([]);
		} else {
			setSelectedLeadIds(filteredLeads.map((l) => l.id));
		}
	};

	const handleToggleLead = (leadId: string, e: React.MouseEvent | React.KeyboardEvent) => {
		e.stopPropagation();
		setSelectedLeadIds((prev) =>
			prev.includes(leadId) ? prev.filter((id) => id !== leadId) : [...prev, leadId]
		);
	};

	const handleRowClick = (lead: Lead) => {
		setSelectedLeadContext(lead);
		setActiveDrawerLead(lead);
	};

	const handleDownloadCsv = async () => {
		if (leads.length === 0) return;
		const headers = [
			"ID",
			"Tên Doanh Nghiệp",
			"Website",
			"Ngành",
			"Số Điện Thoại",
			"Fit Score",
			"Nguồn",
			"Địa Chỉ",
		];
		const rows = leads.map((l) => [
			`"${l.id}"`,
			`"${l.company_name.replace(/"/g, '""')}"`,
			`"${l.domain || ""}"`,
			`"${l.industry || ""}"`,
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
			data-testid="nowing-lead-matrix"
			className={cn(
				"h-full flex flex-col bg-background text-foreground overflow-hidden font-sans transition-all duration-200",
				isPingActive && "ring-2 ring-emerald-500/50 shadow-lg shadow-emerald-500/10",
				isFullscreen && "fixed inset-0 z-50",
				className
			)}
		>
			{/* Primary Action Bar (Row 1 - Height 38px / 40px) */}
			<div className="h-10 px-3 border-b border-border/70 bg-background flex items-center justify-between gap-2 shrink-0 select-none">
				{/* Left Filters & Search */}
				<div className="flex items-center gap-2 min-w-0 flex-1">
					{/* Source Dropdown */}
					<div className="relative" ref={sourceDropdownRef}>
						<button
							type="button"
							onClick={() => {
								setIsSourceOpen((prev) => !prev);
								setIsStatusOpen(false);
							}}
							className="inline-flex items-center gap-1.5 h-8 px-2.5 rounded-lg border border-border/80 bg-background hover:bg-muted/60 text-xs font-medium text-foreground transition-all cursor-pointer shadow-2xs focus:outline-none shrink-0"
						>
							<span className="text-sm">{currentSourceOption.icon}</span>
							<span className="truncate max-w-[110px] sm:max-w-[130px]">
								{currentSourceOption.label}
							</span>
							<ChevronDown
								className={cn(
									"size-3.5 text-muted-foreground transition-transform duration-150",
									isSourceOpen && "rotate-180"
								)}
							/>
						</button>

						{isSourceOpen && (
							<div className="absolute left-0 top-full mt-1 w-60 rounded-xl border border-border bg-popover p-1 shadow-lg z-50 animate-in fade-in zoom-in-95 duration-100">
								<div className="px-2.5 py-1 text-[10px] font-bold uppercase tracking-wider text-muted-foreground">
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
											<Check className="size-3.5 text-emerald-600 dark:text-emerald-400" />
										)}
									</button>
								))}
							</div>
						)}
					</div>

					{/* Status Filter */}
					<div className="relative" ref={statusDropdownRef}>
						<button
							type="button"
							onClick={() => {
								setIsStatusOpen((prev) => !prev);
								setIsSourceOpen(false);
							}}
							className="inline-flex items-center gap-1.5 h-8 px-2.5 rounded-lg border border-border/80 bg-background hover:bg-muted/60 text-xs text-foreground focus:outline-none cursor-pointer shadow-2xs shrink-0 font-medium"
						>
							<span className={cn("size-2 rounded-full", currentStatusOption.dotColor)} />
							<span className="truncate max-w-[100px]">{currentStatusOption.label}</span>
							<ChevronDown
								className={cn(
									"size-3.5 text-muted-foreground transition-transform duration-150",
									isStatusOpen && "rotate-180"
								)}
							/>
						</button>

						{isStatusOpen && (
							<div className="absolute left-0 top-full mt-1 w-44 rounded-xl border border-border bg-popover p-1 shadow-lg z-50 animate-in fade-in zoom-in-95 duration-100">
								{STATUS_OPTIONS.map((opt) => (
									<button
										key={opt.id}
										type="button"
										onClick={() => {
											onStatusFilterChange(opt.id);
											setIsStatusOpen(false);
										}}
										className={cn(
											"w-full flex items-center justify-between px-2.5 py-1.5 rounded-lg text-xs font-medium text-left transition-colors cursor-pointer",
											statusFilter === opt.id
												? "bg-muted text-foreground font-semibold"
												: "text-muted-foreground hover:text-foreground hover:bg-muted/60"
										)}
									>
										<div className="flex items-center gap-2">
											<span className={cn("size-2 rounded-full", opt.dotColor)} />
											<span className="text-xs">{opt.label}</span>
										</div>
										{statusFilter === opt.id && (
											<Check className="size-3.5 text-emerald-600 dark:text-emerald-400" />
										)}
									</button>
								))}
							</div>
						)}
					</div>

					{/* Quick Search */}
					<div className="relative min-w-[90px] max-w-[150px]">
						<Search className="size-3.5 text-muted-foreground absolute left-2.5 top-1/2 -translate-y-1/2 pointer-events-none" />
						<input
							type="text"
							value={searchQuery}
							onChange={(e) => onSearchQueryChange(e.target.value)}
							placeholder="Tìm kiếm..."
							className="w-full pl-8 pr-2.5 h-8 rounded-lg border border-border/80 bg-background text-xs text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-emerald-500/50"
						/>
					</div>
				</div>

				{/* Right Actions */}
				<div className="flex items-center gap-1.5 shrink-0">
					{onOpenReverseIcp && (
						<button
							type="button"
							onClick={onOpenReverseIcp}
							className="inline-flex items-center gap-1.5 h-8 px-2.5 text-xs font-medium rounded-lg border border-border/80 bg-background hover:bg-muted text-foreground transition-all cursor-pointer shadow-2xs"
							title="Tìm leads tương tự qua 1-Click Reverse-ICP"
						>
							<Search className="size-3.5 text-muted-foreground" />
							<span className="hidden lg:inline">Similar leads</span>
						</button>
					)}

					{onOpenDnc && (
						<button
							type="button"
							onClick={onOpenDnc}
							className="inline-flex items-center gap-1.5 h-8 px-2.5 text-xs font-medium rounded-lg border border-border/80 bg-background hover:bg-muted text-foreground transition-all cursor-pointer shadow-2xs"
							title="Quản lý danh sách Do-Not-Call (DNC) tuân thủ Nghị định 13 PDPD"
						>
							<ShieldAlert className="size-3.5 text-amber-600 dark:text-amber-400" />
							<span className="hidden lg:inline">DNC</span>
						</button>
					)}

					<SendExportDropdown
						totalLeadsCount={leads.length}
						onDownloadCsv={handleDownloadCsv}
						onOpenLarkSync={handleOpenLarkSync}
						onOpenGoogleSheetsSync={handleOpenGoogleSheetsSync}
						onShareLink={handleShareLink}
					/>

					<button
						type="button"
						onClick={onRefresh}
						disabled={isLoading}
						title="Làm mới bảng"
						className="size-8 rounded-lg border border-border/80 bg-background hover:bg-muted flex items-center justify-center text-muted-foreground hover:text-foreground transition-colors cursor-pointer"
					>
						<RefreshCw
							className={cn(
								"size-3.5",
								isLoading && "animate-spin text-emerald-600 dark:text-emerald-400"
							)}
						/>
					</button>

					<button
						type="button"
						onClick={() => setIsFullscreen((prev) => !prev)}
						title={isFullscreen ? "Thu nhỏ" : "Toàn màn hình"}
						className="size-8 rounded-lg border border-border/80 bg-background hover:bg-muted flex items-center justify-center text-muted-foreground hover:text-foreground transition-colors cursor-pointer"
					>
						{isFullscreen ? <Minimize2 className="size-3.5" /> : <Maximize2 className="size-3.5" />}
					</button>
				</div>
			</div>

			{/* Context & Stats Bar (Row 2 - Height 30px) */}
			<div className="h-7.5 px-3 border-b border-border/60 bg-muted/20 flex items-center justify-between text-xs shrink-0 select-none">
				<div className="flex items-center gap-3 overflow-hidden">
					<span className="font-mono font-bold text-foreground shrink-0 text-xs">
						Leads {filteredLeads.length}
					</span>
					<span className="text-muted-foreground/40 shrink-0">•</span>
					<span className="text-muted-foreground font-mono text-[11.5px] truncate">
						Giá: <span className="font-bold text-foreground">1.5 credits</span> ($0.022)/lead
					</span>
				</div>

				<div className="flex items-center gap-2.5 shrink-0">
					<span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full bg-amber-500/10 text-amber-700 dark:text-amber-400 border border-amber-500/20 text-[10px] font-medium">
						<AlertTriangle className="size-3" />
						Not sending yet
					</span>
					<span className="text-muted-foreground font-medium text-[11px] hidden sm:inline">
						8 cols
					</span>
				</div>
			</div>

			{/* Main High-Density Fluid Data Matrix Grid */}
			<div className="flex-1 overflow-auto bg-background/50 relative scrollbar-thin">
				{filteredLeads.length === 0 ? (
					<div className="flex flex-col items-center justify-center h-full p-8 text-center select-none">
						<div className="size-10 rounded-2xl bg-emerald-500/10 border border-emerald-500/20 flex items-center justify-center mb-3">
							<Sparkles className="size-5 text-emerald-600 dark:text-emerald-400" />
						</div>
						<div className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full bg-emerald-500/10 text-emerald-700 dark:text-emerald-300 text-xs font-semibold mb-2 border border-emerald-500/20">
							🎯 Bảng Săn Lead Tự Động
						</div>
						<h3 className="text-sm font-bold text-foreground">
							Chưa có dữ liệu phù hợp với bộ lọc
						</h3>
						<p className="text-xs text-muted-foreground mt-1 max-w-sm">
							Hãy nhập yêu cầu trong khung Chat hoặc thay đổi bộ lọc nguồn dữ liệu bên trên.
						</p>
					</div>
				) : (
					<table className="w-full text-left border-collapse text-xs sm:text-[13px] table-auto">
						{/* Table Header Row */}
						<thead className="sticky top-0 z-10 bg-muted/80 backdrop-blur-md border-b border-border/80 text-[11px] font-semibold uppercase tracking-wider text-muted-foreground/90 select-none">
							<tr className="h-8">
								<th className="w-8 px-2 text-center shrink-0">
									<input
										type="checkbox"
										checked={isAllSelected}
										onChange={handleSelectAll}
										className="rounded border-border text-emerald-600 focus:ring-emerald-500 size-3.5 cursor-pointer align-middle"
									/>
								</th>
								<th className="w-8 px-1.5 font-mono text-center shrink-0">#</th>
								<th className="w-24 px-2.5 shrink-0">FIT SCORE &gt;</th>
								<th className="px-3 min-w-[150px] max-w-[280px]">TÊN DOANH NGHIỆP</th>
								<th className="px-3 min-w-[100px] max-w-[180px]">WEBSITE</th>
								<th className="px-3 min-w-[90px] max-w-[140px]">NGÀNH</th>
								<th className="px-3 min-w-[110px] max-w-[150px]">ĐIỆN THOẠI</th>
								<th className="w-32 px-3 text-right shrink-0">HÀNH ĐỘNG</th>
							</tr>
						</thead>

						{/* Table Body Rows (Height 40px, Text 13px) */}
						<tbody className="divide-y divide-border/40 font-sans">
							{filteredLeads.map((lead, idx) => {
								const isSelected = selectedLeadIds.includes(lead.id);
								const isContextActive = selectedLeadContext?.id === lead.id;
								const isHighlighted = highlightedRowIds.includes(lead.id);

								return (
									<tr
										key={lead.id}
										onClick={() => handleRowClick(lead)}
										className={cn(
											"h-10 group hover:bg-muted/40 transition-colors cursor-pointer text-xs sm:text-[12.5px]",
											isSelected && "bg-emerald-500/5 hover:bg-emerald-500/10",
											isContextActive && "bg-muted/70",
											isHighlighted && "animate-pulse bg-emerald-500/10"
										)}
									>
										{/* Checkbox */}
										<td
											className="w-8 px-2 text-center shrink-0"
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
										<td className="w-8 px-1.5 font-mono text-xs text-muted-foreground text-center shrink-0">
											{idx + 1}
										</td>

										{/* Fit Score Badge [🟩 95 >] */}
										<td className="w-24 px-2.5 shrink-0">
											<div className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-md bg-emerald-500/10 text-emerald-700 dark:text-emerald-300 border border-emerald-500/20 font-mono text-[10.5px] font-bold">
												<span className="size-1.5 rounded-full bg-emerald-500" />
												<span>{lead.fit_score ?? 85}</span>
												<ChevronRight className="size-2.5 text-emerald-600/70" />
											</div>
										</td>

										{/* Company Name */}
										<td className="px-3 font-medium text-foreground min-w-[150px] max-w-[280px]">
											<div className="flex items-center gap-1.5 truncate">
												<span className="truncate">{lead.company_name}</span>
												{lead.source === "chat_scraper" && (
													<span className="px-1.5 py-0.2 rounded bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 text-[9px] font-bold uppercase shrink-0">
														Mới
													</span>
												)}
											</div>
										</td>

										{/* Website */}
										<td className="px-3 text-muted-foreground min-w-[100px] max-w-[180px]">
											{lead.domain || lead.source_url ? (
												<a
													href={lead.source_url || `https://${lead.domain}`}
													target="_blank"
													rel="noopener noreferrer"
													onClick={(e) => e.stopPropagation()}
													className="inline-flex items-center gap-1.5 text-muted-foreground hover:text-foreground hover:underline transition-colors truncate max-w-full text-xs"
												>
													<Globe className="size-3.5 text-muted-foreground/70 shrink-0" />
													<span className="truncate">{lead.domain || lead.source_url}</span>
												</a>
											) : (
												<span className="text-muted-foreground/40 text-xs">—</span>
											)}
										</td>

										{/* Industry */}
										<td className="px-3 text-muted-foreground text-xs min-w-[90px] max-w-[140px]">
											<span className="truncate block">{lead.industry || "Bất động sản"}</span>
										</td>

										{/* Phone Pill */}
										<td
											className="px-3 min-w-[110px] max-w-[150px]"
											onClick={(e) => e.stopPropagation()}
											onKeyDown={(e) => e.stopPropagation()}
										>
											<PhoneCopyPill phone={lead.phone} />
										</td>

										{/* Actions */}
										<td
											className="w-32 px-3 text-right shrink-0"
											onClick={(e) => e.stopPropagation()}
											onKeyDown={(e) => e.stopPropagation()}
										>
											<div className="inline-flex items-center justify-end gap-1.5">
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
														className="size-7 p-0 rounded-lg flex items-center justify-center text-muted-foreground hover:text-foreground hover:bg-muted transition-colors cursor-pointer border border-transparent hover:border-border/60"
													>
														<Network className="size-3.5" />
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
