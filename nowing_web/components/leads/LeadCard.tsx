"use client";

import { Building2, Clock, ExternalLink, MapPin, Sparkles } from "lucide-react";
import type React from "react";
import type { Lead } from "@/contracts/types/leads.types";
import { cn, isAllowedUrl } from "@/lib/utils";
import { PhoneCopyPill } from "./PhoneCopyPill";

export interface LeadCardProps {
	lead: Lead;
	onOpenCompanyGraph?: (companyName: string) => void;
	onStatusChange?: (leadId: string, newStatus: string) => void;
	className?: string;
}

const getFitScoreBadge = (score: number | null | undefined) => {
	const raw = score ?? 0;
	const val = Number.isFinite(raw) ? raw : 0;
	if (val >= 80) {
		return {
			label: "High Fit",
			score: val,
			colorClass: "bg-emerald-500/15 text-emerald-400 border-emerald-500/30",
			dotClass: "bg-emerald-400",
		};
	}
	if (val >= 50) {
		return {
			label: "Medium Fit",
			score: val,
			colorClass: "bg-amber-500/15 text-amber-400 border-amber-500/30",
			dotClass: "bg-amber-400",
		};
	}
	return {
		label: "Low Fit",
		score: val,
		colorClass: "bg-rose-500/15 text-rose-400 border-rose-500/30",
		dotClass: "bg-rose-400",
	};
};

const getIntentBadge = (intent: string | null | undefined) => {
	const tag = (intent || "BÁN").toUpperCase();
	if (tag.includes("BÁN")) {
		return {
			label: "🏷️ INTENT: BÁN",
			className: "bg-blue-500/10 text-blue-400 border-blue-500/30",
		};
	}
	if (tag.includes("MUA")) {
		return {
			label: "🏷️ INTENT: MUA",
			className: "bg-purple-500/10 text-purple-400 border-purple-500/30",
		};
	}
	if (tag.includes("TUYỂN") || tag.includes("JOB")) {
		return {
			label: "🏷️ INTENT: TUYỂN DỤNG",
			className: "bg-teal-500/10 text-teal-400 border-teal-500/30",
		};
	}
	if (tag.includes("THẦU") || tag.includes("TENDER")) {
		return {
			label: "🏷️ INTENT: ĐẤU THẦU",
			className: "bg-amber-500/10 text-amber-400 border-amber-500/30",
		};
	}
	return {
		label: `🏷️ INTENT: ${tag}`,
		className: "bg-indigo-500/10 text-indigo-400 border-indigo-500/30",
	};
};

const getSourceIcon = (source: string) => {
	const s = source.toLowerCase();
	if (s.includes("facebook")) return "👥 Facebook";
	if (s.includes("telegram")) return "✈️ Telegram";
	if (s.includes("bds") || s.includes("batdongsan")) return "🏠 Batdongsan";
	if (s.includes("topcv") || s.includes("itviec") || s.includes("job")) return "💼 Jobs";
	if (s.includes("tender") || s.includes("muasamcong")) return "🏛️ Đấu Thầu";
	if (s.includes("shopee") || s.includes("tiktok")) return "🛍️ E-commerce";
	if (s.includes("linkedin")) return "💼 LinkedIn";
	if (s.includes("x") || s.includes("twitter")) return "𝕏 Twitter/X";
	return `🌐 ${source}`;
};

