"use client";

import { Check } from "lucide-react";
import { useTranslations } from "next-intl";
import type React from "react";

export const NowingCompareTable: React.FC = () => {
	const t = useTranslations("landing.compare");

	const features = [
		{
			title: t("f_vietnam_sources"),
			nowing: t("f_vietnam_sources_nowing"),
			apollo: t("f_vietnam_sources_apollo"),
			clay: t("f_vietnam_sources_clay"),
		},
		{
			title: t("f_phone_accuracy"),
			nowing: t("f_phone_accuracy_nowing"),
			apollo: t("f_phone_accuracy_apollo"),
			clay: t("f_phone_accuracy_clay"),
		},
		{
			title: t("f_pricing"),
			nowing: t("f_pricing_nowing"),
			apollo: t("f_pricing_apollo"),
			clay: t("f_pricing_clay"),
		},
		{
			title: t("f_split_canvas"),
			nowing: t("f_split_canvas_nowing"),
			apollo: t("f_split_canvas_apollo"),
			clay: t("f_split_canvas_clay"),
		},
		{
			title: t("f_zalo_outreach"),
			nowing: t("f_zalo_outreach_nowing"),
			apollo: t("f_zalo_outreach_apollo"),
			clay: t("f_zalo_outreach_clay"),
		},
	];

	return (
		<section className="py-16 md:py-24 bg-white dark:bg-slate-950">
			<div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8">
				<div className="text-center max-w-3xl mx-auto mb-12">
					<span className="px-3 py-1 rounded-full bg-emerald-100 dark:bg-emerald-950 text-emerald-800 dark:text-emerald-300 font-bold text-xs uppercase tracking-wider">
						{t("badge")}
					</span>
					<h2 className="mt-3 text-3xl sm:text-4xl font-serif text-slate-900 dark:text-white tracking-tight">
						{t("title")}
					</h2>
					<p className="mt-3 text-base text-slate-600 dark:text-slate-400">{t("subtitle")}</p>
				</div>

				<div className="overflow-x-auto">
					<table className="w-full text-left text-xs sm:text-sm border-collapse rounded-2xl overflow-hidden shadow-lg border border-slate-200 dark:border-slate-800">
						<thead>
							<tr className="bg-slate-50 dark:bg-slate-900 text-slate-700 dark:text-slate-200 border-b border-slate-200 dark:border-slate-800">
								<th className="py-4 px-5 font-bold w-1/3">{t("col_feature")}</th>
								<th className="py-4 px-5 font-extrabold text-emerald-700 dark:text-emerald-400 bg-emerald-50/70 dark:bg-emerald-950/40 w-1/4">
									🌿 {t("col_nowing")}
								</th>
								<th className="py-4 px-5 font-semibold text-slate-500 w-1/6">{t("col_apollo")}</th>
								<th className="py-4 px-5 font-semibold text-slate-500 w-1/6">{t("col_clay")}</th>
							</tr>
						</thead>
						<tbody className="divide-y divide-slate-100 dark:divide-slate-800/80 bg-white dark:bg-slate-950">
							{features.map((item) => (
								<tr key={item.title} className="hover:bg-slate-50/50 dark:hover:bg-slate-900/30">
									<td className="py-4 px-5 font-medium text-slate-900 dark:text-slate-100">
										{item.title}
									</td>
									<td className="py-4 px-5 font-bold text-emerald-700 dark:text-emerald-300 bg-emerald-50/40 dark:bg-emerald-950/20">
										<div className="flex items-start gap-2">
											<Check className="w-4 h-4 text-emerald-600 mt-0.5 flex-shrink-0" />
											<span>{item.nowing}</span>
										</div>
									</td>
									<td className="py-4 px-5 text-slate-500 dark:text-slate-400">{item.apollo}</td>
									<td className="py-4 px-5 text-slate-500 dark:text-slate-400">{item.clay}</td>
								</tr>
							))}
						</tbody>
					</table>
				</div>
			</div>
		</section>
	);
};
