"use client";

import { useTranslations } from "next-intl";
import type React from "react";

export const WorkflowSteps: React.FC = () => {
	const t = useTranslations("landing.workflow");
	return (
		<section className="py-16 md:py-24 bg-slate-50/60 dark:bg-slate-900/40 border-t border-slate-200/80 dark:border-slate-800">
			<div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8">
				<div className="text-center max-w-3xl mx-auto mb-14">
					<span className="px-3 py-1 rounded-full bg-emerald-100 dark:bg-emerald-950 text-emerald-800 dark:text-emerald-300 font-bold text-xs uppercase tracking-wider">
						{t("badge")}
					</span>
					<h2 className="mt-3 text-3xl sm:text-4xl font-serif text-slate-900 dark:text-white tracking-tight">
						{t("title")}
					</h2>
				</div>

				<div className="grid grid-cols-1 md:grid-cols-3 gap-8">
					<div className="relative p-6 rounded-2xl bg-white dark:bg-slate-950 border border-slate-200 dark:border-slate-800 shadow-sm">
						<div className="w-12 h-12 rounded-xl bg-emerald-100 dark:bg-emerald-950/80 text-emerald-700 dark:text-emerald-300 flex items-center justify-center font-bold text-lg mb-4">
							01
						</div>
						<h3 className="text-lg font-bold text-slate-900 dark:text-white mb-2">
							{t("step1_title")}
						</h3>
						<p className="text-xs sm:text-sm text-slate-600 dark:text-slate-400 leading-relaxed">
							{t("step1_desc")}
						</p>
					</div>

					<div className="relative p-6 rounded-2xl bg-white dark:bg-slate-950 border border-slate-200 dark:border-slate-800 shadow-sm">
						<div className="w-12 h-12 rounded-xl bg-teal-100 dark:bg-teal-950/80 text-teal-700 dark:text-teal-300 flex items-center justify-center font-bold text-lg mb-4">
							02
						</div>
						<h3 className="text-lg font-bold text-slate-900 dark:text-white mb-2">
							{t("step2_title")}
						</h3>
						<p className="text-xs sm:text-sm text-slate-600 dark:text-slate-400 leading-relaxed">
							{t("step2_desc")}
						</p>
					</div>

					<div className="relative p-6 rounded-2xl bg-white dark:bg-slate-950 border border-slate-200 dark:border-slate-800 shadow-sm">
						<div className="w-12 h-12 rounded-xl bg-blue-100 dark:bg-blue-950/80 text-blue-700 dark:text-blue-300 flex items-center justify-center font-bold text-lg mb-4">
							03
						</div>
						<h3 className="text-lg font-bold text-slate-900 dark:text-white mb-2">
							{t("step3_title")}
						</h3>
						<p className="text-xs sm:text-sm text-slate-600 dark:text-slate-400 leading-relaxed">
							{t("step3_desc")}
						</p>
					</div>
				</div>
			</div>
		</section>
	);
};
