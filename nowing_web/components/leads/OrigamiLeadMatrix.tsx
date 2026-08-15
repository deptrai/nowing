"use client";

import { useAtom } from "jotai";
import {
	Building2,
	Eye,
	Maximize2,
	Minimize2,
	Network,
	RefreshCw,
	Search,
	Sparkles,
	Users,
} from "lucide-react";
import type React from "react";
import { useMemo } from "react";
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

const getFitScoreBadge = (score: number | null | undefined) => {
	if (score == null) {
		return {
			label: "Chờ chấm",
			score: null,
			colorClass: "bg-zinc-800/60 text-zinc-400 border-zinc-700/50",
		};
	}
	const val = Number.isFinite(score) ? score : 0;
	if (val >= 80) {
		return {
			label: "High Fit",
			score: val,
			colorClass: "bg-emerald-500/15 text-emerald-400 border-emerald-500/30",
		};
	}
	if (val >= 50) {
		return {
			label: "Med Fit",
			score: val,
			colorClass: "bg-amber-500/15 text-amber-400 border-amber-500/30",
		};
	}
	return {
		label: "Low Fit",
		score: val,
		colorClass: "bg-rose-500/15 text-rose-400 border-rose-500/30",
	};
};

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

	return (
		<div
			data-testid="origami-lead-matrix"
			className={cn(
				"h-full flex flex-col bg-zinc-950 text-zinc-100 overflow-hidden",
				isFullscreen && "fixed inset-0 z-50",
				className
			)}
		>
			{/* Workbench Header Toolbar */}
			<div className="p-3.5 border-b border-zinc-800/80 bg-zinc-900/50 soc-caro-grid flex flex-wrap items-center justify-between gap-3">
				<div className="flex items-center gap-2 flex-1 min-w-[280px]">
					{/* Search Box */}
					<div className="relative flex-1 max-w-md">
						<Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-zinc-400" />
						<input
							type="text"
							value={searchQuery}
							onChange={(e) => onSearchQueryChange(e.target.value)}
							placeholder="Tìm theo tên, SĐT, ngành nghề, địa điểm (⌘K)..."
							className="w-full pl-9 pr-3 py-1.5 rounded-xl border border-zinc-800 bg-zinc-950 text-xs text-zinc-100 placeholder-zinc-500 focus:outline-none focus:border-emerald-500/50 focus:ring-1 focus:ring-emerald-500/30 transition-all"
						/>
					</div>

					{/* Source Filter */}
					<select
						value={sourceFilter}
						onChange={(e) => onSourceFilterChange(e.target.value)}
						className="px-2.5 py-1.5 rounded-xl border border-zinc-800 bg-zinc-950 text-xs text-zinc-300 focus:outline-none focus:border-emerald-500/50 cursor-pointer"
					>
						<option value="all">Tất cả nguồn</option>
						<option value="batdongsan">🏠 Batdongsan</option>
						<option value="facebook">👥 Facebook</option>
						<option value="telegram">✈️ Telegram</option>
						<option value="topcv">💼 TopCV / ITviec</option>
						<option value="tender">🏛️ Đấu Thầu</option>
						<option value="linkedin">💼 LinkedIn</option>
						<option value="twitter">𝕏 Twitter/X</option>
					</select>

					{/* Status Filter */}
					<select
						value={statusFilter}
						onChange={(e) => onStatusFilterChange(e.target.value)}
						className="px-2.5 py-1.5 rounded-xl border border-zinc-800 bg-zinc-950 text-xs text-zinc-300 focus:outline-none focus:border-emerald-500/50 cursor-pointer"
					>
						<option value="all">Tất cả trạng thái</option>
						<option value="new">Mới</option>
						<option value="contacted">Đã liên hệ</option>
						<option value="qualified">Tiềm năng cao</option>
						<option value="converted">Đã chuyển đổi</option>
					</select>
				</div>

				<div className="flex items-center gap-2">
					{onOpenReverseIcp && (
						<button
							type="button"
							onClick={onOpenReverseIcp}
							className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white transition-colors cursor-pointer shadow-sm shadow-emerald-950"
						>
							<Sparkles className="w-3.5 h-3.5" />
							Reverse ICP
						</button>
					)}

					<button
						type="button"
						onClick={onRefresh}
						disabled={isLoading}
						title="Làm mới bảng"
						className="p-1.5 rounded-xl border border-zinc-800 bg-zinc-900/80 hover:bg-zinc-800 text-zinc-400 hover:text-zinc-100 transition-colors cursor-pointer"
					>
						<RefreshCw className={cn("w-4 h-4", isLoading && "animate-spin text-emerald-400")} />
					</button>

					<button
						type="button"
						onClick={() => setIsFullscreen((prev) => !prev)}
						title={isFullscreen ? "Thu nhỏ" : "Toàn màn hình"}
						className="p-1.5 rounded-xl border border-zinc-800 bg-zinc-900/80 hover:bg-zinc-800 text-zinc-400 hover:text-zinc-100 transition-colors cursor-pointer"
					>
						{isFullscreen ? <Minimize2 className="w-4 h-4" /> : <Maximize2 className="w-4 h-4" />}
					</button>
				</div>
			</div>

			{/* Table Container */}
			<div className="flex-1 overflow-auto scrollbar-thin">
				{leads.length === 0 ? (
					<div className="h-full min-h-[300px] flex flex-col items-center justify-center p-8 text-center soc-caro-grid">
						<div className="w-12 h-12 rounded-2xl bg-zinc-900 border border-zinc-800 flex items-center justify-center text-zinc-400 mb-3 shadow-md">
							<Users className="w-6 h-6 text-emerald-400" />
						</div>
						<h3 className="text-sm font-bold text-zinc-200 mb-1">Chưa có dữ liệu Leads</h3>
						<p className="text-xs text-zinc-400 max-w-sm mb-4">
							Hãy sử dụng AI Co-pilot bên trái hoặc kích hoạt Reverse ICP từ Website để thu thập
							danh sách khách hàng tiềm năng.
						</p>
						{onOpenReverseIcp && (
							<button
								type="button"
								onClick={onOpenReverseIcp}
								className="inline-flex items-center gap-1.5 px-3.5 py-2 text-xs font-semibold rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white transition-colors cursor-pointer shadow-sm"
							>
								<Sparkles className="w-4 h-4" />
								Phân tích ICP từ URL Website
							</button>
						)}
					</div>
				) : (
					<table className="w-full text-left text-xs text-zinc-300 border-collapse">
						<thead className="sticky top-0 z-10 bg-zinc-950/95 text-[11px] uppercase tracking-wider text-zinc-400 border-b border-zinc-800/80 backdrop-blur-xs">
							<tr>
								<th scope="col" className="w-10 px-4 py-3 text-center">
									<input
										type="checkbox"
										checked={isAllSelected}
										onChange={handleSelectAll}
										className="rounded border-zinc-700 bg-zinc-900 text-emerald-500 focus:ring-emerald-500/30 cursor-pointer"
									/>
								</th>
								<th scope="col" className="px-4 py-3 font-semibold">
									Doanh nghiệp / Khách hàng
								</th>
								<th scope="col" className="px-4 py-3 font-semibold">
									Nguồn & Intent
								</th>
								<th scope="col" className="px-4 py-3 font-semibold">
									SĐT Đã Giải Mã
								</th>
								<th scope="col" className="px-4 py-3 font-semibold">
									Điểm Tiềm Năng (Fit)
								</th>
								<th scope="col" className="px-4 py-3 font-semibold">
									Địa Điểm & Giá
								</th>
								<th scope="col" className="px-4 py-3 font-semibold text-center">
									Tiếp Cận Zalo
								</th>
								<th scope="col" className="px-4 py-3 font-semibold text-right">
									Thao Tác
								</th>
							</tr>
						</thead>
						<tbody className="divide-y divide-zinc-800/60">
							{leads.map((lead) => {
								const isSelected = selectedLeadIds.includes(lead.id);
								const isContextActive = selectedLeadContext?.id === lead.id;
								const isHighlighted = highlightedRowIds.includes(lead.id);
								const fit = getFitScoreBadge(lead.fit_score);

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
											"transition-colors cursor-pointer group focus:outline-none focus:bg-zinc-900/80",
											isSelected && "bg-emerald-950/20",
											isContextActive && "bg-emerald-950/40 ring-1 ring-inset ring-emerald-500/50",
											isHighlighted && "bg-blue-950/30 ring-1 ring-inset ring-blue-500/40",
											!isSelected && !isContextActive && !isHighlighted && "hover:bg-zinc-900/60"
										)}
									>
										{/* Checkbox */}
										<td className="w-10 px-4 py-3 text-center">
											<input
												type="checkbox"
												data-lead-checkbox="true"
												checked={isSelected}
												onClick={(e) => e.stopPropagation()}
												onChange={(e) => handleToggleLead(lead.id, e)}
												className="rounded border-zinc-700 bg-zinc-900 text-emerald-500 focus:ring-emerald-500/30 cursor-pointer"
											/>
										</td>

										{/* Company & Info */}
										<td className="px-4 py-3 space-y-1">
											<div className="flex items-center gap-1.5 font-bold text-zinc-100">
												<Building2 className="w-3.5 h-3.5 text-zinc-400 shrink-0" />
												<span className="truncate max-w-[220px]">{lead.company_name}</span>
											</div>
											{lead.content_snippet && (
												<p className="text-[11px] text-zinc-400 truncate max-w-[240px]">
													{lead.content_snippet}
												</p>
											)}
										</td>

										{/* Source & Intent */}
										<td className="px-4 py-3">
											<div className="flex flex-col gap-1 items-start">
												<span className="text-[10px] font-semibold uppercase px-2 py-0.5 rounded bg-zinc-900 text-zinc-300 border border-zinc-800">
													{lead.source}
												</span>
												{lead.intent && (
													<span className="text-[10px] text-zinc-400">
														Intent: <span className="font-semibold">{lead.intent}</span>
													</span>
												)}
											</div>
										</td>

										{/* Decoded Phone */}
										<td className="px-4 py-3">
											{lead.phone ? (
												<PhoneCopyPill phone={lead.phone} />
											) : (
												<span className="text-xs text-zinc-500 font-mono">Chưa mở khóa</span>
											)}
										</td>

										{/* Fit Score */}
										<td className="px-4 py-3">
											<span
												className={cn(
													"inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-semibold border",
													fit.colorClass
												)}
											>
												<Sparkles className="w-3 h-3" />
												<span className="font-mono">
													{fit.score !== null ? `${fit.score}%` : "Chờ chấm"}
												</span>
												{fit.score !== null && (
													<span className="text-[10px] opacity-80">{fit.label}</span>
												)}
											</span>
										</td>

										{/* Location & Price */}
										<td className="px-4 py-3 space-y-0.5">
											{lead.location && (
												<div className="text-[11px] text-zinc-300 truncate max-w-[150px]">
													{lead.location}
												</div>
											)}
											{(lead.price_estimate ||
												(lead as unknown as Record<string, string | undefined>).price) && (
												<div className="font-mono text-emerald-400 font-bold text-[11px]">
													{lead.price_estimate ||
														(lead as unknown as Record<string, string | undefined>).price}
												</div>
											)}
										</td>

										{/* Zalo Outreach Button */}
										<td className="px-4 py-3 text-center">
											<ZaloOutreachButton
												leadId={lead.id}
												workspaceId={workspaceId}
												phone={lead.phone}
												companyName={lead.company_name}
												intent={lead.intent}
												source={lead.source}
												contentSnippet={lead.content_snippet}
											/>
										</td>

										{/* Actions */}
										<td className="px-4 py-3 text-right">
											<div className="flex items-center justify-end gap-1">
												{onOpenCompanyGraph && (
													<button
														type="button"
														onClick={(e) => {
															e.stopPropagation();
															onOpenCompanyGraph(lead.company_name);
														}}
														title="Xem Company Graph"
														className="p-1 rounded hover:bg-zinc-800 text-zinc-400 hover:text-blue-400 transition-colors cursor-pointer"
													>
														<Network className="w-4 h-4" />
													</button>
												)}
												<button
													type="button"
													onClick={(e) => {
														e.stopPropagation();
														handleRowClick(lead);
													}}
													title="Xem chi tiết"
													className="p-1 rounded hover:bg-zinc-800 text-zinc-400 hover:text-zinc-100 transition-colors cursor-pointer"
												>
													<Eye className="w-4 h-4" />
												</button>
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
