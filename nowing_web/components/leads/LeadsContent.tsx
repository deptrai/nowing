"use client";

import {
	LayoutGrid,
	ListChecks,
	PlusCircle,
	RefreshCw,
	Search,
	ShieldAlert,
	Sparkles,
	Table2,
	Users,
} from "lucide-react";
import { useParams, useRouter, useSearchParams } from "next/navigation";
import type React from "react";
import { useCallback, useEffect, useMemo, useState } from "react";
import { toast } from "sonner";
import type { FilterPresets } from "@/contracts/types/leads.types";
import { useLeads } from "@/lib/hooks/use-leads";
import { useWorkspaceTables } from "@/lib/hooks/use-workspace-tables";
import { CampaignBuilder } from "./campaign-builder/CampaignBuilder";
import { DncManagementModal } from "./DncManagementModal";
import { LeadCard } from "./LeadCard";
import { LeadWorkbench } from "./LeadWorkbench";
import { MultiTableTabs } from "./multi-table-tabs";
import { NowingLeadMatrix } from "./NowingLeadMatrix";
import { ReverseIcpModal } from "./ReverseIcpModal";

// Map LLM-returned platform names to canonical source filter values.
const PLATFORM_MAP: Record<string, string> = {
	facebook: "facebook",
	telegram: "telegram",
	batdongsan: "batdongsan",
	"batdongsan.com.vn": "batdongsan",
	topcv: "topcv",
	"topcv.vn": "topcv",
	tender: "tender",
	"mua sắm công": "tender",
};

const resolvePlatform = (platform: string | undefined): string => {
	if (!platform) return "all";
	const raw = platform.toLowerCase().trim();
	return PLATFORM_MAP[raw] || "all";
};

const buildSearchQuery = (presets: FilterPresets): string => {
	const parts: string[] = [];
	if (presets.target_industries && presets.target_industries.length > 0) {
		parts.push(...presets.target_industries);
	}
	if (presets.locations && presets.locations.length > 0) {
		parts.push(...presets.locations);
	}
	return parts.join(" ");
};

