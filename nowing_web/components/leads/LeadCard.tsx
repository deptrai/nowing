"use client";

import { Building2, Clock, ExternalLink, MapPin, Share2, Sparkles } from "lucide-react";
import type React from "react";
import { useEffect, useState } from "react";
import type { Lead } from "@/contracts/types/leads.types";
import { cn, isAllowedUrl } from "@/lib/utils";
import { PhoneCopyPill } from "./PhoneCopyPill";
import { ZaloOutreachButton } from "./zalo-outreach-button";

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
			className: "bg-emerald-500/10 text-emerald-400 border-emerald-500/30",
		};
	}
	if (tag.includes("TUYỂN") || tag.includes("RECRUIT") || tag.includes("JOB")) {
		return {
			label: "🏷️ INTENT: TUYỂN DỤNG",
			className: "bg-amber-500/10 text-amber-400 border-amber-500/30",
		};
	}
	if (tag.includes("THẦU") || tag.includes("TENDER")) {
		return {
			label: "🏷️ INTENT: ĐẤU THẦU",
			className: "bg-purple-500/10 text-purple-400 border-purple-500/30",
		};
	}
	return {
		label: `🏷️ INTENT: ${tag}`,
		className: "bg-indigo-500/10 text-indigo-400 border-indigo-500/30",
	};
};

const getSourceIcon = (source: string) => {
	const s = (source || "").toLowerCase();
	if (s.includes("facebook")) return "👥 Facebook";
	if (s.includes("telegram")) return "✈️ Telegram";
	if (s.includes("bds") || s.includes("batdongsan")) return "🏠 Batdongsan";
	if (s.includes("topcv") || s.includes("itviec") || s.includes("job")) return "💼 Jobs";
	if (s.includes("tender") || s.includes("muasamcong")) return "🏛️ Đấu Thầu";
	if (s.includes("shopee") || s.includes("tiktok")) return "🛍️ E-commerce";
	if (s.includes("linkedin")) return "💼 LinkedIn";
	if (s.includes("x") || s.includes("twitter")) return "𝕏 Twitter/X";
	return `🌐 ${source || "Nguồn khác"}`;
};

export const LeadCard: React.FC<LeadCardProps> = ({
	lead,
	onOpenCompanyGraph,
	onStatusChange,
	className,
}) => {
	const [isPulsing, setIsPulsing] = useState(false);

	useEffect(() => {
		const handleActionDispatched = (e: Event) => {
			const customEvent = e as CustomEvent<{
				action_type?: string;
				payload?: Record<string, unknown>;
			}>;
			if (
				customEvent.detail?.action_type === "decode_phones" ||
				customEvent.detail?.action_type === "export_csv"
			) {
				setIsPulsing(true);
				const timer = setTimeout(() => setIsPulsing(false), 1200);
				return () => clearTimeout(timer);
			}
		};

		window.addEventListener("nowing:action-dispatched", handleActionDispatched);
		return () => window.removeEventListener("nowing:action-dispatched", handleActionDispatched);
	}, []);

	const fitBadge = getFitScoreBadge(lead.fit_score);
	const intentBadge = getIntentBadge(lead.intent);
	const sourceLabel = getSourceIcon(lead.source);

	return (
		<div
			className={cn(
				"rounded-xl border border-zinc-800 bg-zinc-900/50 p-4 space-y-3 hover:border-zinc-700/80 transition-all duration-200 shadow-sm backdrop-blur-sm",
				isPulsing && "cell-pulse",
				className
			)}
		>
			{/* Header: Badges & Status */}
			<div className="flex flex-wrap items-center justify-between gap-2">
				<div className="flex flex-wrap items-center gap-1.5">
					<span className="text-xs font-semibold px-2 py-0.5 rounded-md bg-zinc-800 text-zinc-300 border border-zinc-700">
						{sourceLabel}
					</span>

					{intentBadge && (
						<span
							className={cn(
								"text-xs font-semibold px-2 py-0.5 rounded-md border",
								intentBadge.className
							)}
						>
							{intentBadge.label}
						</span>
					)}
				</div>

				<div className="flex items-center gap-2">
					{fitBadge && (
						<div
							className={cn(
								"inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-medium border cursor-help",
								fitBadge.colorClass
							)}
							title={`Fit Score: ${fitBadge.score}/100`}
						>
							<span className={cn("w-1.5 h-1.5 rounded-full", fitBadge.dotClass)} />
							<span className="font-bold">{fitBadge.score}</span>
							<span>{fitBadge.label}</span>
						</div>
					)}

					<select
						value={lead.status || "new"}
						onChange={(e) => onStatusChange?.(lead.id, e.target.value)}
						className="px-2 py-0.5 text-xs rounded-md bg-zinc-950/70 border border-zinc-700 text-zinc-300 focus:outline-none focus:ring-1 focus:ring-emerald-500 cursor-pointer"
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

			{/* Company & Industry */}
			<div>
				<div className="flex items-start justify-between gap-2">
					<h3 className="text-base font-bold text-zinc-100 flex items-center gap-1.5">
						<Building2 className="w-4 h-4 text-zinc-400 shrink-0" />
						<span>{lead.company_name}</span>
					</h3>
					{lead.industry && (
						<span className="text-[11px] px-2 py-0.5 rounded bg-zinc-800/80 text-zinc-400 shrink-0">
							{lead.industry}
						</span>
					)}
				</div>

				{lead.content_snippet && (
					<p className="text-xs text-zinc-400 mt-1.5 line-clamp-2 italic bg-zinc-950/40 p-2 rounded-md border border-zinc-800/40">
						"{lead.content_snippet}"
					</p>
				)}
			</div>

			{/* Contact & Location Attributes */}
			<div className="flex flex-wrap items-center gap-3 pt-1 text-xs">
				{lead.phone && <PhoneCopyPill phone={lead.phone} />}

				{lead.location && (
					<div className="flex items-center gap-1 text-zinc-400">
						<MapPin className="w-3.5 h-3.5 text-zinc-500 shrink-0" />
						<span className="truncate max-w-[200px]">{lead.location}</span>
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
						<span suppressHydrationWarning>
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
					<ZaloOutreachButton
						leadId={lead.id}
						workspaceId={lead.workspace_id}
						phone={lead.phone}
						companyName={lead.company_name}
						intent={lead.intent}
						source={lead.source}
						contentSnippet={lead.content_snippet}
					/>

					<button
						type="button"
						onClick={() => onOpenCompanyGraph?.(lead.company_name)}
						className="inline-flex items-center gap-1.5 px-3 py-1 rounded-md text-xs font-semibold bg-emerald-500/10 text-emerald-400 hover:bg-emerald-500/20 border border-emerald-500/20 transition-colors"
					>
						<Share2 className="w-3.5 h-3.5" />
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
					<span>
						Intent Score: {lead.intent_score != null ? `${lead.intent_score}/100` : "Chưa chấm"}
					</span>
				</div>
			</div>
		</div>
	);
};
