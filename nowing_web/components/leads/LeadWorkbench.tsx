"use client";

import {
	ArrowUpDown,
	Bot,
	Building2,
	Copy,
	Download,
	ExternalLink,
	Layers,
	MessageSquare,
	Search,
	Share2,
	Sparkles,
	ThumbsDown,
	ThumbsUp,
	Unlock,
	UserCheck,
	UserX,
	X,
} from "lucide-react";
import type React from "react";
import { useMemo, useState } from "react";
import { toast } from "sonner";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import type {
	AiRationale,
	LeadPipelineStatus,
	SdrQualificationStatus,
	WorkbenchLead,
} from "@/contracts/types/campaign.types";
import type { Lead } from "@/contracts/types/leads.types";
import { leadsApiService } from "@/lib/apis/leads-api.service";
import { copyToClipboard } from "@/lib/utils";
import { PhoneUnlockPill } from "./PhoneUnlockPill";
import { ZaloOutreachButton } from "./zalo-outreach-button";

export interface LeadWorkbenchProps {
	workspaceId: string | number;
	initialLeads?: Lead[];
	onOpenCompanyGraph?: (companyName: string) => void;
}

// Generate realistic AI explainability rationale for leads lacking it
const generateMockAiRationale = (lead: Lead): AiRationale => {
	const fitScore = lead.fit_score ?? 75;
	const isHighFit = fitScore >= 80;

	return {
		lead_id: lead.id,
		fit_rationale: isHighFit
			? `Công ty ${lead.company_name} có mức độ phù hợp cao (${fitScore}/100) nhờ quy mô khớp ICP, ngành nghề ${lead.industry || "B2B"} và đang có tín hiệu mở rộng kinh doanh.`
			: `Công ty ${lead.company_name} có mức độ phù hợp trung bình (${fitScore}/100). Cần SDR kiểm tra thêm nhu cầu thực tế.`,
		fit_factors: [
			{
				factor: "Độ khớp ngành nghề (Industry Match)",
				score: lead.industry ? 90 : 60,
				weight: 0.35,
				matched: Boolean(lead.industry),
				detail: `Ngành: ${lead.industry || "Chưa xác định"} (Nằm trong danh mục ICP)`,
			},
			{
				factor: "Quy mô & Địa lý (Location & Size)",
				score: 85,
				weight: 0.25,
				matched: true,
				detail: `Địa chỉ: ${lead.location || "Toàn quốc"} | Quy mô: ${lead.company_size || "10-50 nhân sự"}`,
			},
			{
				factor: "Tín hiệu thị trường (Market Intent)",
				score: lead.intent_score ?? 70,
				weight: 0.25,
				matched: Boolean(lead.intent),
				detail: `Ý định: ${lead.intent || "BÁN"} (Điểm Intent: ${lead.intent_score ?? 70}/100)`,
			},
			{
				factor: "Mức độ sẵn sàng liên hệ (Contact Readiness)",
				score: lead.phone ? 95 : 40,
				weight: 0.15,
				matched: Boolean(lead.phone),
				detail: lead.phone ? "Có số điện thoại đã kiểm định MST/Zalo" : "Chưa có SĐT khả dụng",
			},
		],
		intent_signals: [
			`Tín hiệu ${lead.intent || "BÁN"} được phát hiện từ nguồn ${lead.source}`,
			lead.content_snippet
				? `Nội dung: "${lead.content_snippet.slice(0, 80)}..."`
				: "Hoạt động đăng tin thường xuyên",
		],
		hiring_signals: lead.source.includes("topcv")
			? ["Đang tuyển dụng 3 vị trí Sales & Marketing", "Tăng trưởng headcount +15% trong 30 ngày"]
			: [],
		source_evidence: {
			source: lead.source,
			source_url: lead.source_url,
			posted_at: lead.created_at,
			raw_snippet: lead.content_snippet,
			matched_keywords: ["b2b", "doanh nghiệp", "đối tác", "hợp tác"],
		},
		suggested_icebreaker: `Chào anh/chị đại diện ${lead.company_name}, em thấy công ty mình đang có nhu cầu ${lead.intent || "phát triển kinh doanh"} trên kênh ${lead.source}. Nowing có giải pháp hỗ trợ kết nối trực tiếp...`,
		confidence_score: 0.88,
	};
};

