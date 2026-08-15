"use client";

import { Building2, ExternalLink, MapPin, Share2, Sparkles } from "lucide-react";
import type React from "react";
import type { Lead } from "@/contracts/types/leads.types";
import { cn, isAllowedUrl } from "@/lib/utils";
import { PhoneCopyPill } from "./PhoneCopyPill";
import { ZaloOutreachButton } from "./zalo-outreach-button";

export interface LeadIntelligenceTableProps {
	leads: Lead[];
	workspaceId?: number | string;
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

export const LeadIntelligenceTable: React.FC<LeadIntelligenceTableProps> = ({
	leads,
	workspaceId = "1",
	onOpenCompanyGraph,
	onStatusChange,
	className,
}) => {
	if (!leads || leads.length === 0) {
		return null;
	}

	return (
		<div className={cn("overflow-x-auto rounded-xl border border-zinc-800 bg-zinc-900/40 backdrop-blur-sm", className)}>
			<table className="w-full text-left text-xs text-zinc-300">
				<thead className="bg-zinc-950/80 text-[11px] uppercase tracking-wider text-zinc-400 border-b border-zinc-800">
					<tr>
						<th scope="col" className="px-4 py-3 font-semibold">Doanh nghiệp / Nguồn</th>
						<th scope="col" className="px-4 py-3 font-semibold">Liên hệ (SĐT)</th>
						<th scope="col" className="px-4 py-3 font-semibold">Fit & Intent</th>
						<th scope="col" className="px-4 py-3 font-semibold">Địa điểm & Giá</th>
						<th scope="col" className="px-4 py-3 font-semibold text-center">Tiếp cận Zalo</th>
						<th scope="col" className="px-4 py-3 font-semibold text-right">Hành động</th>
					</tr>
				</thead>
				<tbody className="divide-y divide-zinc-800/60">
					{leads.map((lead) => {
						const fit = getFitScoreBadge(lead.fit_score);
						return (
							<tr key={lead.id} className="hover:bg-zinc-800/30 transition-colors">
								{/* Company & Source */}
								<td className="px-4 py-3.5 space-y-1">
									<div className="flex items-center gap-1.5 font-bold text-zinc-100">
										<Building2 className="w-3.5 h-3.5 text-zinc-400 shrink-0" />
										<span className="truncate max-w-[200px]">{lead.company_name}</span>
									</div>
									<div className="flex items-center gap-1.5">
										<span className="text-[10px] px-1.5 py-0.5 rounded bg-zinc-800 text-zinc-400 border border-zinc-700">
											{lead.source}
										</span>
										{lead.industry && (
											<span className="text-[10px] text-zinc-500 truncate max-w-[120px]">
												{lead.industry}
											</span>
										)}
									</div>
								</td>

								{/* Phone */}
								<td className="px-4 py-3.5">
									{lead.phone ? (
										<PhoneCopyPill phone={lead.phone} />
									) : (
										<span className="text-zinc-500 text-[11px]">Chưa có SĐT</span>
									)}
								</td>

								{/* Fit Score & Intent */}
								<td className="px-4 py-3.5 space-y-1">
									<div className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-semibold border" style={{ borderColor: "inherit" }}>
										<span className={cn("px-1.5 py-0.5 rounded-md", fit.colorClass)}>
											{fit.score} • {fit.label}
										</span>
									</div>
									{lead.intent && (
										<div className="text-[10px] text-blue-400 font-medium">
											{lead.intent}
										</div>
									)}
								</td>

								{/* Location & Price */}
								<td className="px-4 py-3.5 space-y-1 text-xs">
									{lead.location && (
										<div className="flex items-center gap-1 text-zinc-400">
											<MapPin className="w-3 h-3 text-zinc-500 shrink-0" />
											<span className="truncate max-w-[150px]">{lead.location}</span>
										</div>
									)}
									{lead.price_estimate && (
										<div className="text-amber-400/90 text-[11px] font-medium">
											💰 {lead.price_estimate}
										</div>
									)}
								</td>

								{/* Zalo Action Button */}
								<td className="px-4 py-3.5 text-center">
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

								{/* Other Actions */}
								<td className="px-4 py-3.5 text-right space-x-1.5 whitespace-nowrap">
									<button
										type="button"
										onClick={() => onOpenCompanyGraph?.(lead.company_name)}
										className="inline-flex items-center gap-1 px-2 py-1 rounded bg-emerald-500/10 text-emerald-400 hover:bg-emerald-500/20 border border-emerald-500/20 text-[11px] transition-colors"
										title="Xem Company Graph"
									>
										<Share2 className="w-3 h-3" />
										<span>Graph</span>
									</button>

									{isAllowedUrl(lead.source_url) && (
										<a
											href={lead.source_url}
											target="_blank"
											rel="noopener noreferrer"
											className="inline-flex items-center gap-1 px-2 py-1 rounded text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800 text-[11px] transition-colors"
											title="Mở bài gốc"
										>
											<ExternalLink className="w-3 h-3" />
										</a>
									)}
								</td>
							</tr>
						);
					})}
				</tbody>
			</table>
		</div>
	);
};
