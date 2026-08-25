"use client";

import { CheckCircle, Flame, MessageCircle, Phone, Sparkles, Target, Zap } from "lucide-react";
import { useTranslations } from "next-intl";
import type React from "react";
import { useState } from "react";
import { cn } from "@/lib/utils";

export const ProductShowcaseTabs: React.FC = () => {
	const t = useTranslations("landing.showcase");
	const [activeTab, setActiveTab] = useState<"leads" | "enrich" | "viral">("leads");

	return (
		<section className="py-16 md:py-24 bg-slate-50/60 dark:bg-slate-900/40 border-y border-slate-200/80 dark:border-slate-800">
			<div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8">
				{/* Section Header */}
				<div className="text-center max-w-3xl mx-auto mb-12">
					<div className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-emerald-100/70 dark:bg-emerald-950/70 text-emerald-800 dark:text-emerald-300 text-xs font-bold uppercase tracking-wider mb-3">
						<Sparkles className="w-3.5 h-3.5" aria-hidden="true" />
						<span>{t("badge")}</span>
					</div>
					<h2 className="text-3xl sm:text-4xl font-serif text-slate-900 dark:text-white tracking-tight">
						{t("title")}
					</h2>
					<p className="mt-3 text-base text-slate-600 dark:text-slate-400">{t("subtitle")}</p>
				</div>

				{/* Tab Nav Buttons */}
				<div className="flex justify-center mb-8">
					<div className="inline-flex p-1.5 rounded-2xl bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 shadow-sm">
						<button
							type="button"
							onClick={() => setActiveTab("leads")}
							className={cn(
								"flex items-center gap-2 px-5 py-2.5 rounded-xl text-xs sm:text-sm font-semibold transition-all",
								activeTab === "leads"
									? "bg-emerald-600 text-white shadow-sm"
									: "text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white"
							)}
						>
							<Target className="w-4 h-4" aria-hidden="true" />
							<span>{t("tab_leads")}</span>
						</button>

						<button
							type="button"
							onClick={() => setActiveTab("enrich")}
							className={cn(
								"flex items-center gap-2 px-5 py-2.5 rounded-xl text-xs sm:text-sm font-semibold transition-all",
								activeTab === "enrich"
									? "bg-emerald-600 text-white shadow-sm"
									: "text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white"
							)}
						>
							<Zap className="w-4 h-4" aria-hidden="true" />
							<span>{t("tab_enrich")}</span>
						</button>

						<button
							type="button"
							onClick={() => setActiveTab("viral")}
							className={cn(
								"flex items-center gap-2 px-5 py-2.5 rounded-xl text-xs sm:text-sm font-semibold transition-all",
								activeTab === "viral"
									? "bg-emerald-600 text-white shadow-sm"
									: "text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white"
							)}
						>
							<Flame className="w-4 h-4" aria-hidden="true" />
							<span>{t("tab_viral")}</span>
						</button>
					</div>
				</div>

				{/* Tab 1 Content: Live Table Matrix Preview */}
				{activeTab === "leads" && (
					<div className="bg-white dark:bg-slate-950 border border-slate-200 dark:border-slate-800 rounded-2xl shadow-xl overflow-hidden animate-in fade-in-50 duration-200">
						{/* Table Header Bar */}
						<div className="px-5 py-3.5 bg-slate-50 dark:bg-slate-900 border-b border-slate-200 dark:border-slate-800 flex flex-wrap items-center justify-between gap-3 text-xs">
							<div className="flex items-center gap-2">
								<span className="flex h-2.5 w-2.5 rounded-full bg-emerald-500 animate-pulse" />
								<span className="font-bold text-slate-800 dark:text-slate-200">
									{t("table_title")}
								</span>
								<span className="px-2 py-0.5 rounded bg-emerald-100 dark:bg-emerald-950 text-emerald-800 dark:text-emerald-300 font-semibold text-[11px]">
									{t("sync_status")}
								</span>
							</div>

							<div className="flex items-center gap-2">
								<span className="text-slate-400">{t("filtered_status")}</span>
							</div>
						</div>

						{/* Table Content */}
						<div className="overflow-x-auto">
							<table className="w-full text-left text-xs sm:text-sm border-collapse">
								<thead>
									<tr className="border-b border-slate-200 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-900/50 text-slate-500 dark:text-slate-400">
										<th className="py-3 px-4 font-semibold">{t("col_name")}</th>
										<th className="py-3 px-4 font-semibold">{t("col_source")}</th>
										<th className="py-3 px-4 font-semibold">{t("col_phone")}</th>
										<th className="py-3 px-4 font-semibold">Fit Score</th>
										<th className="py-3 px-4 font-semibold text-right">{t("col_action")}</th>
									</tr>
								</thead>
								<tbody className="divide-y divide-slate-100 dark:divide-slate-800/80">
									<tr className="hover:bg-emerald-50/30 dark:hover:bg-emerald-950/20 transition-colors">
										<td className="py-3.5 px-4">
											<div className="font-semibold text-slate-900 dark:text-white">
												Nguyễn Văn Hùng (Real Estate Broker)
											</div>
											<div className="text-xs text-slate-500">
												Dang Van Bi Streetfront, Thu Duc City ($350k)
											</div>
										</td>
										<td className="py-3.5 px-4">
											<span className="px-2 py-0.5 rounded bg-blue-50 text-blue-700 dark:bg-blue-950 dark:text-blue-300 text-xs font-medium border border-blue-200/50">
												Batdongsan.com.vn
											</span>
										</td>
										<td className="py-3.5 px-4">
											<span className="font-mono font-bold text-emerald-700 dark:text-emerald-400 bg-emerald-50 dark:bg-emerald-950/60 px-2 py-1 rounded border border-emerald-200/60">
												0908 123 456
											</span>
										</td>
										<td className="py-3.5 px-4">
											<div className="inline-flex items-center gap-1 font-semibold text-emerald-600">
												<span>96%</span>
												<span className="text-[10px] px-1.5 py-0.5 rounded bg-emerald-100 text-emerald-800 font-bold">
													Fit
												</span>
											</div>
										</td>
										<td className="py-3.5 px-4 text-right">
											<button
												type="button"
												className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-semibold shadow-xs transition-transform active:scale-95"
											>
												<MessageCircle className="w-3.5 h-3.5" aria-hidden="true" />
												<span>Zalo Message</span>
											</button>
										</td>
									</tr>

									<tr className="hover:bg-emerald-50/30 dark:hover:bg-emerald-950/20 transition-colors">
										<td className="py-3.5 px-4">
											<div className="font-semibold text-slate-900 dark:text-white">
												Trần Thị Thu Mai (Direct Property Owner)
											</div>
											<div className="text-xs text-slate-500">Vo Van Ngan Alley House, Thu Duc</div>
										</td>
										<td className="py-3.5 px-4">
											<span className="px-2 py-0.5 rounded bg-orange-50 text-orange-700 dark:bg-orange-950 dark:text-orange-300 text-xs font-medium border border-orange-200/50">
												Cho Tot Nha
											</span>
										</td>
										<td className="py-3.5 px-4">
											<span className="font-mono font-bold text-emerald-700 dark:text-emerald-400 bg-emerald-50 dark:bg-emerald-950/60 px-2 py-1 rounded border border-emerald-200/60">
												0982 456 789
											</span>
										</td>
										<td className="py-3.5 px-4">
											<div className="inline-flex items-center gap-1 font-semibold text-emerald-600">
												<span>92%</span>
												<span className="text-[10px] px-1.5 py-0.5 rounded bg-emerald-100 text-emerald-800 font-bold">
													Fit
												</span>
											</div>
										</td>
										<td className="py-3.5 px-4 text-right">
											<button
												type="button"
												className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-semibold shadow-xs transition-transform active:scale-95"
											>
												<MessageCircle className="w-3.5 h-3.5" aria-hidden="true" />
												<span>Zalo Message</span>
											</button>
										</td>
									</tr>

									<tr className="hover:bg-emerald-50/30 dark:hover:bg-emerald-950/20 transition-colors">
										<td className="py-3.5 px-4">
											<div className="font-semibold text-slate-900 dark:text-white">
												Lê Hoàng Nam (Founder & CTO - Software Enterprise)
											</div>
											<div className="text-xs text-slate-500">
												Hiring 5 Senior Node.js & React Engineers
											</div>
										</td>
										<td className="py-3.5 px-4">
											<span className="px-2 py-0.5 rounded bg-emerald-50 text-emerald-700 dark:bg-emerald-950 dark:text-emerald-300 text-xs font-medium border border-emerald-200/50">
												TopCV & Masothue
											</span>
										</td>
										<td className="py-3.5 px-4">
											<span className="font-mono font-bold text-emerald-700 dark:text-emerald-400 bg-emerald-50 dark:bg-emerald-950/60 px-2 py-1 rounded border border-emerald-200/60">
												0912 888 999
											</span>
										</td>
										<td className="py-3.5 px-4">
											<div className="inline-flex items-center gap-1 font-semibold text-emerald-600">
												<span>95%</span>
												<span className="text-[10px] px-1.5 py-0.5 rounded bg-emerald-100 text-emerald-800 font-bold">
													Fit
												</span>
											</div>
										</td>
										<td className="py-3.5 px-4 text-right">
											<button
												type="button"
												className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-slate-900 hover:bg-slate-800 text-white text-xs font-semibold shadow-xs transition-transform active:scale-95"
											>
												<Phone className="w-3.5 h-3.5" aria-hidden="true" />
												<span>Call Lead</span>
											</button>
										</td>
									</tr>
								</tbody>
							</table>
						</div>
					</div>
				)}

				{/* Tab 2 Content: 3-Tier Waterfall Engine */}
				{activeTab === "enrich" && (
					<div className="bg-white dark:bg-slate-950 border border-slate-200 dark:border-slate-800 rounded-2xl p-6 sm:p-8 shadow-xl animate-in fade-in-50 duration-200">
						<div className="mb-4">
							<h3 className="font-bold text-slate-900 dark:text-white text-lg mb-1">
								{t("enrich_card_title")}
							</h3>
							<p className="text-xs sm:text-sm text-slate-500 leading-relaxed">
								{t("enrich_card_desc")}
							</p>
						</div>
						<div className="grid grid-cols-1 md:grid-cols-3 gap-6">
							<div className="p-5 rounded-xl bg-slate-50 dark:bg-slate-900 border border-slate-200 dark:border-slate-800">
								<div className="w-8 h-8 rounded-lg bg-emerald-100 text-emerald-700 font-bold flex items-center justify-center mb-3">
									1
								</div>
								<h4 className="font-bold text-slate-900 dark:text-white text-base mb-1">
									Tier 1: Token Pool Rotation
								</h4>
								<p className="text-xs text-slate-500 leading-relaxed">
									Redis Mutex token pool rotating decryption across Batdongsan and Muaban listings.
								</p>
							</div>

							<div className="p-5 rounded-xl bg-slate-50 dark:bg-slate-900 border border-slate-200 dark:border-slate-800">
								<div className="w-8 h-8 rounded-lg bg-teal-100 text-teal-700 font-bold flex items-center justify-center mb-3">
									2
								</div>
								<h4 className="font-bold text-slate-900 dark:text-white text-base mb-1">
									Tier 2: Mobile Gateway API
								</h4>
								<p className="text-xs text-slate-500 leading-relaxed">
									Emulated device UUID gateway resolution extracting full poster mobile contacts.
								</p>
							</div>

							<div className="p-5 rounded-xl bg-slate-50 dark:bg-slate-900 border border-slate-200 dark:border-slate-800">
								<div className="w-8 h-8 rounded-lg bg-blue-100 text-blue-700 font-bold flex items-center justify-center mb-3">
									3
								</div>
								<h4 className="font-bold text-slate-900 dark:text-white text-base mb-1">
									Tier 3: Zalo OA & Carrier Verification
								</h4>
								<p className="text-xs text-slate-500 leading-relaxed">
									Validating telecom network active status and Zalo UID active endpoints with 99.2%
									accuracy.
								</p>
							</div>
						</div>
					</div>
				)}

				{/* Tab 3 Content: Viral Social Outbound Co-pilot */}
				{activeTab === "viral" && (
					<div className="bg-white dark:bg-slate-950 border border-slate-200 dark:border-slate-800 rounded-2xl p-6 sm:p-8 shadow-xl animate-in fade-in-50 duration-200">
						<div className="grid grid-cols-1 md:grid-cols-2 gap-6 items-center">
							<div>
								<span className="px-2.5 py-1 rounded bg-amber-100 text-amber-800 font-semibold text-xs mb-2 inline-block">
									Outlier Viral Signal Detection (5x Avg Engagement)
								</span>
								<h3 className="text-xl font-bold text-slate-900 dark:text-white mb-2">
									{t("viral_card_title")}
								</h3>
								<p className="text-xs sm:text-sm text-slate-600 dark:text-slate-400 mb-4 leading-relaxed">
									{t("viral_card_desc")}
								</p>
								<div className="space-y-2 text-xs text-slate-700 dark:text-slate-300">
									<div className="flex items-center gap-2">
										<CheckCircle className="w-4 h-4 text-emerald-500" aria-hidden="true" />
										<span>Hook classification: Contrast, Story, Value List</span>
									</div>
									<div className="flex items-center gap-2">
										<CheckCircle className="w-4 h-4 text-emerald-500" aria-hidden="true" />
										<span>Human-in-the-loop verification & custom approval</span>
									</div>
								</div>
							</div>

							<div className="p-4 rounded-xl bg-slate-900 text-slate-100 font-mono text-xs border border-slate-800">
								<div className="text-emerald-400 font-bold mb-2">
									✨ AI Generated Hook (Voice: B2B Real Estate Specialist)
								</div>
								<div className="text-slate-300 leading-relaxed">
									&quot;Why top investors are shifting capital to Thu Duc before the metro line
									connects — 3 data-backed reasons you should know...&quot;
								</div>
							</div>
						</div>
					</div>
				)}
			</div>
		</section>
	);
};
