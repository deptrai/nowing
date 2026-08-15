"use client";

import {
	AlertTriangle,
	Building2,
	Calendar,
	ExternalLink,
	MapPin,
	Network,
	Phone,
	Sparkles,
	Tag,
	X,
} from "lucide-react";
import type React from "react";
import { useEffect } from "react";
import type { Lead } from "@/contracts/types/leads.types";
import { isAllowedUrl } from "@/lib/utils";
import { PhoneCopyPill } from "./PhoneCopyPill";
import { ZaloOutreachButton } from "./zalo-outreach-button";

export interface LeadDetailFlyoutDrawerProps {
	lead: Lead | null;
	isOpen: boolean;
	onClose: () => void;
	workspaceId?: string | number;
	onOpenCompanyGraph?: (companyName: string) => void;
	onReportInvalidPhone?: (lead: Lead) => void;
}

export const LeadDetailFlyoutDrawer: React.FC<LeadDetailFlyoutDrawerProps> = ({
	lead,
	isOpen,
	onClose,
	workspaceId = "1",
	onOpenCompanyGraph,
	onReportInvalidPhone,
}) => {
	useEffect(() => {
		const handleKeyDown = (e: KeyboardEvent) => {
			if (e.key === "Escape" && isOpen) {
				onClose();
			}
		};
		window.addEventListener("keydown", handleKeyDown);
		return () => window.removeEventListener("keydown", handleKeyDown);
	}, [isOpen, onClose]);

	if (!isOpen || !lead) {
		return null;
	}

	const fitScore = lead.fit_score ?? 0;
	const intentScore = lead.intent_score ?? 0;
	const compositeScore = lead.composite_score ?? 0;

	return (
		<div className="fixed inset-0 z-50 overflow-hidden">
			{/* Backdrop */}
			<button
				type="button"
				aria-label="Đóng chi tiết lead"
				className="absolute inset-0 bg-black/60 backdrop-blur-xs transition-opacity cursor-pointer w-full h-full border-0 p-0"
				onClick={onClose}
			/>

			<div className="fixed inset-y-0 right-0 max-w-full flex pl-10">
				<aside
					role="dialog"
					aria-modal="true"
					aria-label="Chi tiết khách hàng tiềm năng"
					data-testid="lead-detail-flyout-drawer"
					className="w-screen max-w-[480px] bg-zinc-950 border-l border-zinc-800 shadow-2xl flex flex-col text-zinc-100 z-10 animate-in slide-in-from-right duration-200"
				>
					{/* Header */}
					<div className="px-6 py-5 border-b border-zinc-800/80 bg-zinc-900/60 soc-caro-grid flex items-start justify-between">
						<div className="space-y-1 pr-4">
							<div className="flex items-center gap-2">
								<span className="text-[10px] font-semibold uppercase tracking-wider px-2 py-0.5 rounded bg-emerald-500/15 text-emerald-400 border border-emerald-500/30">
									{lead.source}
								</span>
								{lead.status && (
									<span className="text-[10px] font-medium px-2 py-0.5 rounded bg-zinc-800 text-zinc-400 border border-zinc-700">
										{lead.status}
									</span>
								)}
							</div>
							<h3 className="text-base font-bold text-zinc-100 line-clamp-2">
								{lead.company_name}
							</h3>
						</div>
						<button
							type="button"
							onClick={onClose}
							className="p-1.5 rounded-lg text-zinc-400 hover:text-zinc-100 hover:bg-zinc-800 transition-colors cursor-pointer"
						>
							<X className="w-5 h-5" />
						</button>
					</div>

					{/* Body Content */}
					<div className="flex-1 overflow-y-auto p-6 space-y-6 scrollbar-thin">
						{/* Score Matrix */}
						<div className="p-4 rounded-xl bg-zinc-900/80 border border-zinc-800 space-y-3">
							<div className="flex items-center justify-between">
								<span className="text-xs font-semibold text-zinc-300 flex items-center gap-1.5">
									<Sparkles className="w-3.5 h-3.5 text-emerald-400" />
									Đánh giá Điểm Tiềm Năng (Fit Score)
								</span>
								<span className="font-mono text-sm font-bold text-emerald-400">
									{fitScore} / 100
								</span>
							</div>

							<div className="space-y-2 text-xs">
								<div>
									<div className="flex justify-between text-[11px] text-zinc-400 mb-1">
										<span>Khớp Chân Dung (Fit Score)</span>
										<span className="font-mono font-medium text-zinc-200">{fitScore}%</span>
									</div>
									<div className="w-full h-1.5 rounded-full bg-zinc-800 overflow-hidden">
										<div
											className="h-full bg-emerald-500 rounded-full transition-all duration-300"
											style={{ width: `${Math.min(100, Math.max(0, fitScore))}%` }}
										/>
									</div>
								</div>

								{intentScore > 0 && (
									<div>
										<div className="flex justify-between text-[11px] text-zinc-400 mb-1">
											<span>Ý Định Mua / Nhu Cầu (Intent)</span>
											<span className="font-mono font-medium text-zinc-200">{intentScore}%</span>
										</div>
										<div className="w-full h-1.5 rounded-full bg-zinc-800 overflow-hidden">
											<div
												className="h-full bg-blue-500 rounded-full transition-all duration-300"
												style={{ width: `${Math.min(100, Math.max(0, intentScore))}%` }}
											/>
										</div>
									</div>
								)}

								{compositeScore > 0 && (
									<div>
										<div className="flex justify-between text-[11px] text-zinc-400 mb-1">
											<span>Tổng Hợp (Composite)</span>
											<span className="font-mono font-medium text-zinc-200">{compositeScore}%</span>
										</div>
										<div className="w-full h-1.5 rounded-full bg-zinc-800 overflow-hidden">
											<div
												className="h-full bg-amber-500 rounded-full transition-all duration-300"
												style={{ width: `${Math.min(100, Math.max(0, compositeScore))}%` }}
											/>
										</div>
									</div>
								)}
							</div>
						</div>

						{/* Contact & Outreach Actions */}
						<div className="p-4 rounded-xl bg-zinc-900/60 border border-zinc-800/80 space-y-3">
							<h4 className="text-xs font-semibold text-zinc-300 uppercase tracking-wider">
								Thông Tin Liên Hệ & Tiếp Cận
							</h4>

							<div className="flex items-center justify-between gap-2 p-2.5 rounded-lg bg-zinc-950 border border-zinc-800">
								<div className="flex items-center gap-2">
									<Phone className="w-4 h-4 text-emerald-400 shrink-0" />
									{lead.phone ? (
										<PhoneCopyPill phone={lead.phone} />
									) : (
										<span className="text-xs text-zinc-500 font-mono">Chưa mở khóa SĐT</span>
									)}
								</div>
								{(() => {
									const cleanDigits = lead.phone?.replace(/[^0-9+]/g, "") || "";
									return cleanDigits.length >= 8 ? (
										<a
											href={`tel:${cleanDigits}`}
											className="px-2.5 py-1 text-xs font-medium rounded-md bg-zinc-800 hover:bg-zinc-700 text-zinc-200 transition-colors"
										>
											Gọi ngay
										</a>
									) : null;
								})()}
							</div>

							<div className="grid grid-cols-2 gap-2 pt-1">
								<ZaloOutreachButton
									leadId={lead.id}
									workspaceId={workspaceId}
									phone={lead.phone}
									companyName={lead.company_name}
									intent={lead.intent}
									source={lead.source}
									contentSnippet={lead.content_snippet}
									className="w-full justify-center"
								/>

								{onOpenCompanyGraph && (
									<button
										type="button"
										onClick={() => onOpenCompanyGraph(lead.company_name)}
										className="inline-flex items-center justify-center gap-1.5 px-3 py-2 text-xs font-medium rounded-lg bg-zinc-800 hover:bg-zinc-700 text-zinc-200 border border-zinc-700/60 transition-colors cursor-pointer"
									>
										<Network className="w-3.5 h-3.5 text-blue-400" />
										Company Graph
									</button>
								)}
							</div>
						</div>

						{/* Entity Metadata */}
						<div className="space-y-2 text-xs text-zinc-300">
							{lead.location && (
								<div className="flex items-start gap-2">
									<MapPin className="w-3.5 h-3.5 text-zinc-500 shrink-0 mt-0.5" />
									<span>{lead.location}</span>
								</div>
							)}
							{lead.price_estimate && (
								<div className="flex items-start gap-2">
									<Tag className="w-3.5 h-3.5 text-emerald-500 shrink-0 mt-0.5" />
									<span className="font-mono font-bold text-emerald-400">
										{lead.price_estimate}
									</span>
								</div>
							)}
							{lead.industry && (
								<div className="flex items-start gap-2">
									<Building2 className="w-3.5 h-3.5 text-zinc-500 shrink-0 mt-0.5" />
									<span>Ngành: {lead.industry}</span>
								</div>
							)}
							{lead.created_at && (
								<div className="flex items-start gap-2">
									<Calendar className="w-3.5 h-3.5 text-zinc-500 shrink-0 mt-0.5" />
									<span className="text-zinc-400 font-mono text-[11px]">
										{!Number.isNaN(new Date(lead.created_at).getTime())
											? new Date(lead.created_at).toLocaleString("vi-VN")
											: "Vừa xong"}
									</span>
								</div>
							)}
						</div>

						{/* Full Content Snippet */}
						{lead.content_snippet && (
							<div className="space-y-2">
								<h4 className="text-xs font-semibold text-zinc-300 uppercase tracking-wider">
									Nội dung bài đăng gốc
								</h4>
								<div className="p-3.5 rounded-xl bg-zinc-900/90 border border-zinc-800/80 text-xs text-zinc-300 leading-relaxed whitespace-pre-wrap font-sans">
									{lead.content_snippet}
								</div>
							</div>
						)}

						{/* Source Link & Invalid Phone Report */}
						<div className="pt-2 flex items-center justify-between text-xs text-zinc-500 border-t border-zinc-800">
							{lead.source_url && isAllowedUrl(lead.source_url) ? (
								<a
									href={lead.source_url}
									target="_blank"
									rel="noopener noreferrer"
									className="inline-flex items-center gap-1 text-zinc-400 hover:text-emerald-400 transition-colors"
								>
									<ExternalLink className="w-3.5 h-3.5" />
									Mở bài gốc
								</a>
							) : (
								<span />
							)}

							{lead.phone && onReportInvalidPhone && (
								<button
									type="button"
									onClick={() => onReportInvalidPhone(lead)}
									className="inline-flex items-center gap-1 text-rose-400/80 hover:text-rose-400 transition-colors cursor-pointer"
								>
									<AlertTriangle className="w-3.5 h-3.5" />
									Báo SĐT sai (Hoàn tiền 100%)
								</button>
							)}
						</div>
					</div>
				</aside>
			</div>
		</div>
	);
};
