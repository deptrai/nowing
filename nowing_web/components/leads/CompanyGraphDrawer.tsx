"use client";

import {
	Bell,
	Briefcase,
	ExternalLink,
	FileText,
	Mail,
	Scale,
	Share2,
	TrendingUp,
	UserCheck,
	X,
} from "lucide-react";
import { useTranslations } from "next-intl";
import type React from "react";
import { useEffect, useState } from "react";
import { toast } from "sonner";
import type { CompanyGraph } from "@/contracts/types/leads.types";
import { leadsApiService } from "@/lib/apis/leads-api.service";
import { isAllowedUrl } from "@/lib/utils";
import { PhoneCopyPill } from "./PhoneCopyPill";

export interface CompanyGraphDrawerProps {
	workspaceId: number | string;
	companyName: string | null;
	isOpen: boolean;
	onClose: () => void;
}

export const CompanyGraphDrawer: React.FC<CompanyGraphDrawerProps> = ({
	workspaceId,
	companyName,
	isOpen,
	onClose,
}) => {
	const t = useTranslations("leads");
	const [data, setData] = useState<CompanyGraph | null>(null);
	const [loading, setLoading] = useState<boolean>(false);
	const [error, setError] = useState<string | null>(null);

	useEffect(() => {
		if (!isOpen || !companyName) {
			setData(null);
			return;
		}

		let active = true;
		setLoading(true);
		setError(null);

		leadsApiService
			.getCompanyGraph(workspaceId, companyName)
			.then((res) => {
				if (active) {
					setData(res);
					setLoading(false);
				}
			})
			.catch((err) => {
				if (active) {
					console.error("Failed to load company graph:", err);
					setError(t("graph_load_error"));
					setLoading(false);
				}
			});

		return () => {
			active = false;
		};
	}, [isOpen, companyName, workspaceId]);

	// Close on Escape key
	useEffect(() => {
		const handleKeyDown = (e: KeyboardEvent) => {
			if (e.key === "Escape" && isOpen) {
				onClose();
			}
		};
		window.addEventListener("keydown", handleKeyDown);
		return () => window.removeEventListener("keydown", handleKeyDown);
	}, [isOpen, onClose]);

	if (!isOpen) return null;

	return (
		<div className="fixed inset-0 z-50 overflow-hidden">
			{/* Backdrop */}
			<div
				className="absolute inset-0 bg-black/60 backdrop-blur-sm transition-opacity"
				onClick={onClose}
				aria-hidden="true"
			/>

			{/* Slide-over Panel */}
			<div className="fixed inset-y-0 right-0 max-w-full flex pl-10">
				<div className="w-screen max-w-2xl bg-zinc-950 border-l border-zinc-800 shadow-2xl flex flex-col overflow-y-auto">
					{/* Header */}
					<div className="sticky top-0 z-10 bg-zinc-950/90 backdrop-blur-md px-6 py-4 border-b border-zinc-800 flex items-center justify-between">
						<div className="flex items-center gap-3">
							<div className="p-2 rounded-lg bg-emerald-500/10 border border-emerald-500/20 text-emerald-400">
								<Share2 className="w-5 h-5" aria-hidden="true" />
							</div>
							<div>
								<div className="flex items-center gap-2">
									<h2 className="text-lg font-bold text-zinc-100">
										{companyName || t("graph_title_fallback")}
									</h2>
									<span className="px-2 py-0.5 rounded text-[11px] font-semibold bg-emerald-500/10 text-emerald-400 border border-emerald-500/30">
										{t("graph_badge")}
									</span>
								</div>
								<p className="text-xs text-zinc-400">{t("graph_subtitle")}</p>
							</div>
						</div>

						<button
							type="button"
							onClick={onClose}
							className="p-1.5 rounded-lg text-zinc-400 hover:text-zinc-100 hover:bg-zinc-800 transition-colors"
							aria-label={t("graph_close_panel")}
						>
							<X className="w-5 h-5" aria-hidden="true" />
						</button>
					</div>

					{/* Body */}
					<div className="p-6 space-y-6 flex-1">
						{loading && (
							<div className="flex flex-col items-center justify-center py-16 text-zinc-400 space-y-3">
								<div className="w-8 h-8 border-2 border-emerald-500 border-t-transparent rounded-full animate-spin" />
								<p className="text-sm">{t("graph_loading")}</p>
							</div>
						)}

						{error && (
							<div className="p-4 rounded-lg bg-rose-500/10 border border-rose-500/20 text-rose-400 text-sm">
								{error}
							</div>
						)}

						{!loading && data && (
							<>
								{/* 1. Legal Entity Overview */}
								{data.legal_entity && (
									<div className="rounded-xl border border-zinc-800 bg-zinc-900/50 p-4 space-y-3">
										<div className="flex items-center gap-2 text-zinc-200 font-semibold text-sm border-b border-zinc-800/80 pb-2">
											<Scale className="w-4 h-4 text-emerald-400" aria-hidden="true" />
											<span>{t("graph_legal_title")}</span>
										</div>

										<div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-xs">
											<div>
												<span className="text-zinc-500">{t("graph_tax_id")}:</span>
												<p className="font-mono text-zinc-200 font-medium">
													{data.legal_entity.tax_id || t("graph_not_updated")}
												</p>
											</div>
											<div>
												<span className="text-zinc-500">{t("graph_rep")}:</span>
												<p className="text-zinc-200 font-medium">
													{data.legal_entity.representative || t("graph_not_updated")}
												</p>
											</div>
											<div>
												<span className="text-zinc-500">{t("graph_capital")}:</span>
												<p className="text-zinc-200 font-medium">
													{data.legal_entity.charter_capital || t("graph_not_updated")}
												</p>
											</div>
											<div>
												<span className="text-zinc-500">{t("graph_founded")}:</span>
												<p className="text-zinc-200 font-medium">
													{data.legal_entity.founding_date || t("graph_not_updated")}
												</p>
											</div>
											<div className="md:col-span-2">
												<span className="text-zinc-500">{t("graph_hq")}:</span>
												<p className="text-zinc-200 font-medium">
													{data.legal_entity.headquarters || t("graph_not_updated")}
												</p>
											</div>
										</div>
									</div>
								)}

								{/* 2. Decision Makers Directory (Story 21.9) */}
								<div className="space-y-3">
									<div className="flex items-center justify-between">
										<div className="flex items-center gap-2 text-zinc-200 font-semibold text-sm">
											<UserCheck className="w-4 h-4 text-blue-400" aria-hidden="true" />
											<span>{t("graph_dm_title")}</span>
										</div>
										<span className="text-xs text-zinc-400">
											{t("graph_dm_count", { count: data.decision_makers.length })}
										</span>
									</div>

									<div className="grid grid-cols-1 md:grid-cols-2 gap-3">
										{data.decision_makers.map((dm, index) => (
											<div
												key={`dm-${index}`}
												className="rounded-xl border border-zinc-800 bg-zinc-900/60 p-3.5 space-y-2 hover:border-zinc-700 transition-colors"
											>
												<div className="flex items-start justify-between gap-2">
													<div>
														<h4 className="text-sm font-bold text-zinc-100">{dm.name}</h4>
														<p className="text-xs text-zinc-400">{dm.title}</p>
													</div>
													<span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
														{t("graph_dm_match", { pct: Math.round(dm.confidence * 100) })}
													</span>
												</div>

												<div className="flex flex-col gap-1.5 pt-1 text-xs">
													{dm.phone && <PhoneCopyPill phone={dm.phone} />}
													{dm.email && (
														<div className="flex items-center gap-1.5 text-zinc-300 font-mono text-[11px]">
															<Mail className="w-3 h-3 text-zinc-500" aria-hidden="true" />
															<span>{dm.email}</span>
														</div>
													)}
												</div>

												{isAllowedUrl(dm.linkedin_url) && (
													<a
														href={dm.linkedin_url}
														target="_blank"
														rel="noopener noreferrer"
														className="inline-flex items-center gap-1 text-xs text-blue-400 hover:text-blue-300 transition-colors pt-1"
													>
														<ExternalLink className="w-3 h-3" aria-hidden="true" />
														<span>{t("graph_linkedin")}</span>
													</a>
												)}
											</div>
										))}
									</div>
								</div>

								{/* 3. Hiring Velocity Signals (Story 12.10) */}
								<div className="rounded-xl border border-zinc-800 bg-zinc-900/50 p-4 space-y-3">
									<div className="flex items-center justify-between border-b border-zinc-800/80 pb-2">
										<div className="flex items-center gap-2 text-zinc-200 font-semibold text-sm">
											<TrendingUp className="w-4 h-4 text-emerald-400" aria-hidden="true" />
											<span>{t("graph_hiring_title")}</span>
										</div>
										{data.hiring_velocity_pct !== null &&
											data.hiring_velocity_pct !== undefined && (
												<span className="text-xs font-bold text-emerald-400 bg-emerald-500/10 px-2 py-0.5 rounded border border-emerald-500/20">
													{data.hiring_velocity_pct > 0
														? `+${data.hiring_velocity_pct}`
														: data.hiring_velocity_pct}
													% {t("graph_hiring_30d")}
												</span>
											)}
									</div>

									<p className="text-xs text-zinc-300">
										{t.rich("graph_hiring_body", {
											count: data.active_jobs_count,
											b: (c) => <span className="font-bold text-emerald-400">{c}</span>,
										})}
									</p>

									<div className="space-y-2">
										{data.hiring_signals.map((hs, index) => (
											<div
												key={`hs-${index}`}
												className="flex items-center justify-between p-2.5 rounded-lg bg-zinc-950/60 border border-zinc-800/60 text-xs"
											>
												<div className="flex items-center gap-2">
													<Briefcase className="w-3.5 h-3.5 text-zinc-400" aria-hidden="true" />
													<span className="font-medium text-zinc-200">{hs.title}</span>
													{hs.department && (
														<span className="text-zinc-500">• {hs.department}</span>
													)}
												</div>
												<span className="px-2 py-0.5 rounded bg-zinc-800 text-zinc-300 text-[10px]">
													{hs.platform}
												</span>
											</div>
										))}
									</div>
								</div>

								{/* 4. Public Procurement & Tenders (Story 16.5) */}
								{data.tenders.length > 0 && (
									<div className="rounded-xl border border-zinc-800 bg-zinc-900/50 p-4 space-y-3">
										<div className="flex items-center gap-2 text-zinc-200 font-semibold text-sm border-b border-zinc-800/80 pb-2">
											<FileText className="w-4 h-4 text-amber-400" aria-hidden="true" />
											<span>{t("graph_tenders_title")}</span>
										</div>

										<div className="space-y-2">
											{data.tenders.map((tender, index) => (
												<div
													key={`tender-${index}`}
													className="p-3 rounded-lg bg-zinc-950/60 border border-zinc-800/60 space-y-2 text-xs"
												>
													<div className="flex items-start justify-between gap-2">
														<h5 className="font-semibold text-zinc-200">{tender.title}</h5>
														<span className="shrink-0 px-2 py-0.5 rounded text-[10px] font-mono bg-amber-500/10 text-amber-300 border border-amber-500/20">
															{tender.tender_number}
														</span>
													</div>

													<div className="flex flex-wrap items-center justify-between gap-2 text-zinc-400 text-[11px]">
														<span>
															{t("graph_tender_budget")}:{" "}
															<strong className="text-emerald-400 font-mono">
																{tender.budget_vnd
																	? t("graph_tender_billion", {
																			v: (tender.budget_vnd / 1_000_000_000).toFixed(1),
																		})
																	: t("graph_tender_negotiable")}
															</strong>
														</span>

														{isAllowedUrl(tender.source_url) && (
															<a
																href={tender.source_url}
																target="_blank"
																rel="noopener noreferrer"
																className="text-blue-400 hover:underline flex items-center gap-1"
															>
																<span>{t("graph_tender_view")}</span>
																<ExternalLink className="w-3 h-3" aria-hidden="true" />
															</a>
														)}
													</div>
												</div>
											))}
										</div>
									</div>
								)}
							</>
						)}
					</div>

					{/* Footer Actions */}
					<div className="sticky bottom-0 z-10 bg-zinc-950/90 backdrop-blur-md px-6 py-4 border-t border-zinc-800 flex flex-wrap items-center justify-between gap-3">
						<button
							type="button"
							onClick={() => toast.success(t("graph_toast_email"))}
							className="inline-flex items-center gap-2 px-4 py-2 rounded-lg text-xs font-semibold bg-emerald-600 text-white hover:bg-emerald-500 transition-colors shadow-lg shadow-emerald-950/50"
						>
							<Mail className="w-4 h-4" aria-hidden="true" />
							<span>{t("graph_btn_email")}</span>
						</button>

						<div className="flex items-center gap-2">
							<button
								type="button"
								onClick={() => toast.info(t("graph_toast_watch"))}
								className="inline-flex items-center gap-1.5 px-3 py-2 rounded-lg text-xs font-medium bg-zinc-800 text-zinc-200 hover:bg-zinc-700 transition-colors border border-zinc-700"
							>
								<Bell className="w-3.5 h-3.5" aria-hidden="true" />
								<span>{t("graph_btn_watch")}</span>
							</button>

							<button
								type="button"
								onClick={onClose}
								className="px-3 py-2 rounded-lg text-xs text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800 transition-colors"
							>
								Đóng
							</button>
						</div>
					</div>
				</div>
			</div>
		</div>
	);
};
