"use client";

import { Heart, ShieldCheck } from "lucide-react";
import Link from "next/link";
import { useTranslations } from "next-intl";
import type React from "react";
import { NowingLogo } from "./NowingLogo";

export const NowingFooter: React.FC = () => {
	const t = useTranslations("landing.footer");

	return (
		<footer className="bg-slate-900 text-slate-300 py-16 border-t border-slate-800">
			<div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8">
				<div className="grid grid-cols-1 md:grid-cols-5 gap-10 pb-12 border-b border-slate-800">
					{/* Brand column */}
					<div className="md:col-span-2 space-y-4">
						<NowingLogo size={36} showText={true} textClassName="text-white" />
						<p className="text-xs sm:text-sm text-slate-400 max-w-sm leading-relaxed">
							{t("tagline")}
						</p>
						<div className="flex items-center gap-2 text-xs text-emerald-400">
							<ShieldCheck className="w-4 h-4" aria-hidden="true" />
							<span>Enterprise-grade Compliance & Security</span>
						</div>
					</div>

					{/* Links Col 1: Product */}
					<div className="space-y-3">
						<h4 className="text-xs font-bold uppercase tracking-wider text-white">
							{t("col_product")}
						</h4>
						<ul className="space-y-2 text-xs text-slate-400">
							<li>
								<Link href="/dashboard" className="hover:text-emerald-400 transition-colors">
									{t("link_lead_matrix")}
								</Link>
							</li>
							<li>
								<Link href="/dashboard" className="hover:text-emerald-400 transition-colors">
									{t("link_reverse_icp")}
								</Link>
							</li>
							<li>
								<Link href="/dashboard" className="hover:text-emerald-400 transition-colors">
									{t("link_social_copilot")}
								</Link>
							</li>
							<li>
								<Link href="/pricing" className="hover:text-emerald-400 transition-colors">
									{t("link_pricing")}
								</Link>
							</li>
						</ul>
					</div>

					{/* Links Col 2: Solutions */}
					<div className="space-y-3">
						<h4 className="text-xs font-bold uppercase tracking-wider text-white">
							{t("col_solutions")}
						</h4>
						<ul className="space-y-2 text-xs text-slate-400">
							<li>
								<Link href="/dashboard" className="hover:text-emerald-400 transition-colors">
									{t("link_real_estate")}
								</Link>
							</li>
							<li>
								<Link href="/dashboard" className="hover:text-emerald-400 transition-colors">
									{t("link_recruitment")}
								</Link>
							</li>
							<li>
								<Link href="/dashboard" className="hover:text-emerald-400 transition-colors">
									{t("link_b2b_sales")}
								</Link>
							</li>
							<li>
								<Link
									href="/partners"
									className="hover:text-emerald-400 transition-colors text-emerald-400 font-semibold"
								>
									{t("link_affiliate")}
								</Link>
							</li>
						</ul>
					</div>

					{/* Links Col 3: Resources & Company */}
					<div className="space-y-3">
						<h4 className="text-xs font-bold uppercase tracking-wider text-white">
							{t("col_resources")}
						</h4>
						<ul className="space-y-2 text-xs text-slate-400">
							<li>
								<Link href="/docs" className="hover:text-emerald-400 transition-colors">
									{t("link_docs")}
								</Link>
							</li>
							<li>
								<Link href="/terms" className="hover:text-emerald-400 transition-colors">
									{t("link_terms")}
								</Link>
							</li>
							<li>
								<Link href="/privacy" className="hover:text-emerald-400 transition-colors">
									{t("link_privacy")}
								</Link>
							</li>
							<li>
								<Link href="/contact" className="hover:text-emerald-400 transition-colors">
									Contact Support
								</Link>
							</li>
						</ul>
					</div>
				</div>

				<div className="pt-8 flex flex-col sm:flex-row items-center justify-between gap-4 text-xs text-slate-500">
					<div>{t("copyright")}</div>
					<div className="flex items-center gap-1">
						<span>Built with</span>
						<Heart className="w-3.5 h-3.5 text-rose-500 fill-rose-500" aria-hidden="true" />
						<span>for modern revenue teams</span>
					</div>
				</div>
			</div>
		</footer>
	);
};
