"use client";

import {
	ArrowRight,
	Briefcase,
	Building2,
	GraduationCap,
	HardHat,
	HeartPulse,
	Landmark,
	ShoppingBag,
	Store,
	Truck,
	Users,
	Utensils,
	Wheat,
} from "lucide-react";
import Link from "next/link";
import { useTranslations } from "next-intl";
import type React from "react";

export const VerticalsMegaGrid: React.FC = () => {
	const t = useTranslations("landing.verticals");

	const verticals = [
		{
			icon: Building2,
			title: t("v_bds_title"),
			description: t("v_bds_desc"),
			tags: ["Batdongsan", "Chợ Tốt Nhà", "Zalo BĐS"],
			color: "text-emerald-600 bg-emerald-50 dark:bg-emerald-950/60",
		},
		{
			icon: Users,
			title: t("v_it_title"),
			description: t("v_it_desc"),
			tags: ["TopCV", "ITviec", "Headhunter"],
			color: "text-blue-600 bg-blue-50 dark:bg-blue-950/60",
		},
		{
			icon: ShoppingBag,
			title: t("v_b2b_title"),
			description: t("v_b2b_desc"),
			tags: ["B2B", "MST", "ĐKKD"],
			color: "text-amber-600 bg-amber-50 dark:bg-amber-950/60",
		},
		{
			icon: HardHat,
			title: t("v_tender_title"),
			description: t("v_tender_desc"),
			tags: ["Mua Sắm Công", "Nhà thầu", "Vật liệu"],
			color: "text-cyan-600 bg-cyan-50 dark:bg-cyan-950/60",
		},
		{
			icon: Store,
			title: t("v_fashion_title"),
			description: t("v_fashion_desc"),
			tags: ["TikTok Shop", "Shopee Top", "Wholesale"],
			color: "text-pink-600 bg-pink-50 dark:bg-pink-950/60",
		},
		{
			icon: Landmark,
			title: t("v_finance_title"),
			description: t("v_finance_desc"),
			tags: ["CafeF", "Vietstock", "BCTC"],
			color: "text-teal-600 bg-teal-50 dark:bg-teal-950/60",
		},
		{
			icon: Truck,
			title: t("v_logistics_title"),
			description: t("v_logistics_desc"),
			tags: ["Kho bãi", "Chủ hàng", "Xuất nhập khẩu"],
			color: "text-indigo-600 bg-indigo-50 dark:bg-indigo-950/60",
		},
		{
			icon: Utensils,
			title: t("v_franchise_title"),
			description: t("v_franchise_desc"),
			tags: ["Mặt bằng F&B", "Chủ quán", "ShopeeFood"],
			color: "text-orange-600 bg-orange-50 dark:bg-orange-950/60",
		},
		{
			icon: Briefcase,
			title: t("v_auto_title"),
			description: t("v_auto_desc"),
			tags: ["Showroom", "Garage", "Auto"],
			color: "text-slate-600 bg-slate-100 dark:bg-slate-800",
		},
		{
			icon: HeartPulse,
			title: t("v_health_title"),
			description: t("v_health_desc"),
			tags: ["Phòng khám", "Chủ Spa", "Bác sĩ"],
			color: "text-rose-600 bg-rose-50 dark:bg-rose-950/60",
		},
		{
			icon: GraduationCap,
			title: t("v_legal_title"),
			description: t("v_legal_desc"),
			tags: ["ĐKKD", "Kế toán", "Thuế"],
			color: "text-purple-600 bg-purple-50 dark:bg-purple-950/60",
		},
		{
			icon: Wheat,
			title: t("v_solar_title"),
			description: t("v_solar_desc"),
			tags: ["Solar", "EPC", "Energy"],
			color: "text-lime-600 bg-lime-50 dark:bg-lime-950/60",
		},
	];

	return (
		<section className="py-16 md:py-24 bg-white dark:bg-slate-950">
			<div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8">
				{/* Header */}
				<div className="text-center max-w-3xl mx-auto mb-14">
					<span className="px-3 py-1 rounded-full bg-emerald-100 dark:bg-emerald-950 text-emerald-800 dark:text-emerald-300 font-bold text-xs uppercase tracking-wider">
						{t("badge")}
					</span>
					<h2 className="mt-3 text-3xl sm:text-4xl font-serif text-slate-900 dark:text-white tracking-tight">
						{t("title")}
					</h2>
					<p className="mt-3 text-base text-slate-600 dark:text-slate-400">{t("subtitle")}</p>
				</div>

				{/* 12 Grid Cards */}
				<div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6">
					{verticals.map((item) => {
						const IconComp = item.icon;
						return (
							<div
								key={item.title}
								className="group relative p-6 rounded-2xl bg-slate-50/70 dark:bg-slate-900/60 border border-slate-200/80 dark:border-slate-800 hover:border-emerald-400/80 dark:hover:border-emerald-500/80 transition-all hover:shadow-lg hover:shadow-emerald-500/5 flex flex-col justify-between"
							>
								<div>
									<div
										className={`w-10 h-10 rounded-xl flex items-center justify-center mb-4 ${item.color}`}
									>
										<IconComp className="w-5 h-5" />
									</div>

									<h3 className="text-base font-bold text-slate-900 dark:text-white group-hover:text-emerald-600 dark:group-hover:text-emerald-400 transition-colors">
										{item.title}
									</h3>

									<p className="mt-2 text-xs sm:text-sm text-slate-600 dark:text-slate-400 leading-relaxed">
										{item.description}
									</p>
								</div>

								<div className="mt-4 pt-4 border-t border-slate-200/60 dark:border-slate-800 flex flex-wrap items-center gap-1.5">
									{item.tags.map((tag) => (
										<span
											key={`${item.title}-${tag}`}
											className="px-2 py-0.5 rounded-md bg-white dark:bg-slate-800 text-slate-600 dark:text-slate-300 text-[11px] font-medium border border-slate-200 dark:border-slate-700"
										>
											{tag}
										</span>
									))}
								</div>
							</div>
						);
					})}
				</div>

				{/* Bottom Note */}
				<div className="mt-10 text-center">
					<Link
						href="/dashboard"
						className="inline-flex items-center gap-2 px-5 py-2.5 rounded-xl bg-slate-900 hover:bg-slate-800 dark:bg-emerald-600 dark:hover:bg-emerald-500 text-white text-xs sm:text-sm font-semibold shadow-sm transition-all"
					>
						<span>Launch Lead Search</span>
						<ArrowRight className="w-4 h-4" />
					</Link>
				</div>
			</div>
		</section>
	);
};
