"use client";

import { useAtom } from "jotai";
import {
	AlertTriangle,
	ChevronDown,
	ChevronRight,
	Globe,
	Lock,
	Maximize2,
	Minimize2,
	Network,
	Plus,
	RefreshCw,
	Search,
	SlidersHorizontal,
	Sparkles,
	Table as TableIcon,
} from "lucide-react";
import type React from "react";
import { useMemo, useState } from "react";
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

export const OrigamiLeadMatrix: React.FC<OrigamiLeadMatrixProps> = ({
	leads,
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
	const [activeTabName, setActiveTabName] = useState("Tất cả khách hàng tiềm năng");

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
		await navigator.clipboard.writeText(window.location.href);
	};

	const displayTitle = useMemo(() => {
		if (searchQuery) return `Kết quả: ${searchQuery}`;
		if (sourceFilter !== "all") {
			const sourceLabels: Record<string, string> = {
				batdongsan: "Leads Bất Động Sản (Batdongsan)",
				chotot: "Leads Mua Bán / BDS (Chợ Tốt)",
				topcv: "Tín Hiệu Tuyển Dụng (TopCV)",
				muasamcong: "Gói Thầu Mua Sắm Công",
				facebook: "Cộng Đồng Mạng Xã Hội",
				telegram: "Nhóm Đầu Tư & Tín Hiệu",
			};
			return sourceLabels[sourceFilter] || `Leads từ nguồn ${sourceFilter}`;
		}
		return activeTabName || "Tất cả khách hàng tiềm năng";
	}, [searchQuery, sourceFilter, activeTabName]);

	return (
		<div
			data-testid="origami-lead-matrix"
			className={cn(
				"h-full flex flex-col bg-background text-foreground overflow-hidden font-sans",
				isFullscreen && "fixed inset-0 z-50",
				className
			)}
		>
			{/* Top Spreadsheet Tab Bar with Multi-Table Tabs & Credits */}
			<div className="h-10 border-b border-border/80 bg-muted/40 flex items-center justify-between px-3 shrink-0">
				<div className="flex items-center gap-1.5 overflow-x-auto no-scrollbar flex-1">
					<button
						type="button"
						onClick={() => {
							setActiveTabName("Tất cả khách hàng tiềm năng");
							onSourceFilterChange("all");
						}}
						className="flex items-center gap-1.5 px-3 py-1 bg-background border-t-2 border-t-emerald-500 border-x border-border/80 rounded-t-md text-xs font-semibold text-foreground shadow-xs shrink-0 cursor-pointer"
					>
						<TableIcon className="w-3.5 h-3.5 text-emerald-600 dark:text-emerald-400" />
						<span className="truncate max-w-[180px]">{displayTitle}</span>
						<ChevronDown className="w-3 h-3 text-muted-foreground ml-1" />
					</button>
					<button
						type="button"
						onClick={() => {
							setActiveTabName("Bất động sản & Chủ nhà");
							onSourceFilterChange("batdongsan");
						}}
						className="flex items-center gap-1 px-3 py-1 text-xs text-muted-foreground hover:text-foreground hover:bg-background/60 rounded-t-md transition-colors shrink-0 cursor-pointer border border-transparent hover:border-border/50"
					>
						<TableIcon className="w-3.5 h-3.5 opacity-60" />
						<span className="truncate max-w-[150px]">Bất động sản</span>
					</button>
					<button
						type="button"
						onClick={() => {
							setActiveTabName("Tín hiệu tuyển dụng");
							onSourceFilterChange("topcv");
						}}
						className="flex items-center gap-1 px-3 py-1 text-xs text-muted-foreground hover:text-foreground hover:bg-background/60 rounded-t-md transition-colors shrink-0 cursor-pointer border border-transparent hover:border-border/50"
					>
						<TableIcon className="w-3.5 h-3.5 opacity-60" />
						<span className="truncate max-w-[150px]">Tuyển dụng & Doanh nghiệp</span>
					</button>
					<button
						type="button"
						title="Thêm bảng mới"
						className="p-1 text-muted-foreground hover:text-foreground hover:bg-background/80 rounded transition-colors cursor-pointer"
					>
						<Plus className="w-3.5 h-3.5" />
					</button>
				</div>

				<div className="flex items-center gap-2 shrink-0">
					<div className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full bg-emerald-500/10 text-emerald-700 dark:text-emerald-300 text-[11px] font-medium border border-emerald-500/20">
						<span className="text-[10px]">💎</span>
						<span className="font-mono font-bold">1,420</span> Credits
					</div>
				</div>
			</div>

			{/* Main Editorial Header: Title + Primary Actions */}
			<div className="px-5 py-4 border-b border-border/80 bg-background flex flex-wrap items-center justify-between gap-4">
				<div className="flex items-center gap-3">
					<h1 className="text-xl sm:text-2xl font-bold tracking-tight text-foreground font-sans">
						{displayTitle}
					</h1>
					<div className="relative">
						<select
							value={sourceFilter}
							onChange={(e) => onSourceFilterChange(e.target.value)}
							className="appearance-none pl-2.5 pr-7 py-1 rounded-lg border border-border bg-muted/30 text-xs font-medium text-muted-foreground hover:text-foreground hover:bg-muted/60 transition-colors cursor-pointer focus:outline-none"
						>
							<option value="all">🔍 Tất cả nguồn tìm kiếm</option>
							<option value="batdongsan">🏠 Batdongsan.com.vn</option>
							<option value="facebook">👥 Facebook Groups</option>
							<option value="telegram">✈️ Telegram Channels</option>
							<option value="topcv">💼 TopCV / ITviec</option>
							<option value="tender">🏛️ Cổng Đấu Thầu</option>
							<option value="linkedin">💼 LinkedIn Search</option>
						</select>
						<ChevronDown className="w-3 h-3 text-muted-foreground absolute right-2 top-1/2 -translate-y-1/2 pointer-events-none" />
					</div>
				</div>

				<div className="flex items-center gap-2.5">
					{onOpenReverseIcp && (
						<button
							type="button"
							onClick={onOpenReverseIcp}
							className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-xl border border-border bg-background hover:bg-muted text-foreground transition-all cursor-pointer shadow-xs"
						>
							<Search className="w-3.5 h-3.5 text-muted-foreground" />
							Find similar leads
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

			{/* Campaigns & Filter Chips Bar */}
			<div className="px-5 py-2.5 border-b border-border/60 bg-muted/10 flex flex-wrap items-center justify-between gap-3 text-xs">
				<div className="flex flex-wrap items-center gap-4">
					<div className="flex items-center gap-2">
						<span className="text-[11px] font-bold tracking-wider text-muted-foreground uppercase">
							Campaigns:
						</span>
						<span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full bg-amber-500/10 text-amber-700 dark:text-amber-400 border border-amber-500/20 text-[11px] font-medium">
							<AlertTriangle className="w-3 h-3" />
							Not sending yet — connect a campaign
						</span>
					</div>

					<div className="flex items-center gap-2 flex-wrap">
						<div className="relative">
							<Search className="w-3 h-3 text-muted-foreground absolute left-2.5 top-1/2 -translate-y-1/2 pointer-events-none" />
							<input
								type="text"
								value={searchQuery}
								onChange={(e) => onSearchQueryChange(e.target.value)}
								placeholder="Tìm trong bảng..."
								className="pl-7 pr-2.5 py-0.5 rounded-full border border-border bg-background text-[11px] text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-emerald-500/50"
							/>
						</div>
						<select
							value={statusFilter}
							onChange={(e) => onStatusFilterChange(e.target.value)}
							className="px-2.5 py-0.5 rounded-full border border-border bg-background text-[11px] text-foreground focus:outline-none cursor-pointer"
						>
							<option value="all">Tất cả trạng thái</option>
							<option value="new">Mới</option>
							<option value="contacted">Đã liên hệ</option>
							<option value="qualified">Tiềm năng</option>
						</select>
					</div>
				</div>

				<div className="flex items-center gap-2">
					<button
						type="button"
						onClick={onRefresh}
						disabled={isLoading}
						title="Làm mới dữ liệu"
						className="p-1 text-muted-foreground hover:text-foreground rounded transition-colors cursor-pointer"
					>
						<RefreshCw
							className={cn(
								"w-3.5 h-3.5",
								isLoading && "animate-spin text-emerald-600 dark:text-emerald-400"
							)}
						/>
					</button>
					<button
						type="button"
						onClick={() => setIsFullscreen((prev) => !prev)}
						title={isFullscreen ? "Thu nhỏ" : "Toàn màn hình"}
						className="p-1 text-muted-foreground hover:text-foreground rounded transition-colors cursor-pointer"
					>
						{isFullscreen ? (
							<Minimize2 className="w-3.5 h-3.5" />
						) : (
							<Maximize2 className="w-3.5 h-3.5" />
						)}
					</button>
				</div>
			</div>

			{/* Sub-header Bar: Stats & Controls */}
			<div className="px-5 py-2 border-b border-border/60 bg-muted/20 flex items-center justify-between gap-4 text-xs text-muted-foreground">
				<div className="flex items-center gap-4">
					<div className="flex items-center gap-1 font-medium text-foreground cursor-pointer">
						<span>Leads</span>
						<span className="font-bold text-emerald-600 dark:text-emerald-400">{leads.length}</span>
						<ChevronDown className="w-3 h-3 opacity-70" />
					</div>
					<div className="h-3.5 w-[1px] bg-border" />
					<div className="flex items-center gap-1 text-[11px] cursor-pointer">
						<span>Projected price:</span>
						<span className="font-bold text-foreground font-mono">1.5 credits</span>
						<span className="text-[10px] text-muted-foreground">($0.022) per lead</span>
						<ChevronDown className="w-3 h-3 opacity-70" />
					</div>
				</div>

				<div className="flex items-center gap-2">
					<button
						type="button"
						className="inline-flex items-center gap-1 px-2 py-1 rounded-md border border-border/80 bg-background text-[11px] font-medium text-foreground hover:bg-muted transition-colors cursor-pointer"
					>
						<span>8 cols</span>
						<ChevronDown className="w-3 h-3 opacity-70" />
					</button>
					<button
						type="button"
						className="p-1 rounded-md border border-border/80 bg-background text-muted-foreground hover:text-foreground hover:bg-muted transition-colors cursor-pointer"
						title="Sắp xếp"
					>
						<SlidersHorizontal className="w-3 h-3" />
					</button>
				</div>
			</div>

			{/* Spreadsheet Table Container */}
			<div className="flex-1 overflow-auto scrollbar-thin">
				{leads.length === 0 ? (
					<div className="h-full min-h-[420px] flex flex-col items-center justify-center p-8 text-center soc-caro-grid">
						<div className="w-14 h-14 rounded-2xl bg-card border border-border flex items-center justify-center text-muted-foreground mb-4 shadow-md ring-1 ring-emerald-500/20">
							<Sparkles className="w-7 h-7 text-emerald-600 dark:text-emerald-400 animate-pulse" />
						</div>
						<span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-emerald-500/10 text-emerald-700 dark:text-emerald-300 text-xs font-semibold mb-2 border border-emerald-500/20">
							🎯 Bảng Săn Lead Sống Đa Kênh
						</span>
						<h3 className="text-lg font-bold text-foreground mb-2">
							Sẵn sàng Săn Lead với AI Co-pilot
						</h3>
						<p className="text-xs text-muted-foreground max-w-md mb-6 leading-relaxed">
							Hãy nhập lệnh tìm kiếm trong khung AI Chat bên trái. Hệ thống sẽ tự động điều phối cào
							dữ liệu sống từ 5+ nền tảng (BĐS, Chợ Tốt, TopCV, Đấu Thầu...) và đổ trực tiếp vào ma
							trận bảng này.
						</p>

						<div className="flex flex-wrap items-center justify-center gap-2 max-w-lg mb-6">
							<button
								type="button"
								onClick={() => {
									onSourceFilterChange("batdongsan");
								}}
								className="px-3 py-1.5 rounded-lg border border-border/80 bg-card hover:bg-muted text-xs font-medium text-foreground transition-colors cursor-pointer flex items-center gap-1.5"
							>
								<span>🏢</span>
								<span>Xem Leads Bất Động Sản</span>
							</button>
							<button
								type="button"
								onClick={() => {
									onSourceFilterChange("topcv");
								}}
								className="px-3 py-1.5 rounded-lg border border-border/80 bg-card hover:bg-muted text-xs font-medium text-foreground transition-colors cursor-pointer flex items-center gap-1.5"
							>
								<span>💼</span>
								<span>Xem Tín Hiệu Tuyển Dụng</span>
							</button>
							{onOpenReverseIcp && (
								<button
									type="button"
									onClick={onOpenReverseIcp}
									className="px-3.5 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-semibold transition-colors cursor-pointer flex items-center gap-1.5 shadow-sm"
								>
									<Sparkles className="w-3.5 h-3.5" />
									<span>Phân tích ICP từ Website</span>
								</button>
							)}
						</div>
					</div>
				) : (
					<table className="w-full text-left text-xs text-foreground border-collapse">
						<thead className="sticky top-0 z-10 bg-muted/90 text-[11px] text-muted-foreground border-b border-border font-medium backdrop-blur-xs">
							<tr>
								<th scope="col" className="w-10 px-3 py-2.5 text-center">
									<input
										type="checkbox"
										checked={isAllSelected}
										onChange={handleSelectAll}
										className="rounded border-border bg-background text-emerald-600 focus:ring-emerald-500/30 cursor-pointer"
									/>
								</th>
								<th scope="col" className="w-10 px-2 py-2.5 font-medium text-center">
									#
								</th>
								<th scope="col" className="w-24 px-3 py-2.5 font-medium">
									FIT SCORE &gt;
								</th>
								<th scope="col" className="w-[20%] px-3 py-2.5 font-medium">
									T TÊN DOANH NGHIỆP
								</th>
								<th scope="col" className="w-[14%] px-3 py-2.5 font-medium">
									🌐 WEBSITE
								</th>
								<th scope="col" className="w-[13%] px-3 py-2.5 font-medium">
									T NGÀNH
								</th>
								<th scope="col" className="w-[20%] px-3 py-2.5 font-medium">
									T MÔ TẢ HOẠT ĐỘNG
								</th>
								<th scope="col" className="w-[15%] px-3 py-2.5 font-medium">
									📍 ĐỊA ĐIỂM
								</th>
								<th scope="col" className="w-[18%] px-3 py-2.5 font-medium text-center">
									SĐT & TIẾP CẬN
								</th>
							</tr>
						</thead>
						<tbody className="divide-y divide-border/60 bg-background font-sans">
							{leads.map((lead, idx) => {
								const isSelected = selectedLeadIds.includes(lead.id);
								const isContextActive = selectedLeadContext?.id === lead.id;
								const isHighlighted = highlightedRowIds.includes(lead.id);
								const isNewLead = lead.source === "chat_scraper" || isHighlighted;
								const fitScore = lead.fit_score ?? 85 + (idx % 15);

								return (
									<tr
										key={lead.id}
										tabIndex={0}
										data-testid={`lead-row-${lead.id}`}
										onClick={() => handleRowClick(lead)}
										onKeyDown={(e) => {
											if (e.key === "Enter" || e.key === " ") {
												e.preventDefault();
												handleRowClick(lead);
											}
										}}
										className={cn(
											"transition-all duration-300 cursor-pointer group hover:bg-muted/40 focus:outline-none focus:bg-muted/60",
											isNewLead && "animate-lead-pulse bg-emerald-500/10",
											isSelected && "bg-emerald-500/10",
											isContextActive && "bg-emerald-500/15 ring-1 ring-inset ring-emerald-500/40",
											isHighlighted && "bg-blue-500/15 ring-1 ring-inset ring-blue-500/40"
										)}
									>
										{/* Checkbox */}
										<td className="w-10 px-3 py-2.5 text-center">
											<input
												type="checkbox"
												data-lead-checkbox="true"
												checked={isSelected}
												onClick={(e) => e.stopPropagation()}
												onChange={(e) => handleToggleLead(lead.id, e)}
												className="rounded border-border bg-background text-emerald-600 focus:ring-emerald-500/30 cursor-pointer"
											/>
										</td>

										{/* Row Index (#) */}
										<td className="w-10 px-2 py-2.5 text-center font-mono text-[11px] text-muted-foreground">
											{idx + 1}
										</td>

										{/* Fit Score Pill (Origami style: 🟩 100 >) */}
										<td className="w-24 px-3 py-2.5">
											<div className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-md bg-emerald-500/10 border border-emerald-500/30 text-emerald-700 dark:text-emerald-400 font-mono text-[11px] font-bold">
												<span className="w-2 h-2 rounded-[2px] bg-emerald-500" />
												<span>{fitScore}</span>
												<ChevronRight className="w-3 h-3 opacity-60" />
											</div>
										</td>

										{/* Company Name */}
										<td className="px-3 py-2.5 font-medium text-foreground">
											<div className="flex items-center justify-between gap-1.5 overflow-hidden">
												<div className="flex items-center gap-1.5 overflow-hidden">
													<span className="truncate font-semibold">{lead.company_name}</span>
													{isNewLead && (
														<span className="inline-flex items-center gap-0.5 px-1.5 py-0.2 rounded-full bg-emerald-500/20 text-emerald-700 dark:text-emerald-300 text-[10px] font-bold shrink-0 animate-pulse">
															✨ Mới
														</span>
													)}
												</div>
												{onOpenCompanyGraph && (
													<button
														type="button"
														onClick={(e) => {
															e.stopPropagation();
															onOpenCompanyGraph(lead.company_name);
														}}
														title="Company Graph"
														className="p-0.5 rounded hover:bg-muted text-muted-foreground hover:text-blue-500 opacity-0 group-hover:opacity-100 transition-opacity shrink-0"
													>
														<Network className="w-3 h-3" />
													</button>
												)}
											</div>
										</td>

										{/* Website / Domain with Favicon */}
										<td className="px-3 py-2.5">
											<div className="flex items-center gap-1.5 text-muted-foreground hover:text-foreground overflow-hidden">
												<Globe className="w-3.5 h-3.5 text-emerald-600 shrink-0" />
												<span className="truncate font-mono text-[11px]">
													{lead.domain ||
														(lead.source_url
															? lead.source_url.replace(/^https?:\/\//, "").split("/")[0]
															: `${lead.company_name.toLowerCase().replace(/[^a-z0-9]/g, "")}.com`)}
												</span>
											</div>
										</td>

										{/* Industry */}
										<td className="px-3 py-2.5 text-muted-foreground">
											<span className="truncate block text-[11px]">
												{lead.industry || "wholesale / B2B"}
											</span>
										</td>

										{/* Description Activity */}
										<td className="px-3 py-2.5 text-muted-foreground">
											<p className="truncate text-[11px]">
												{lead.content_snippet || "Cung cấp giải pháp & phân phối toàn quốc..."}
											</p>
										</td>

										{/* Location */}
										<td className="px-3 py-2.5 text-muted-foreground">
											<span className="truncate block text-[11px]">
												{lead.location || "TP. Hồ Chí Minh, Việt Nam"}
											</span>
										</td>

										{/* SĐT & Zalo Outreach Button */}
										<td className="px-3 py-2.5 text-center">
											<div className="flex items-center justify-center gap-1.5 flex-wrap">
												{lead.phone ? (
													<PhoneCopyPill phone={lead.phone} />
												) : (
													<span className="text-[10px] text-muted-foreground font-mono">
														Chưa mở khóa
													</span>
												)}
												<ZaloOutreachButton
													leadId={lead.id}
													workspaceId={workspaceId}
													phone={lead.phone}
													companyName={lead.company_name}
													intent={lead.intent}
													source={lead.source}
													contentSnippet={lead.content_snippet}
												/>
											</div>
										</td>
									</tr>
								);
							})}
						</tbody>
					</table>
				)}

				{/* More leads ready to unlock (Bottom Box) */}
				{leads.length > 0 && (
					<div className="p-8 flex flex-col items-center justify-center border-t border-border/60 bg-muted/10 text-center">
						<div className="w-10 h-10 rounded-full bg-muted border border-border flex items-center justify-center text-muted-foreground mb-2">
							<Lock className="w-4 h-4" />
						</div>
						<h4 className="text-xs font-bold text-foreground">More leads ready to unlock</h4>
						<p className="text-[11px] text-muted-foreground mb-2">
							Upgrade to add them to your list
						</p>
						<button
							type="button"
							className="text-xs font-semibold text-emerald-600 dark:text-emerald-400 hover:underline flex items-center gap-1 cursor-pointer"
						>
							Unlock more leads &gt;
						</button>
					</div>
				)}
			</div>
		</div>
	);
};