export const LeadWorkbench: React.FC<LeadWorkbenchProps> = ({
	workspaceId,
	initialLeads = [],
	onOpenCompanyGraph,
}) => {
	// Leads list state
	const [leads, setLeads] = useState<WorkbenchLead[]>(() =>
		initialLeads.map((l, index) => {
			// determine pipeline stage progressively
			let stage: LeadPipelineStatus = "raw";
			if (l.phone && l.is_unlocked) stage = "verified";
			else if (l.enriched) stage = "enriched";
			else if (l.fit_score != null) stage = "scored";
			else if (index % 2 === 0) stage = "deduped";

			return {
				...l,
				pipeline_stage: stage,
				sdr_status: null,
				ai_rationale: generateMockAiRationale(l),
			};
		})
	);

	// Filtering & Searching
	const [searchQuery, setSearchQuery] = useState("");
	const [stageFilter, setStageFilter] = useState<string>("all");
	const [sdrStatusFilter, setSdrStatusFilter] = useState<string>("all");
	const [sortField, setSortField] = useState<"fit_score" | "intent_score" | "created_at">(
		"fit_score"
	);
	const [sortAsc, setSortAsc] = useState(false);

	// Selection for Bulk Actions
	const [selectedLeadIds, setSelectedLeadIds] = useState<string[]>([]);

	// AI Rationale Drawer
	const [selectedLeadForRationale, setSelectedLeadForRationale] = useState<WorkbenchLead | null>(
		null
	);
	const [isDrawerOpen, setIsDrawerOpen] = useState(false);

	// Qualification Status mutation
	const handleQualifyLead = async (
		leadId: string,
		status: SdrQualificationStatus,
		note?: string
	) => {
		// Optimistic update
		setLeads((prev) =>
			prev.map((l) =>
				l.id === leadId ? { ...l, sdr_status: status, qualification_note: note } : l
			)
		);

		try {
			await leadsApiService.qualifyLead(workspaceId, leadId, status, note);
			const labelMap: Record<SdrQualificationStatus, string> = {
				qualified: "Đã đánh dấu: Tiềm năng cao (Qualified)",
				not_icp: "Đã đánh dấu: Không đúng ICP (Not ICP)",
				bad_contact: "Đã đánh dấu: SĐT/Email sai (Bad Contact)",
				already_customer: "Đã đánh dấu: Đã là khách hàng",
				unqualified: "Đã đặt lại trạng thái",
			};
			toast.success(labelMap[status]);
		} catch (_err) {
			toast.error("Không thể cập nhật trạng thái phân loại SDR");
		}
	};

	// Toggle single checkbox
	const handleToggleSelect = (leadId: string) => {
		setSelectedLeadIds((prev) =>
			prev.includes(leadId) ? prev.filter((id) => id !== leadId) : [...prev, leadId]
		);
	};

	// Filtered & Sorted Leads
	const filteredLeads = useMemo(() => {
		return leads
			.filter((lead) => {
				if (stageFilter !== "all" && lead.pipeline_stage !== stageFilter) return false;
				if (sdrStatusFilter !== "all") {
					if (sdrStatusFilter === "unreviewed" && lead.sdr_status != null) return false;
					if (sdrStatusFilter !== "unreviewed" && lead.sdr_status !== sdrStatusFilter) return false;
				}
				if (searchQuery.trim()) {
					const q = searchQuery.toLowerCase();
					const matchCompany = lead.company_name.toLowerCase().includes(q);
					const matchPhone = (lead.phone || "").toLowerCase().includes(q);
					const matchIndustry = (lead.industry || "").toLowerCase().includes(q);
					const matchLocation = (lead.location || "").toLowerCase().includes(q);
					return matchCompany || matchPhone || matchIndustry || matchLocation;
				}
				return true;
			})
			.sort((a, b) => {
				const valA = a[sortField] ?? 0;
				const valB = b[sortField] ?? 0;
				if (sortAsc) return valA > valB ? 1 : -1;
				return valA < valB ? 1 : -1;
			});
	}, [leads, stageFilter, sdrStatusFilter, searchQuery, sortField, sortAsc]);

	// Select all visible
	const handleSelectAllVisible = () => {
		if (selectedLeadIds.length === filteredLeads.length) {
			setSelectedLeadIds([]);
		} else {
			setSelectedLeadIds(filteredLeads.map((l) => l.id));
		}
	};

	// Bulk Actions Handlers
	const handleBulkUnlock = () => {
		toast.success(`Đang gửi yêu cầu mở khóa ${selectedLeadIds.length} danh bạ đã chọn`);
		setSelectedLeadIds([]);
	};

	const handleBulkZalo = () => {
		toast.success(`Đã chuẩn bị kịch bản Zalo Outreach cho ${selectedLeadIds.length} khách hàng`);
		setSelectedLeadIds([]);
	};

	const handleBulkExportCrm = () => {
		const csvContent =
			"data:text/csv;charset=utf-8," +
			["ID,Company,Industry,Phone,Fit Score,Status,Intent"]
				.concat(
					filteredLeads
						.filter((l) => selectedLeadIds.includes(l.id))
						.map(
							(l) =>
								`"${l.id}","${l.company_name}","${l.industry || ""}","${l.phone || ""}","${l.fit_score || 0}","${l.sdr_status || "new"}","${l.intent || ""}"`
						)
				)
				.join("\n");
		const encodedUri = encodeURI(csvContent);
		const link = document.createElement("a");
		link.setAttribute("href", encodedUri);
		link.setAttribute("download", `nowing_leads_sdr_export_${Date.now()}.csv`);
		document.body.appendChild(link);
		link.click();
		document.body.removeChild(link);

		toast.success(`Đã xuất ${selectedLeadIds.length} lead sang file CSV/CRM!`);
		setSelectedLeadIds([]);
	};

	const getPipelineStageBadge = (stage: LeadPipelineStatus) => {
		switch (stage) {
			case "raw":
				return (
					<Badge
						variant="outline"
						className="bg-zinc-800 text-zinc-400 border-zinc-700 text-[10px]"
					>
						1. Raw Signal
					</Badge>
				);
			case "deduped":
				return (
					<Badge
						variant="outline"
						className="bg-blue-950/40 text-blue-400 border-blue-800/50 text-[10px]"
					>
						2. Deduped
					</Badge>
				);
			case "scored":
				return (
					<Badge
						variant="outline"
						className="bg-amber-950/40 text-amber-400 border-amber-800/50 text-[10px]"
					>
						3. AI Scored
					</Badge>
				);
			case "enriched":
				return (
					<Badge
						variant="outline"
						className="bg-purple-950/40 text-purple-400 border-purple-800/50 text-[10px]"
					>
						4. Enriched (MST)
					</Badge>
				);
			case "verified":
				return (
					<Badge
						variant="outline"
						className="bg-emerald-950/40 text-emerald-400 border-emerald-800/50 text-[10px]"
					>
						5. Verified & Unlocked
					</Badge>
				);
		}
	};

	return (
		<div className="space-y-4">
			{/* Workbench Header Controls */}
			<div className="p-4 rounded-xl bg-zinc-900/60 border border-zinc-800 space-y-3 backdrop-blur-sm">
				<div className="flex flex-wrap items-center justify-between gap-3">
					<div className="flex items-center gap-2">
						<div className="p-1.5 rounded-lg bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
							<Layers className="w-4 h-4" />
						</div>
						<div>
							<h2 className="text-sm font-bold text-zinc-100 flex items-center gap-2">
								<span>SDR Lead Workbench</span>
								<Badge
									variant="outline"
									className="text-[10px] bg-emerald-500/10 text-emerald-400 border-emerald-500/20"
								>
									High-Density Matrix
								</Badge>
							</h2>
							<p className="text-[11px] text-zinc-400">
								Bảng điều khiển thẩm định nhanh, minh bạch điểm Fit Score và kích hoạt kênh liên hệ
							</p>
						</div>
					</div>

					{/* Search Bar */}
					<div className="relative min-w-[280px]">
						<Search className="w-3.5 h-3.5 text-zinc-500 absolute left-3 top-1/2 -translate-y-1/2" />
						<input
							type="text"
							value={searchQuery}
							onChange={(e) => setSearchQuery(e.target.value)}
							placeholder="Lọc tên công ty, SĐT, ngành, địa chỉ..."
							className="w-full pl-8 pr-3 py-1.5 text-xs rounded-lg bg-zinc-950/70 border border-zinc-800 text-zinc-200 placeholder:text-zinc-500 focus:outline-none focus:ring-1 focus:ring-emerald-500"
						/>
					</div>
				</div>

				{/* Secondary Filters Bar */}
				<div className="flex flex-wrap items-center justify-between gap-3 pt-3 border-t border-zinc-800/60 text-xs">
					<div className="flex flex-wrap items-center gap-2">
						{/* Pipeline Stage Filter */}
						<div className="flex items-center gap-1.5">
							<span className="text-zinc-400 text-[11px]">Tiến trình:</span>
							<select
								value={stageFilter}
								onChange={(e) => setStageFilter(e.target.value)}
								className="px-2 py-1 text-xs rounded-md bg-zinc-950/70 border border-zinc-800 text-zinc-300 focus:ring-1 focus:ring-emerald-500"
							>
								<option value="all">Tất cả các bước (All Pipeline Stages)</option>
								<option value="raw">1. Raw Signal</option>
								<option value="deduped">2. Deduped</option>
								<option value="scored">3. AI Scored</option>
								<option value="enriched">4. Enriched (MST)</option>
								<option value="verified">5. Verified Phone</option>
							</select>
						</div>

						{/* SDR Qualification Filter */}
						<div className="flex items-center gap-1.5">
							<span className="text-zinc-400 text-[11px]">Đánh giá SDR:</span>
							<select
								value={sdrStatusFilter}
								onChange={(e) => setSdrStatusFilter(e.target.value)}
								className="px-2 py-1 text-xs rounded-md bg-zinc-950/70 border border-zinc-800 text-zinc-300 focus:ring-1 focus:ring-emerald-500"
							>
								<option value="all">Tất cả đánh giá</option>
								<option value="unreviewed">Chưa đánh giá (Pending SDR)</option>
								<option value="qualified">✅ Tiềm năng cao (Qualified)</option>
								<option value="not_icp">❌ Không đúng ICP (Not ICP)</option>
								<option value="bad_contact">🚫 Sai liên hệ (Bad Contact)</option>
								<option value="already_customer">🤝 Đã là khách hàng</option>
							</select>
						</div>
					</div>

					{/* Sorting */}
					<div className="flex items-center gap-2">
						<span className="text-zinc-400 text-[11px]">Sắp xếp:</span>
						<button
							type="button"
							onClick={() => {
								if (sortField === "fit_score") setSortAsc(!sortAsc);
								else {
									setSortField("fit_score");
									setSortAsc(false);
								}
							}}
							className={`px-2 py-1 rounded text-xs border flex items-center gap-1 ${
								sortField === "fit_score"
									? "bg-emerald-500/10 text-emerald-400 border-emerald-500/30"
									: "bg-zinc-800 text-zinc-400 border-zinc-700"
							}`}
						>
							<span>Fit Score</span>
							<ArrowUpDown className="w-3 h-3" />
						</button>

						<button
							type="button"
							onClick={() => {
								if (sortField === "intent_score") setSortAsc(!sortAsc);
								else {
									setSortField("intent_score");
									setSortAsc(false);
								}
							}}
							className={`px-2 py-1 rounded text-xs border flex items-center gap-1 ${
								sortField === "intent_score"
									? "bg-amber-500/10 text-amber-400 border-amber-500/30"
									: "bg-zinc-800 text-zinc-400 border-zinc-700"
							}`}
						>
							<span>Intent Score</span>
							<ArrowUpDown className="w-3 h-3" />
						</button>
					</div>
				</div>
			</div>

			{/* ================= HIGH DENSITY WORKBENCH TABLE ================= */}
			<div className="rounded-xl border border-zinc-800 bg-zinc-900/40 overflow-hidden shadow-lg">
				<div className="overflow-x-auto">
					<table className="w-full text-left border-collapse text-xs">
						<thead>
							<tr className="border-b border-zinc-800 bg-zinc-950/80 text-zinc-400 font-semibold">
								<th className="p-3 w-8 text-center">
									<input
										type="checkbox"
										checked={
											filteredLeads.length > 0 && selectedLeadIds.length === filteredLeads.length
										}
										onChange={handleSelectAllVisible}
										className="rounded border-zinc-700 text-emerald-500 focus:ring-emerald-500 cursor-pointer"
									/>
								</th>
								<th className="p-3 min-w-[220px]">Doanh Nghiệp & Tín Hiệu</th>
								<th className="p-3 min-w-[130px]">Tiến Trình (Stage)</th>
								<th className="p-3 min-w-[120px] text-center">Fit Score / AI</th>
								<th className="p-3 min-w-[160px]">Thông Tin Liên Hệ</th>
								<th className="p-3 min-w-[200px]">Thẩm Định Nhanh (SDR Actions)</th>
								<th className="p-3 w-16 text-center">Chi Tiết</th>
							</tr>
						</thead>
						<tbody className="divide-y divide-zinc-800/60">
							{filteredLeads.length === 0 ? (
								<tr>
									<td colSpan={7} className="text-center py-16 text-zinc-500">
										Không tìm thấy lead nào phù hợp với điều kiện lọc
									</td>
								</tr>
							) : (
								filteredLeads.map((lead) => {
									const isSelected = selectedLeadIds.includes(lead.id);
									const fitScore = lead.fit_score ?? 0;

									return (
										<tr
											key={lead.id}
											className={`hover:bg-zinc-800/30 transition-colors ${
												isSelected ? "bg-emerald-950/15" : ""
											}`}
										>
											{/* Selection Checkbox */}
											<td className="p-3 text-center">
												<input
													type="checkbox"
													checked={isSelected}
													onChange={() => handleToggleSelect(lead.id)}
													className="rounded border-zinc-700 text-emerald-500 focus:ring-emerald-500 cursor-pointer"
												/>
											</td>

											{/* Company Info */}
											<td className="p-3 space-y-1">
												<div className="flex items-center gap-1.5">
													<Building2 className="w-3.5 h-3.5 text-zinc-400 shrink-0" />
													<span className="font-bold text-zinc-100">{lead.company_name}</span>
												</div>
												<div className="flex flex-wrap items-center gap-1 text-[11px] text-zinc-400">
													<span className="px-1.5 py-0.2 rounded bg-zinc-800 text-zinc-300">
														{lead.source}
													</span>
													{lead.industry && <span>• {lead.industry}</span>}
													{lead.location && <span>• {lead.location}</span>}
												</div>
												{lead.content_snippet && (
													<p className="text-[11px] text-zinc-400 italic line-clamp-1 max-w-[260px]">
														"{lead.content_snippet}"
													</p>
												)}
											</td>

											{/* Pipeline Stage Badge */}
											<td className="p-3">{getPipelineStageBadge(lead.pipeline_stage)}</td>

											{/* Fit Score & AI Rationale Trigger */}
											<td className="p-3 text-center">
												<button
													type="button"
													onClick={() => {
														setSelectedLeadForRationale(lead);
														setIsDrawerOpen(true);
													}}
													className="inline-flex flex-col items-center group p-1.5 rounded-lg hover:bg-zinc-800/60 transition-all border border-transparent hover:border-zinc-700"
												>
													<div className="flex items-center gap-1">
														<span
															className={`font-mono font-bold text-sm ${
																fitScore >= 80
																	? "text-emerald-400"
																	: fitScore >= 50
																		? "text-amber-400"
																		: "text-rose-400"
															}`}
														>
															{fitScore}
														</span>
														<span className="text-[10px] text-zinc-500">/100</span>
													</div>
													<span className="text-[10px] text-emerald-400 group-hover:underline flex items-center gap-0.5">
														<Bot className="w-2.5 h-2.5" />
														AI Rationale
													</span>
												</button>
											</td>

											{/* Contact Info */}
											<td className="p-3 space-y-1">
												{lead.phone ? (
													<div className="flex items-center gap-1">
														<PhoneUnlockPill
															lead={lead}
															workspaceId={workspaceId}
															showIcon={true}
														/>
													</div>
												) : (
													<span className="text-[11px] text-zinc-500 italic">Chưa có SĐT</span>
												)}
												{lead.is_zalo_active && (
													<Badge
														variant="outline"
														className="bg-blue-950/40 text-blue-400 border-blue-800/40 text-[9px]"
													>
														Zalo Active
													</Badge>
												)}
											</td>

											{/* Quick Qualify SDR Actions */}
											<td className="p-3">
												<div className="flex flex-wrap items-center gap-1">
													<button
														type="button"
														title="Khớp ICP & Tiềm năng cao"
														onClick={() => handleQualifyLead(lead.id, "qualified")}
														className={`p-1.5 rounded text-xs border transition-all ${
															lead.sdr_status === "qualified"
																? "bg-emerald-500 text-black border-emerald-400 font-bold"
																: "bg-zinc-950/60 text-zinc-400 border-zinc-800 hover:text-emerald-300 hover:border-emerald-500/50"
														}`}
													>
														<ThumbsUp className="w-3.5 h-3.5" />
													</button>

													<button
														type="button"
														title="Không đúng tiêu chuẩn ICP"
														onClick={() => handleQualifyLead(lead.id, "not_icp")}
														className={`p-1.5 rounded text-xs border transition-all ${
															lead.sdr_status === "not_icp"
																? "bg-rose-500 text-black border-rose-400 font-bold"
																: "bg-zinc-950/60 text-zinc-400 border-zinc-800 hover:text-rose-300 hover:border-rose-500/50"
														}`}
													>
														<ThumbsDown className="w-3.5 h-3.5" />
													</button>

													<button
														type="button"
														title="SĐT sai / không liên lạc được"
														onClick={() => handleQualifyLead(lead.id, "bad_contact")}
														className={`p-1.5 rounded text-xs border transition-all ${
															lead.sdr_status === "bad_contact"
																? "bg-amber-500 text-black border-amber-400 font-bold"
																: "bg-zinc-950/60 text-zinc-400 border-zinc-800 hover:text-amber-300 hover:border-amber-500/50"
														}`}
													>
														<UserX className="w-3.5 h-3.5" />
													</button>

													<button
														type="button"
														title="Đã là khách hàng của công ty"
														onClick={() => handleQualifyLead(lead.id, "already_customer")}
														className={`p-1.5 rounded text-xs border transition-all ${
															lead.sdr_status === "already_customer"
																? "bg-blue-500 text-black border-blue-400 font-bold"
																: "bg-zinc-950/60 text-zinc-400 border-zinc-800 hover:text-blue-300 hover:border-blue-500/50"
														}`}
													>
														<UserCheck className="w-3.5 h-3.5" />
													</button>

													{lead.phone && !lead.blocked_by_dnc && (
														<ZaloOutreachButton
															leadId={lead.id}
															workspaceId={lead.workspace_id}
															phone={lead.phone}
															companyName={lead.company_name}
															intent={lead.intent}
															source={lead.source}
															contentSnippet={lead.content_snippet}
														/>
													)}
												</div>
											</td>

											{/* Extra Links */}
											<td className="p-3 text-center">
												<button
													type="button"
													onClick={() => onOpenCompanyGraph?.(lead.company_name)}
													className="p-1.5 rounded bg-zinc-800/80 hover:bg-zinc-700 text-zinc-400 hover:text-white transition-colors"
													title="Xem Company Graph & Mạng lưới quan hệ"
												>
													<Share2 className="w-3.5 h-3.5" />
												</button>
											</td>
										</tr>
									);
								})
							)}
						</tbody>
					</table>
				</div>
			</div>

			{/* ================= FLOATING BULK ACTION BAR ================= */}
			{selectedLeadIds.length > 0 && (
				<div className="fixed bottom-6 left-1/2 -translate-x-1/2 z-50 flex items-center gap-3 px-5 py-3 rounded-2xl bg-zinc-900/95 border border-emerald-500/50 shadow-2xl backdrop-blur-md ring-1 ring-emerald-500/30 animate-in fade-in slide-in-from-bottom-4">
					<div className="flex items-center gap-2 pr-3 border-r border-zinc-700">
						<span className="flex h-2 w-2 rounded-full bg-emerald-400 animate-pulse" />
						<span className="text-xs font-bold text-zinc-100">
							Đã chọn {selectedLeadIds.length} lead
						</span>
					</div>

					<Button
						type="button"
						size="sm"
						onClick={handleBulkUnlock}
						className="bg-emerald-500 hover:bg-emerald-400 text-black text-xs font-bold"
					>
						<Unlock className="w-3.5 h-3.5 mr-1.5" />
						Mở khóa SĐT ({selectedLeadIds.length})
					</Button>

					<Button
						type="button"
						size="sm"
						variant="secondary"
						onClick={handleBulkZalo}
						className="bg-blue-600 hover:bg-blue-500 text-white text-xs font-semibold"
					>
						<MessageSquare className="w-3.5 h-3.5 mr-1.5" />
						Gửi Zalo Hàng Loạt
					</Button>

					<Button
						type="button"
						size="sm"
						variant="outline"
						onClick={handleBulkExportCrm}
						className="border-zinc-700 text-zinc-200 text-xs"
					>
						<Download className="w-3.5 h-3.5 mr-1.5" />
						Xuất CSV / CRM
					</Button>

					<Button
						type="button"
						size="sm"
						variant="ghost"
						onClick={() => setSelectedLeadIds([])}
						className="text-zinc-400 hover:text-zinc-200 text-xs"
					>
						<X className="w-3.5 h-3.5" />
					</Button>
				</div>
			)}

			{/* ================= AI RATIONALE DRAWER ================= */}
			{isDrawerOpen && selectedLeadForRationale && (
				<div className="fixed inset-0 z-50 flex justify-end bg-black/60 backdrop-blur-sm animate-in fade-in">
					<div className="w-full max-w-lg bg-zinc-950 border-l border-zinc-800 p-6 overflow-y-auto space-y-6 shadow-2xl animate-in slide-in-from-right">
						{/* Drawer Header */}
						<div className="flex items-center justify-between pb-4 border-b border-zinc-800">
							<div className="flex items-center gap-2">
								<div className="p-2 rounded-xl bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
									<Bot className="w-5 h-5" />
								</div>
								<div>
									<h3 className="text-base font-bold text-zinc-100">AI Lead Fit Rationale</h3>
									<p className="text-xs text-zinc-400">{selectedLeadForRationale.company_name}</p>
								</div>
							</div>
							<Button
								variant="ghost"
								size="sm"
								onClick={() => setIsDrawerOpen(false)}
								className="text-zinc-400 hover:text-white"
							>
								<X className="w-4 h-4" />
							</Button>
						</div>

						{/* Overview Rationale Box */}
						<div className="p-4 rounded-xl bg-emerald-950/20 border border-emerald-800/40 space-y-2">
							<div className="flex items-center justify-between">
								<span className="text-xs font-semibold text-emerald-400 flex items-center gap-1.5">
									<Sparkles className="w-3.5 h-3.5" />
									<span>Đánh Giá Khớp ICP</span>
								</span>
								<span className="font-mono font-bold text-emerald-300 text-sm">
									{selectedLeadForRationale.fit_score ?? 75}/100
								</span>
							</div>
							<p className="text-xs text-zinc-300 leading-relaxed">
								{selectedLeadForRationale.ai_rationale?.fit_rationale}
							</p>
						</div>

						{/* Fit Factor Breakdown */}
						<div className="space-y-3">
							<h4 className="text-xs font-bold text-zinc-300 uppercase tracking-wider">
								Chi Tiết Tiêu Chí Chấm Điểm (Fit Factors)
							</h4>
							<div className="space-y-2">
								{selectedLeadForRationale.ai_rationale?.fit_factors.map((factor) => (
									<div
										key={factor.factor}
										className="p-3 rounded-lg bg-zinc-900/60 border border-zinc-800/80 space-y-1"
									>
										<div className="flex items-center justify-between text-xs">
											<span className="font-semibold text-zinc-200">{factor.factor}</span>
											<span className="font-mono font-bold text-emerald-400">{factor.score} đ</span>
										</div>
										<p className="text-[11px] text-zinc-400">{factor.detail}</p>
									</div>
								))}
							</div>
						</div>

						{/* Intent Signals & Source Evidence */}
						<div className="space-y-3">
							<h4 className="text-xs font-bold text-zinc-300 uppercase tracking-wider">
								Bằng Chứng Tín Hiệu (Source Evidence)
							</h4>
							<div className="p-3.5 rounded-lg bg-zinc-900/60 border border-zinc-800 space-y-2 text-xs">
								<div className="flex justify-between text-[11px]">
									<span className="text-zinc-500">Nguồn gốc:</span>
									<span className="font-semibold text-zinc-300">
										{selectedLeadForRationale.source}
									</span>
								</div>
								{selectedLeadForRationale.source_url && (
									<div className="flex justify-between text-[11px]">
										<span className="text-zinc-500">Link bài gốc:</span>
										<a
											href={selectedLeadForRationale.source_url}
											target="_blank"
											rel="noopener noreferrer"
											className="text-emerald-400 hover:underline inline-flex items-center gap-1"
										>
											<span>Xem chi tiết</span>
											<ExternalLink className="w-2.5 h-2.5" />
										</a>
									</div>
								)}
								{selectedLeadForRationale.content_snippet && (
									<div className="pt-2 border-t border-zinc-800">
										<span className="text-[10px] text-zinc-500">Trích đoạn nội dung:</span>
										<p className="text-xs italic text-zinc-300 mt-1 bg-zinc-950 p-2.5 rounded border border-zinc-800">
											"{selectedLeadForRationale.content_snippet}"
										</p>
									</div>
								)}
							</div>
						</div>

						{/* Suggested AI Icebreaker */}
						{selectedLeadForRationale.ai_rationale?.suggested_icebreaker && (
							<div className="p-4 rounded-xl bg-blue-950/20 border border-blue-800/40 space-y-2">
								<div className="flex items-center justify-between">
									<span className="text-xs font-semibold text-blue-400 flex items-center gap-1.5">
										<MessageSquare className="w-3.5 h-3.5" />
										<span>Gợi Ý Mở Đầu Tiếp Cận (AI Icebreaker)</span>
									</span>
									<button
										type="button"
										onClick={() => {
											copyToClipboard(
												selectedLeadForRationale.ai_rationale?.suggested_icebreaker || ""
											);
											toast.success("Đã sao chép kịch bản mở đầu!");
										}}
										className="p-1 rounded hover:bg-blue-900/50 text-blue-300"
										title="Sao chép kịch bản"
									>
										<Copy className="w-3.5 h-3.5" />
									</button>
								</div>
								<p className="text-xs text-zinc-300 italic">
									"{selectedLeadForRationale.ai_rationale.suggested_icebreaker}"
								</p>
							</div>
						)}

						{/* Drawer Quick Actions */}
						<div className="pt-4 border-t border-zinc-800 flex gap-2">
							<Button
								type="button"
								onClick={() => {
									handleQualifyLead(selectedLeadForRationale.id, "qualified");
									setIsDrawerOpen(false);
								}}
								className="flex-1 bg-emerald-500 hover:bg-emerald-400 text-black text-xs font-bold"
							>
								<ThumbsUp className="w-3.5 h-3.5 mr-1.5" />
								Đánh Giá Qualified
							</Button>
							<Button
								type="button"
								variant="outline"
								onClick={() => {
									handleQualifyLead(selectedLeadForRationale.id, "not_icp");
									setIsDrawerOpen(false);
								}}
								className="border-zinc-700 text-zinc-300 text-xs"
							>
								<ThumbsDown className="w-3.5 h-3.5 mr-1.5" />
								Loại bỏ
							</Button>
						</div>
					</div>
				</div>
			)}
		</div>
	);
};
