"use client";

import { useTranslations } from "next-intl";
import type React from "react";

export const LiveMetricsCounter: React.FC = () => {
	const t = useTranslations("landing.metrics");
	return (
		<section className="py-12 bg-white dark:bg-slate-950 border-b border-slate-200/80 dark:border-slate-800">
			<div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8">
				<div className="grid grid-cols-2 md:grid-cols-4 gap-6 text-center">
					<div className="p-4 rounded-xl">
						<div className="text-3xl sm:text-4xl font-extrabold text-slate-900 dark:text-white font-mono tracking-tight">
							{t("accuracy_rate")}
						</div>
						<div className="text-xs sm:text-sm font-semibold text-emerald-600 dark:text-emerald-400 mt-1">
							{t("accuracy_label")}
						</div>
					</div>

					<div className="p-4 rounded-xl">
						<div className="text-3xl sm:text-4xl font-extrabold text-slate-900 dark:text-white font-mono tracking-tight">
							{t("leads_count")}
						</div>
						<div className="text-xs sm:text-sm font-semibold text-emerald-600 dark:text-emerald-400 mt-1">
							{t("leads_label")}
						</div>
					</div>

					<div className="p-4 rounded-xl">
						<div className="text-3xl sm:text-4xl font-extrabold text-slate-900 dark:text-white font-mono tracking-tight">
							{t("sources_count")}
						</div>
						<div className="text-xs sm:text-sm font-semibold text-emerald-600 dark:text-emerald-400 mt-1">
							{t("sources_label")}
						</div>
					</div>

					<div className="p-4 rounded-xl">
						<div className="text-3xl sm:text-4xl font-extrabold text-emerald-600 dark:text-emerald-400 font-mono tracking-tight">
							{t("customers_count")}
						</div>
						<div className="text-xs sm:text-sm font-semibold text-slate-900 dark:text-white mt-1">
							{t("customers_label")}
						</div>
					</div>
				</div>
			</div>
		</section>
	);
};
