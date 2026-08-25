"use client";

import { ArrowRight, Coins } from "lucide-react";
import Link from "next/link";
import { useTranslations } from "next-intl";
import type React from "react";

export const AffiliateBanner: React.FC = () => {
	const t = useTranslations("landing.affiliate");

	return (
		<section className="py-12 bg-gradient-to-br from-emerald-900 via-slate-900 to-slate-950 text-white relative overflow-hidden">
			{/* Ambient glows */}
			<div className="absolute top-0 right-0 w-96 h-96 bg-emerald-500/10 rounded-full blur-3xl pointer-events-none" />
			<div className="absolute bottom-0 left-0 w-80 h-80 bg-teal-500/10 rounded-full blur-3xl pointer-events-none" />

			<div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 relative z-10">
				<div className="flex flex-col md:flex-row items-center justify-between gap-8 p-8 rounded-3xl bg-white/5 border border-white/10 backdrop-blur-md">
					<div className="max-w-2xl">
						<div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-emerald-500/20 text-emerald-300 text-xs font-semibold mb-3 border border-emerald-500/30">
							<Coins className="w-3.5 h-3.5" aria-hidden="true" />
							<span>{t("badge")}</span>
						</div>

						<h3 className="text-2xl sm:text-3xl font-serif font-normal tracking-tight text-white">
							{t("title")}
						</h3>

						<p className="mt-2 text-sm text-slate-300 leading-relaxed">{t("subtitle")}</p>
					</div>

					<div className="flex-shrink-0">
						<Link
							href="/partners"
							className="inline-flex items-center gap-2 px-6 py-3.5 rounded-2xl bg-emerald-500 hover:bg-emerald-400 text-slate-950 font-bold text-sm shadow-lg shadow-emerald-500/20 transition-all hover:scale-105 active:scale-95"
						>
							<span>{t("btn_join")}</span>
							<ArrowRight className="w-4 h-4" aria-hidden="true" />
						</Link>
					</div>
				</div>
			</div>
		</section>
	);
};
