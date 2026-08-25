"use client";

import { Check } from "lucide-react";
import Link from "next/link";
import { useTranslations } from "next-intl";
import type React from "react";

export const NowingPricingSection: React.FC = () => {
	const t = useTranslations("landing.pricing_section");

	return (
		<section
			className="py-16 md:py-24 bg-slate-50/70 dark:bg-slate-900/40 border-t border-slate-200/80 dark:border-slate-800"
			id="pricing"
		>
			<div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8">
				<div className="text-center max-w-3xl mx-auto mb-14">
					<span className="px-3 py-1 rounded-full bg-emerald-100 dark:bg-emerald-950 text-emerald-800 dark:text-emerald-300 font-bold text-xs uppercase tracking-wider">
						{t("badge")}
					</span>
					<h2 className="mt-3 text-3xl sm:text-4xl font-serif text-slate-900 dark:text-white tracking-tight">
						{t("title")}
					</h2>
					<p className="mt-3 text-base text-slate-600 dark:text-slate-400">{t("subtitle")}</p>
				</div>

				<div className="grid grid-cols-1 md:grid-cols-3 gap-8">
					{/* Plan 1: Free $0 */}
					<div className="p-6 sm:p-8 rounded-2xl bg-white dark:bg-slate-950 border border-slate-200 dark:border-slate-800 shadow-sm flex flex-col justify-between">
						<div>
							<span className="text-xs font-bold uppercase tracking-wider text-slate-500">
								{t("chat_free_title")}
							</span>
							<h3 className="text-xl font-bold text-slate-900 dark:text-white mt-1">
								AI Co-pilot Core
							</h3>
							<div className="mt-4 mb-6">
								<span className="text-4xl font-extrabold text-slate-900 dark:text-white font-mono">
									$0
								</span>
								<span className="text-slate-400 text-xs ml-1">/ lifetime</span>
							</div>

							<p className="text-xs sm:text-sm text-slate-600 dark:text-slate-400 leading-relaxed mb-4">
								{t("chat_free_desc")}
							</p>
						</div>

						<div className="mt-8">
							<Link
								href="/register"
								className="w-full inline-flex items-center justify-center py-2.5 px-4 rounded-xl border border-slate-300 dark:border-slate-700 font-semibold text-xs sm:text-sm text-slate-700 dark:text-slate-200 hover:bg-slate-50 dark:hover:bg-slate-900 transition-colors"
							>
								{t("btn_get_started")}
							</Link>
						</div>
					</div>

					{/* Plan 2: Pay-as-you-go Credits (Featured) */}
					<div className="relative p-6 sm:p-8 rounded-2xl bg-white dark:bg-slate-950 border-2 border-emerald-500 shadow-xl shadow-emerald-500/10 flex flex-col justify-between">
						<div className="absolute -top-3.5 left-1/2 -translate-x-1/2 px-3 py-1 rounded-full bg-emerald-600 text-white text-[11px] font-bold uppercase tracking-wider shadow-sm">
							Pay-As-You-Go
						</div>

						<div>
							<span className="text-xs font-bold uppercase tracking-wider text-emerald-600">
								{t("credit_payg_title")}
							</span>
							<h3 className="text-xl font-bold text-slate-900 dark:text-white mt-1">
								Lead Decryption Credits
							</h3>
							<div className="mt-4 mb-6">
								<span className="text-4xl font-extrabold text-emerald-600 font-mono">
									1.5 credits
								</span>
								<span className="text-slate-400 text-xs ml-1">($0.0015 / phone)</span>
							</div>

							<p className="text-xs sm:text-sm text-slate-600 dark:text-slate-400 leading-relaxed mb-4">
								{t("credit_payg_desc")}
							</p>
						</div>

						<div className="mt-8">
							<Link
								href="/dashboard"
								className="w-full inline-flex items-center justify-center py-2.5 px-4 rounded-xl bg-emerald-600 hover:bg-emerald-700 text-white font-semibold text-xs sm:text-sm shadow-md transition-all"
							>
								{t("btn_get_started")}
							</Link>
						</div>
					</div>

					{/* Plan 3: Enterprise / Agency */}
					<div className="p-6 sm:p-8 rounded-2xl bg-white dark:bg-slate-950 border border-slate-200 dark:border-slate-800 shadow-sm flex flex-col justify-between">
						<div>
							<span className="text-xs font-bold uppercase tracking-wider text-slate-500">
								Enterprise
							</span>
							<h3 className="text-xl font-bold text-slate-900 dark:text-white mt-1">
								Agency & Scale
							</h3>
							<div className="mt-4 mb-6">
								<span className="text-3xl font-extrabold text-slate-900 dark:text-white font-mono">
									Custom
								</span>
								<span className="text-slate-400 text-xs ml-1">/ volume pricing</span>
							</div>

							<ul className="space-y-3 text-xs sm:text-sm text-slate-600 dark:text-slate-400">
								<li className="flex items-center gap-2">
									<Check className="w-4 h-4 text-emerald-500 flex-shrink-0" aria-hidden="true" />
									<span>Dedicated Proxy Pool & Custom Scrapers</span>
								</li>
								<li className="flex items-center gap-2">
									<Check className="w-4 h-4 text-emerald-500 flex-shrink-0" aria-hidden="true" />
									<span>Direct CRM & Webhook Sync (HubSpot, Lark)</span>
								</li>
								<li className="flex items-center gap-2">
									<Check className="w-4 h-4 text-emerald-500 flex-shrink-0" aria-hidden="true" />
									<span>RBAC Multi-Seat Workspace Control</span>
								</li>
							</ul>
						</div>

						<div className="mt-8">
							<Link
								href="/contact"
								className="w-full inline-flex items-center justify-center py-2.5 px-4 rounded-xl border border-slate-300 dark:border-slate-700 font-semibold text-xs sm:text-sm text-slate-700 dark:text-slate-200 hover:bg-slate-50 dark:hover:bg-slate-900 transition-colors"
							>
								Contact Sales
							</Link>
						</div>
					</div>
				</div>
			</div>
		</section>
	);
};