export const LeadsContent: React.FC = () => {
	const params = useParams();
	const router = useRouter();
	const searchParams = useSearchParams();
	const workspaceId = params?.workspace_id ? String(params.workspace_id) : "1";

	const [viewMode, setViewMode] = useState<"workbench" | "builder" | "matrix" | "cards">(
		"workbench"
	);
	const [sourceFilter, setSourceFilter] = useState<string>("all");
	const [statusFilter, setStatusFilter] = useState<string>("all");
	const [searchQuery, setSearchQuery] = useState<string>("");
	const [_selectedCompany, setSelectedCompany] = useState<string | null>(null);
	const [_isDrawerOpen, setIsDrawerOpen] = useState<boolean>(false);
	const [isReverseIcpOpen, setIsReverseIcpOpen] = useState<boolean>(false);
	const [isDncModalOpen, setIsDncModalOpen] = useState<boolean>(false);
	const [activeTableId, setActiveTableId] = useState<string | null>(searchParams.get("table"));

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

	const {
		tables,
		createTable,
		updateTable,
		deleteTable,
		refetch: refetchTables,
	} = useWorkspaceTables(workspaceId);

	const currentFilterPreset = useMemo(
		() => ({
			source: sourceFilter !== "all" ? sourceFilter : undefined,
			status: statusFilter !== "all" ? statusFilter : undefined,
			search: searchQuery || undefined,
		}),
		[sourceFilter, statusFilter, searchQuery]
	);

	const applyFilterPreset = useCallback((preset: Record<string, unknown> | undefined) => {
		const p = preset || {};
		setSourceFilter(typeof p.source === "string" ? p.source : "all");
		setStatusFilter(typeof p.status === "string" ? p.status : "all");
		setSearchQuery(typeof p.search === "string" ? p.search : "");
	}, []);

	const syncUrlToTable = (tableId: string | null) => {
		if (tableId) {
			router.replace(`/dashboard/${workspaceId}/leads?table=${tableId}`, { scroll: false });
		} else {
			router.replace(`/dashboard/${workspaceId}/leads`, { scroll: false });
		}
	};

	const handleSelectTable = (tableId: string | null) => {
		setActiveTableId(tableId);
		if (tableId) {
			const table = tables.find((t) => t.id === tableId);
			if (table) {
				applyFilterPreset(table.filter_preset);
			} else {
				toast.error("Không tìm thấy bảng đã chọn");
			}
		} else {
			applyFilterPreset({});
		}
		syncUrlToTable(tableId);
	};

	const handleCreateTable = async (name: string, icon: string) => {
		const created = await createTable({
			name,
			icon,
			filter_preset: currentFilterPreset,
		});
		if (created) {
			setActiveTableId(created.id);
			syncUrlToTable(created.id);
			toast.success(`Đã tạo bảng "${created.name}"`);
		}
	};

	const handleUpdateTable = async (tableId: string, name: string) => {
		const updated = await updateTable(tableId, { name });
		if (updated) {
			toast.success("Đã cập nhật tên bảng");
		}
	};

	const handleDeleteTable = async (tableId: string) => {
		const ok = await deleteTable(tableId);
		if (ok) {
			if (activeTableId === tableId) {
				handleSelectTable(null);
			}
			toast.success("Đã xóa bảng");
		}
	};

	// Apply table filter when navigating directly with ?table={id}
	useEffect(() => {
		if (activeTableId && tables.length > 0) {
			const table = tables.find((t) => t.id === activeTableId);
			if (table) {
				applyFilterPreset(table.filter_preset);
			}
		}
	}, [activeTableId, tables, applyFilterPreset]);

	const handleOpenGraph = (companyName: string) => {
		setSelectedCompany(companyName);
		setIsDrawerOpen(true);
	};

	const _handleCloseDrawer = () => {
		setIsDrawerOpen(false);
		setSelectedCompany(null);
	};

	const handleApplyIcpPresets = (presets: FilterPresets) => {
		const mappedSource = resolvePlatform(presets.platforms?.[0]);
		setSourceFilter(mappedSource);
		setSearchQuery(buildSearchQuery(presets));
	};

	const handleCreateTableFromIcp = async (name: string, icon: string, presets: FilterPresets) => {
		handleApplyIcpPresets(presets);
		const icpFilterPreset = {
			source:
				resolvePlatform(presets.platforms?.[0]) !== "all"
					? resolvePlatform(presets.platforms?.[0])
					: undefined,
			search: buildSearchQuery(presets) || undefined,
		};
		const created = await createTable({
			name,
			icon,
			filter_preset: icpFilterPreset,
		});
		if (created) {
			setActiveTableId(created.id);
			syncUrlToTable(created.id);
			toast.success(`Đã tạo tab bảng "${created.name}" từ ICP`);
		} else {
			toast.error("Tạo tab bảng thất bại");
		}
	};

	return (
		<div className="space-y-6">
			{/* Page Header */}
			<div className="flex flex-wrap items-center justify-between gap-4 pb-4 border-b border-zinc-800">
				<div>
					<div className="flex items-center gap-2.5">
						<div className="p-2 rounded-xl bg-emerald-500/10 border border-emerald-500/20 text-emerald-400">
							<Users className="w-6 h-6" aria-hidden="true" />
						</div>
						<div>
							<h1 className="text-xl font-bold text-zinc-100 flex items-center gap-2">
								<span>Lead Intelligence Panel</span>
								<span className="text-xs px-2 py-0.5 rounded-full bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 font-mono">
									Story 21.15
								</span>
							</h1>
							<p className="text-xs text-zinc-400">
								SDR Lead Workbench, Campaign Builder 3-bước, Matrix Bảng tính & Tích hợp 1-Click
								Reverse-ICP
							</p>
						</div>
					</div>
				</div>

				<div className="flex items-center gap-2">
					{/* View Mode Switcher */}
					<div className="flex items-center bg-zinc-900 border border-zinc-800 p-1 rounded-lg">
						<button
							type="button"
							onClick={() => setViewMode("workbench")}
							className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium transition-colors ${
								viewMode === "workbench"
									? "bg-emerald-500/20 text-emerald-300 border border-emerald-500/30"
									: "text-zinc-400 hover:text-zinc-200"
							}`}
						>
							<ListChecks className="w-3.5 h-3.5" />
							<span>Lead Workbench</span>
						</button>

						<button
							type="button"
							onClick={() => setViewMode("builder")}
							className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium transition-colors ${
								viewMode === "builder"
									? "bg-emerald-500/20 text-emerald-300 border border-emerald-500/30"
									: "text-zinc-400 hover:text-zinc-200"
							}`}
						>
							<PlusCircle className="w-3.5 h-3.5" />
							<span>Campaign Builder</span>
						</button>

						<button
							type="button"
							onClick={() => setViewMode("matrix")}
							className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium transition-colors ${
								viewMode === "matrix"
									? "bg-emerald-500/20 text-emerald-300 border border-emerald-500/30"
									: "text-zinc-400 hover:text-zinc-200"
							}`}
						>
							<Table2 className="w-3.5 h-3.5" />
							<span>Matrix</span>
						</button>

						<button
							type="button"
							onClick={() => setViewMode("cards")}
							className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium transition-colors ${
								viewMode === "cards"
									? "bg-emerald-500/20 text-emerald-300 border border-emerald-500/30"
									: "text-zinc-400 hover:text-zinc-200"
							}`}
						>
							<LayoutGrid className="w-3.5 h-3.5" />
							<span>Cards</span>
						</button>
					</div>

					<button
						type="button"
						onClick={() => setIsReverseIcpOpen(true)}
						className="inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-lg text-xs font-semibold bg-emerald-500 hover:bg-emerald-400 text-black transition-colors shadow-sm shadow-emerald-500/20"
					>
						<Sparkles className="w-3.5 h-3.5" aria-hidden="true" />
						<span>Reverse-ICP</span>
					</button>

					<button
						type="button"
						onClick={() => setIsDncModalOpen(true)}
						className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold bg-red-950/40 text-red-400 hover:bg-red-900/50 hover:text-red-300 border border-red-800/50 transition-colors shadow-sm"
					>
						<ShieldAlert className="w-3.5 h-3.5" aria-hidden="true" />
						<span>DNC</span>
					</button>

					<button
						type="button"
						onClick={() => {
							refetch();
							refetchTables();
						}}
						className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium bg-zinc-800 text-zinc-300 hover:text-white hover:bg-zinc-700 transition-colors border border-zinc-700"
					>
						<RefreshCw className={`w-3.5 h-3.5 ${loading ? "animate-spin" : ""}`} />
						<span>Làm mới</span>
					</button>
				</div>
			</div>

			{/* Dynamic View Mode Content */}
			{viewMode === "builder" ? (
				<CampaignBuilder
					workspaceId={workspaceId}
					onCampaignCreated={() => {
						setViewMode("workbench");
						refetch();
					}}
					onCancel={() => setViewMode("workbench")}
				/>
			) : viewMode === "workbench" ? (
				<LeadWorkbench
					workspaceId={workspaceId}
					initialLeads={displayLeads}
					onOpenCompanyGraph={handleOpenGraph}
				/>
			) : viewMode === "matrix" ? (
				<NowingLeadMatrix
					leads={displayLeads}
					isLoading={loading}
					workspaceId={workspaceId}
					sourceFilter={sourceFilter}
					onSourceFilterChange={setSourceFilter}
					statusFilter={statusFilter}
					onStatusFilterChange={setStatusFilter}
					searchQuery={searchQuery}
					onSearchQueryChange={setSearchQuery}
					onRefresh={() => {
						refetch();
						refetchTables();
					}}
					onOpenReverseIcp={() => setIsReverseIcpOpen(true)}
					onOpenDnc={() => setIsDncModalOpen(true)}
					onOpenCompanyGraph={handleOpenGraph}
				/>
			) : (
				<>
					{/* Multi-Table Tabs */}
					<MultiTableTabs
						tables={tables}
						activeTableId={activeTableId}
						onSelectTable={handleSelectTable}
						onCreateTable={handleCreateTable}
						onUpdateTable={handleUpdateTable}
						onDeleteTable={handleDeleteTable}
					/>

					{/* Filter & Search Bar */}
					<div className="grid grid-cols-1 md:grid-cols-12 gap-3 p-3.5 rounded-xl bg-zinc-900/60 border border-zinc-800/80 backdrop-blur-sm">
						{/* Search Input */}
						<div className="md:col-span-6 relative">
							<Search
								className="w-4 h-4 text-zinc-500 absolute left-3 top-1/2 -translate-y-1/2"
								aria-hidden="true"
							/>
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
								Hiển thị <strong className="text-zinc-200">{displayLeads.length}</strong> cơ hội
								tiềm năng
							</span>
							<div className="flex items-center gap-1 text-[11px] text-zinc-500">
								<Sparkles className="w-3.5 h-3.5 text-emerald-400" aria-hidden="true" />
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
								<p className="text-sm font-medium text-zinc-400">
									Chưa có Lead nào phù hợp với bộ lọc
								</p>
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
				</>
			)}

			{/* 1-Click Reverse-ICP Modal (Story 21.10) */}
			<ReverseIcpModal
				isOpen={isReverseIcpOpen}
				onClose={() => setIsReverseIcpOpen(false)}
				workspaceId={workspaceId}
				onApplyFilterPresets={handleApplyIcpPresets}
				onCreateTableFromIcp={handleCreateTableFromIcp}
			/>

			{/* Do-Not-Call (DNC) Compliance Modal (Story 21.14) */}
			<DncManagementModal
				isOpen={isDncModalOpen}
				onClose={() => setIsDncModalOpen(false)}
				workspaceId={workspaceId}
			/>
		</div>
	);
};
