"use client";

import { RefreshCw, Search, Sparkles, Users } from "lucide-react";
import { useParams } from "next/navigation";
import type React from "react";
import { useState } from "react";
import type { FilterPresets } from "@/contracts/types/leads.types";
import { useLeads } from "@/lib/hooks/use-leads";
import { CompanyGraphDrawer } from "./CompanyGraphDrawer";
import { LeadCard } from "./LeadCard";
import { ReverseIcpModal } from "./ReverseIcpModal";

export const LeadsContent: React.FC = () => {
	const params = useParams();
	const workspaceId = params?.workspace_id ? String(params.workspace_id) : "1";

	const [sourceFilter, setSourceFilter] = useState<string>("all");
	const [statusFilter, setStatusFilter] = useState<string>("all");
	const [searchQuery, setSearchQuery] = useState<string>("");
	const [selectedCompany, setSelectedCompany] = useState<string | null>(null);
	const [isDrawerOpen, setIsDrawerOpen] = useState<boolean>(false);
	const [isReverseIcpOpen, setIsReverseIcpOpen] = useState<boolean>(false);

	const {
		leads: apiLeads,
		loading,
		error,
		refetch,
		updateStatus,
	} = useLeads(workspaceId, {
		source: sourceFilter !== "all" ? sourceFilter : undefined,
		status: statusFilter !== "all" ? statusFilter : undefined,
		search: searchQuery || undefined,
	});

	// Server-side filtered leads from PostgreSQL API
	const displayLeads = apiLeads || [];

	const handleOpenGraph = (companyName: string) => {
		setSelectedCompany(companyName);
		setIsDrawerOpen(true);
	};

	const handleCloseDrawer = () => {
		setIsDrawerOpen(false);
		setSelectedCompany(null);
	};

	const handleApplyIcpPresets = (presets: FilterPresets) => {
		// Map LLM-returned platform names to the canonical source filter values.
		const platformMap: Record<string, string> = {
			facebook: "facebook",
			telegram: "telegram",
			batdongsan: "batdongsan",
			"batdongsan.com.vn": "batdongsan",
			topcv: "topcv",
			"topcv.vn": "topcv",
			tender: "tender",
			"mua sắm công": "tender",
		};
		if (presets.platforms && presets.platforms.length > 0) {
			const raw = presets.platforms[0].toLowerCase().trim();
			setSourceFilter(platformMap[raw] || "all");
		}
		const queryParts: string[] = [];
		if (presets.target_industries && presets.target_industries.length > 0) {
			queryParts.push(...presets.target_industries);
		}
		if (presets.locations && presets.locations.length > 0) {
			queryParts.push(...presets.locations);
		}
		if (queryParts.length > 0) {
			setSearchQuery(queryParts.join(" "));
		}
	};

	const handleCreateTableFromIcp = async (_name: string, _icon: string, presets: FilterPresets) => {
		handleApplyIcpPresets(presets);
	};

	return (
		<div className="space-y-6">
			{/* Page Header */}
			<div className="flex flex-wrap items-center justify-between gap-4 pb-4 border-b border-zinc-800">
				<div>
					<div className="flex items-center gap-2.5">
						<div className="p-2 rounded-xl bg-emerald-500/10 border border-emerald-500/20 text-emerald-400">
							<Users className="w-6 h-6" />
						</div>
						<div>
							<h1 className="text-xl font-bold text-zinc-100 flex items-center gap-2">
								<span>Lead Intelligence Panel</span>
								<span className="text-xs px-2 py-0.5 rounded-full bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 font-mono">
									Story 21.4
								</span>
							</h1>
							<p className="text-xs text-zinc-400">
								Tổng hợp Lead đa nguồn (BĐS, Tuyển dụng, Đấu thầu, Social) kèm Fit Score & Company
								Graph
							</p>
						</div>
					</div>
				</div>

				<div className="flex items-center gap-2">
					<button
						type="button"
						onClick={() => setIsReverseIcpOpen(true)}
						className="inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-lg text-xs font-semibold bg-emerald-500 hover:bg-emerald-400 text-black transition-colors shadow-sm shadow-emerald-500/20"
					>
						<Sparkles className="w-3.5 h-3.5" />
						<span>1-Click Reverse-ICP</span>
					</button>

					<button
						type="button"
						onClick={() => refetch()}
						className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium bg-zinc-800 text-zinc-300 hover:text-white hover:bg-zinc-700 transition-colors border border-zinc-700"
					>
						<RefreshCw className={`w-3.5 h-3.5 ${loading ? "animate-spin" : ""}`} />
						<span>Làm mới</span>
					</button>
				</div>
			</div>

			{/* Filter & Search Bar */}
			<div className="grid grid-cols-1 md:grid-cols-12 gap-3 p-3.5 rounded-xl bg-zinc-900/60 border border-zinc-800/80 backdrop-blur-sm">
				{/* Search Input */}
				<div className="md:col-span-6 relative">
					<Search className="w-4 h-4 text-zinc-500 absolute left-3 top-1/2 -translate-y-1/2" />
					<input
						type="text"
						value={searchQuery}
						onChange={(e) => setSearchQuery(e.target.value)}
						placeholder="Tìm theo tên công ty, số điện thoại, ngành nghề, vị trí..."
						className="w-full pl-9 pr-4 py-2 text-xs rounded-lg bg-zinc-950/70 border border-zinc-800 text-zinc-200 placeholder:text-zinc-500 focus:outline-none focus:ring-1 focus:ring-emerald-500"
					/>
				</div>

				{/* Source Filter */}
				<div className="md:col-span-3">
					<select
						value={sourceFilter}
						onChange={(e) => setSourceFilter(e.target.value)}
						className="w-full px-3 py-2 text-xs rounded-lg bg-zinc-950/70 border border-zinc-800 text-zinc-200 focus:outline-none focus:ring-1 focus:ring-emerald-500 cursor-pointer"
					>
						<option value="all">Tất cả nguồn (All Sources)</option>
						<option value="facebook">👥 Facebook Groups</option>
						<option value="telegram">✈️ Telegram Channels</option>
						<option value="batdongsan">🏠 Batdongsan.com.vn</option>
						<option value="topcv">💼 TopCV / ITviec Jobs</option>
						<option value="tender">🏛️ Mua Sắm Công (Tenders)</option>
					</select>
				</div>

				{/* Status Filter */}
				<div className="md:col-span-3">
					<select
						value={statusFilter}
						onChange={(e) => setStatusFilter(e.target.value)}
						className="w-full px-3 py-2 text-xs rounded-lg bg-zinc-950/70 border border-zinc-800 text-zinc-200 focus:outline-none focus:ring-1 focus:ring-emerald-500 cursor-pointer"
					>
						<option value="all">Tất cả trạng thái (All Status)</option>
						<option value="new">Mới (New)</option>
						<option value="open">Đang mở (Open)</option>
						<option value="contacted">Đã liên hệ (Contacted)</option>
						<option value="qualified">Tiềm năng cao (Qualified)</option>
						<option value="converted">Đã chuyển đổi (Converted)</option>
						<option value="lost">Bỏ qua (Lost)</option>
						<option value="pending">Chờ xử lý (Pending)</option>
					</select>
				</div>
			</div>

			{/* Error State */}
			{error && (
				<div className="p-4 rounded-xl bg-rose-500/10 border border-rose-500/20 text-rose-400 text-xs flex items-center justify-between">
					<span>Không thể tải danh sách Leads: {error}</span>
					<button
						type="button"
						onClick={() => refetch()}
						className="px-2.5 py-1 rounded bg-rose-500/20 hover:bg-rose-500/30 text-rose-300 transition-colors font-medium"
					>
						Thử lại
					</button>
				</div>
			)}

			{/* Leads Grid */}
			<div className="space-y-3">
				<div className="flex items-center justify-between text-xs text-zinc-400">
					<span>
						Hiển thị <strong className="text-zinc-200">{displayLeads.length}</strong> cơ hội tiềm
						năng
					</span>
					<div className="flex items-center gap-1 text-[11px] text-zinc-500">
						<Sparkles className="w-3.5 h-3.5 text-emerald-400" />
						<span>Fit Score được chấm tự động theo ICP của Workspace</span>
					</div>
				</div>

				{loading && displayLeads.length === 0 ? (
					<div className="flex flex-col items-center justify-center py-20 text-zinc-500 space-y-3 bg-zinc-900/30 rounded-xl border border-zinc-800/50">
						<div className="w-8 h-8 border-2 border-emerald-500 border-t-transparent rounded-full animate-spin" />
						<p className="text-xs">Đang tải và đồng bộ dữ liệu Leads từ PostgreSQL...</p>
					</div>
				) : displayLeads.length === 0 ? (
					<div className="text-center py-16 bg-zinc-900/30 rounded-xl border border-zinc-800/50 text-zinc-500 space-y-2">
						<p className="text-sm font-medium text-zinc-400">Chưa có Lead nào phù hợp với bộ lọc</p>
						<p className="text-xs">Thử xóa bộ lọc hoặc tìm kiếm từ khóa khác</p>
					</div>
				) : (
					<div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
						{displayLeads.map((lead) => (
							<LeadCard
								key={lead.id}
								lead={lead}
								onOpenCompanyGraph={handleOpenGraph}
								onStatusChange={updateStatus}
							/>
						))}
					</div>
				)}
			</div>

			{/* Company Graph Drawer */}
			<CompanyGraphDrawer
				workspaceId={workspaceId}
				companyName={selectedCompany}
				isOpen={isDrawerOpen}
				onClose={handleCloseDrawer}
			/>

			{/* 1-Click Reverse-ICP Modal (Story 21.10) */}
			<ReverseIcpModal
				isOpen={isReverseIcpOpen}
				onClose={() => setIsReverseIcpOpen(false)}
				workspaceId={workspaceId}
				onApplyFilterPresets={handleApplyIcpPresets}
				onCreateTableFromIcp={handleCreateTableFromIcp}
			/>
		</div>
	);
};
