"use client";

import { ChevronDown } from "lucide-react";
import { useTranslations } from "next-intl";
import type React from "react";
import { useState } from "react";
import { cn } from "@/lib/utils";

export const NowingFaq: React.FC = () => {
	const t = useTranslations("landing.faq");
	const [openIdx, setOpenIdx] = useState<number | null>(0);

	const faqs = [
		{
			q: t("q1"),
			a: t("a1"),
		},
		{
			q: t("q2"),
			a: t("a2"),
		},
		{
			q: t("q3"),
			a: t("a3"),
		},
		{
			q: t("q4"),
			a: t("a4"),
		},
	];

	return (
		<section className="py-16 md:py-24 bg-white dark:bg-slate-950">
			<div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8">
				<div className="text-center max-w-2xl mx-auto mb-12">
					<span className="px-3 py-1 rounded-full bg-emerald-100 dark:bg-emerald-950 text-emerald-800 dark:text-emerald-300 font-bold text-xs uppercase tracking-wider">
						{t("badge")}
					</span>
					<h2 className="mt-3 text-3xl sm:text-4xl font-serif text-slate-900 dark:text-white tracking-tight">
						{t("title")}
					</h2>
				</div>

				<div className="space-y-4">
					{faqs.map((faq, index) => {
						const isOpen = openIdx === index;
						return (
							<div
								key={faq.q}
								className="rounded-2xl border border-slate-200 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-900/50 overflow-hidden transition-colors"
							>
								<button
									type="button"
									onClick={() => setOpenIdx(isOpen ? null : index)}
									className="w-full py-4 px-6 text-left flex items-center justify-between gap-4 font-bold text-sm sm:text-base text-slate-900 dark:text-white"
								>
									<span>{faq.q}</span>
									<ChevronDown
										className={cn(
											"w-4 h-4 text-slate-400 transition-transform duration-200",
											isOpen && "rotate-180 text-emerald-600"
										)}
										aria-hidden="true"
									/>
								</button>
								{isOpen && (
									<div className="px-6 pb-4 pt-1 text-xs sm:text-sm text-slate-600 dark:text-slate-300 leading-relaxed border-t border-slate-200/50 dark:border-slate-800/50 animate-in fade-in-50 duration-150">
										{faq.a}
									</div>
								)}
							</div>
						);
					})}
				</div>
			</div>
		</section>
	);
};