export const LeadCard: React.FC<LeadCardProps> = ({
	lead,
	onOpenCompanyGraph,
	onStatusChange,
	className,
}) => {
	const fitBadge = getFitScoreBadge(lead.fit_score);
	const intentBadge = getIntentBadge(lead.intent);
	const sourceLabel = getSourceIcon(lead.source);

	return (
		<div
			className={cn(
				"group relative rounded-xl border border-zinc-800/80 bg-zinc-900/60 p-4 transition-all duration-200 hover:border-zinc-700/80 hover:bg-zinc-900/90 shadow-sm backdrop-blur-sm",
				className
			)}
		>
			{/* Top Bar: Source + Intent + Fit Score */}
			<div className="flex flex-wrap items-center justify-between gap-2 pb-3 border-b border-zinc-800/60">
				<div className="flex items-center gap-2">
					<span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-md text-xs font-medium bg-zinc-800 text-zinc-300 border border-zinc-700/50">
						{sourceLabel}
					</span>
					<span
						className={cn(
							"inline-flex items-center px-2.5 py-0.5 rounded-md text-xs font-semibold border",
							intentBadge.className
						)}
					>
						{intentBadge.label}
					</span>
				</div>

				<div className="flex items-center gap-2">
					{/* Fit Score Badge */}
					<div
						title={`Fit Score: ${fitBadge.score}/100`}
						className={cn(
							"inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-bold border cursor-help transition-transform hover:scale-105",
							fitBadge.colorClass
						)}
					>
						<span className={cn("w-2 h-2 rounded-full animate-pulse", fitBadge.dotClass)} />
						<span>{fitBadge.score}</span>
						<span className="text-[10px] font-medium opacity-80">{fitBadge.label}</span>
					</div>

					{/* Pipeline Status Select */}
					<select
						value={lead.status || "new"}
						onChange={(e) => onStatusChange?.(lead.id, e.target.value)}
						className="px-2 py-1 text-xs rounded-md bg-zinc-800/90 text-zinc-300 border border-zinc-700 focus:outline-none focus:ring-1 focus:ring-emerald-500 cursor-pointer"
					>
						<option value="new">Mới (New)</option>
						<option value="open">Mới mở (Open)</option>
						<option value="contacted">Đã liên hệ</option>
						<option value="qualified">Tiềm năng cao</option>
						<option value="converted">Chuyển đổi (Won)</option>
						<option value="lost">Bỏ qua (Lost)</option>
						<option value="pending">Chờ xử lý (Pending)</option>
					</select>
				</div>
			</div>

			{/* Main Content: Company Name + Snippet */}
			<div className="pt-3 pb-2 space-y-2">
				<div className="flex items-start justify-between gap-2">
					<h3 className="text-base font-semibold text-zinc-100 group-hover:text-emerald-400 transition-colors flex items-center gap-1.5">
						<Building2 className="w-4 h-4 text-zinc-400 shrink-0" />
						<span>{lead.company_name}</span>
					</h3>
					{lead.industry && (
						<span className="text-xs text-zinc-400 bg-zinc-800/60 px-2 py-0.5 rounded border border-zinc-800">
							{lead.industry}
						</span>
					)}
				</div>

				{lead.content_snippet && (
					<p className="text-xs text-zinc-300/90 line-clamp-2 leading-relaxed bg-zinc-950/40 p-2.5 rounded-lg border border-zinc-800/40">
						"{lead.content_snippet}"
					</p>
				)}
			</div>

			{/* Attributes Row: Phone, Location, Price */}
			<div className="flex flex-wrap items-center gap-3 py-2 text-xs text-zinc-400 border-t border-zinc-800/40">
				{lead.phone && <PhoneCopyPill phone={lead.phone} />}

				{lead.location && (
					<div className="inline-flex items-center gap-1">
						<MapPin className="w-3.5 h-3.5 text-zinc-500" />
						<span>{lead.location}</span>
					</div>
				)}

				{lead.price_estimate && (
					<div className="inline-flex items-center gap-1 font-medium text-amber-300/90 bg-amber-500/10 px-2 py-0.5 rounded border border-amber-500/20">
						<span>💰 {lead.price_estimate}</span>
					</div>
				)}

				{lead.created_at && (
					<div className="inline-flex items-center gap-1 text-[11px] text-zinc-500 ml-auto">
						<Clock className="w-3 h-3" />
						<span>
							{new Date(lead.created_at).toLocaleDateString("vi-VN", {
								hour: "2-digit",
								minute: "2-digit",
								day: "2-digit",
								month: "2-digit",
							})}
						</span>
					</div>
				)}
			</div>

			{/* Action Footer */}
			<div className="flex flex-wrap items-center justify-between gap-2 pt-2 mt-1 border-t border-zinc-800/60">
				<div className="flex items-center gap-2">
					<button
						type="button"
						onClick={() => onOpenCompanyGraph?.(lead.company_name)}
						className="inline-flex items-center gap-1.5 px-3 py-1 rounded-md text-xs font-medium bg-zinc-800 text-zinc-200 hover:bg-zinc-700 hover:text-white border border-zinc-700 transition-colors focus:outline-none focus:ring-1 focus:ring-zinc-400"
					>
						<Building2 className="w-3.5 h-3.5 text-emerald-400" />
						<span>Xem Company Graph</span>
					</button>

					{isAllowedUrl(lead.source_url) && (
						<a
							href={lead.source_url}
							target="_blank"
							rel="noopener noreferrer"
							className="inline-flex items-center gap-1 px-2.5 py-1 rounded-md text-xs text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800 transition-colors"
						>
							<ExternalLink className="w-3.5 h-3.5" />
							<span>Mở bài gốc</span>
						</a>
					)}
				</div>

				<div className="flex items-center gap-1.5 text-[11px] text-zinc-400">
					<Sparkles className="w-3 h-3 text-amber-400" />
					<span>Intent Score: {lead.intent_score ?? 75}/100</span>
				</div>
			</div>
		</div>
	);
};
