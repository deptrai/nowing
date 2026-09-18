"use client";

import { IconCalculator, IconCheck, IconSparkles, IconTrendingUp } from "@tabler/icons-react";
import Link from "next/link";
import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Slider } from "@/components/ui/slider";
import { useTranslations } from "next-intl";

export function PricingLeadCalculator() {
	const t = useTranslations("pricing");
	const [phoneUnlocks, setPhoneUnlocks] = useState<number>(300);
	const [researchQueries, setResearchQueries] = useState<number>(100);
	const [scrapedItems, setScrapedItems] = useState<number>(2000);

	// Unit rates
	const phoneCost = phoneUnlocks * 0.05; // $0.05 per verified phone
	const researchCost = researchQueries * 0.03; // $0.03 per deep research run
	const scrapingCost = scrapedItems * 0.002; // $0.002 per scraped lead/post

	const totalNowingCost = Math.max(0, phoneCost + researchCost + scrapingCost);
	// ZoomInfo / Apollo Enterprise equivalent (~$0.60 per lead phone + $200 platform baseline)
	const legacyProviderCost = phoneUnlocks * 0.6 + researchQueries * 0.5 + 250;
	const monthlySavings = Math.max(0, legacyProviderCost - totalNowingCost);
	const savingsPercent = Math.round((monthlySavings / legacyProviderCost) * 100);

	return (
		<div className="w-full max-w-5xl mx-auto my-16 px-4">
			<div className="relative rounded-3xl border border-emerald-200/80 dark:border-emerald-800/50 bg-gradient-to-b from-emerald-50/40 via-white to-white dark:from-emerald-950/20 dark:via-neutral-900 dark:to-neutral-900 p-8 md:p-12 shadow-xl shadow-emerald-500/5 overflow-hidden">
				{/* Background Grid Pattern */}
				<div
					className="absolute inset-0 opacity-[0.03] dark:opacity-[0.05] pointer-events-none"
					style={{
						backgroundImage: "radial-gradient(#059669 1px, transparent 1px)",
						backgroundSize: "24px 24px",
					}}
				/>

				<div className="relative z-10">
					<div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-neutral-200/60 dark:border-neutral-800 pb-6 mb-8">
						<div>
							<div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-emerald-100/80 dark:bg-emerald-900/40 text-emerald-800 dark:text-emerald-300 text-xs font-semibold uppercase tracking-wider mb-2">
								<IconCalculator className="size-3.5" />
								<span>{t("calc_badge")}</span>
							</div>
							<h3 className="font-serif text-2xl md:text-3xl font-normal tracking-tight text-neutral-900 dark:text-white">
								{t("calc_title")}
							</h3>
							<p className="text-sm md:text-base text-neutral-600 dark:text-neutral-400 mt-1">
								{t("calc_desc")}
							</p>
						</div>

						<div className="flex items-center gap-2 bg-emerald-500/10 border border-emerald-500/20 rounded-2xl px-4 py-2 text-emerald-700 dark:text-emerald-300 text-sm font-medium">
							<IconSparkles className="size-4 shrink-0" />
							<span>{t("calc_starter_credit")}</span>
						</div>
					</div>

					<div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-center">
						{/* Sliders Column */}
						<div className="lg:col-span-7 space-y-6">
							{/* Phone Unlocks */}
							<div className="bg-white/80 dark:bg-neutral-800/50 backdrop-blur-xs p-5 rounded-2xl border border-neutral-200/70 dark:border-neutral-700/60 shadow-xs">
								<div className="flex justify-between items-center mb-3">
									<div>
										<span className="font-semibold text-neutral-800 dark:text-neutral-200 text-sm md:text-base">
											{t("calc_phone_title")}
										</span>
										<div className="text-xs text-neutral-500 dark:text-neutral-400">
											{t("calc_phone_rate")}
										</div>
									</div>
									<span className="font-mono font-bold text-emerald-600 dark:text-emerald-400 text-lg">
										{t("calc_phone_unit", { count: phoneUnlocks.toLocaleString() })}
									</span>
								</div>
								<Slider
									value={[phoneUnlocks]}
									onValueChange={(val) => setPhoneUnlocks(val[0])}
									min={0}
									max={3000}
									step={50}
									className="py-2"
								/>
							</div>

							{/* Deep Research & Agent Tasks */}
							<div className="bg-white/80 dark:bg-neutral-800/50 backdrop-blur-xs p-5 rounded-2xl border border-neutral-200/70 dark:border-neutral-700/60 shadow-xs">
								<div className="flex justify-between items-center mb-3">
									<div>
										<span className="font-semibold text-neutral-800 dark:text-neutral-200 text-sm md:text-base">
											{t("calc_research_title")}
										</span>
										<div className="text-xs text-neutral-500 dark:text-neutral-400">
											{t("calc_research_rate")}
										</div>
									</div>
									<span className="font-mono font-bold text-emerald-600 dark:text-emerald-400 text-lg">
										{t("calc_phone_unit", { count: researchQueries.toLocaleString() })}
									</span>
								</div>
								<Slider
									value={[researchQueries]}
									onValueChange={(val) => setResearchQueries(val[0])}
									min={0}
									max={1000}
									step={20}
									className="py-2"
								/>
							</div>

							{/* Data Scrapers & Social Feeds */}
							<div className="bg-white/80 dark:bg-neutral-800/50 backdrop-blur-xs p-5 rounded-2xl border border-neutral-200/70 dark:border-neutral-700/60 shadow-xs">
								<div className="flex justify-between items-center mb-3">
									<div>
										<span className="font-semibold text-neutral-800 dark:text-neutral-200 text-sm md:text-base">
											{t("calc_scraping_title")}
										</span>
										<div className="text-xs text-neutral-500 dark:text-neutral-400">
											{t("calc_scraping_rate")}
										</div>
									</div>
									<span className="font-mono font-bold text-emerald-600 dark:text-emerald-400 text-lg">
										{t("calc_phone_unit", { count: scrapedItems.toLocaleString() })}
									</span>
								</div>
								<Slider
									value={[scrapedItems]}
									onValueChange={(val) => setScrapedItems(val[0])}
									min={0}
									max={20000}
									step={250}
									className="py-2"
								/>
							</div>
						</div>

						{/* Results Card */}
						<div className="lg:col-span-5 bg-neutral-900 dark:bg-neutral-950 text-white p-7 rounded-3xl border border-neutral-800 shadow-2xl relative overflow-hidden flex flex-col justify-between">
							<div className="space-y-6">
								<div className="flex items-center justify-between">
									<span className="text-xs font-semibold tracking-wider text-emerald-400 uppercase">
										{t("calc_est_bill")}
									</span>
									<span className="inline-flex items-center gap-1 bg-emerald-500/20 text-emerald-300 text-xs px-2.5 py-0.5 rounded-full font-medium">
										<IconTrendingUp className="size-3.5" /> {t("calc_savings_pct", { percent: savingsPercent })}
									</span>
								</div>

								<div>
									<div className="flex items-baseline gap-1">
										<span className="text-4xl md:text-5xl font-black font-mono tracking-tight text-emerald-400">
											${totalNowingCost.toFixed(2)}
										</span>
										<span className="text-neutral-400 text-sm font-medium">{t("calc_per_month")}</span>
									</div>
									<div className="text-xs text-neutral-400 mt-1">
										{t("calc_approx_vnd", { amount: (totalNowingCost * 25400).toLocaleString("vi-VN") })}
									</div>
								</div>

								<div className="p-4 rounded-2xl bg-neutral-800/70 border border-neutral-700/60 space-y-2 text-xs">
									<div className="flex justify-between text-neutral-400">
										<span>{t("calc_legacy_sub")}</span>
										<span className="line-through font-mono text-neutral-500">
											${legacyProviderCost.toFixed(0)}/mo
										</span>
									</div>
									<div className="flex justify-between font-semibold text-emerald-300">
										<span>{t("calc_monthly_savings")}</span>
										<span className="font-mono text-sm">+${monthlySavings.toFixed(2)}</span>
									</div>
								</div>

								<ul className="space-y-2 text-xs text-neutral-300">
									<li className="flex items-center gap-2">
										<IconCheck className="size-4 text-emerald-400 shrink-0" />
										<span>{t("calc_benefit_no_lockin")}</span>
									</li>
									<li className="flex items-center gap-2">
										<IconCheck className="size-4 text-emerald-400 shrink-0" />
										<span>{t("calc_benefit_no_fail_charge")}</span>
									</li>
									<li className="flex items-center gap-2">
										<IconCheck className="size-4 text-emerald-400 shrink-0" />
										<span>{t("calc_benefit_no_expiry")}</span>
									</li>
								</ul>
							</div>

							<div className="mt-6 pt-4 border-t border-neutral-800">
								<Link href="/login" className="w-full block">
									<Button className="w-full bg-emerald-500 hover:bg-emerald-600 text-neutral-950 font-bold py-5 rounded-xl transition-all shadow-lg shadow-emerald-500/20">
										{t("calc_start_free")}
									</Button>
								</Link>
							</div>
						</div>
					</div>
				</div>
			</div>
		</div>
	);
}
