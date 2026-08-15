"use client";

import {
	IconCalculator,
	IconCoins,
	IconQrcode,
	IconSparkles,
	IconTrendingUp,
} from "@tabler/icons-react";
import Link from "next/link";
import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Slider } from "@/components/ui/slider";

const USD_TO_VND_RATE = 25400;

export function PartnerEarningsCalculator() {
	const [referredUsers, setReferredUsers] = useState<number>(25);
	const [avgSpendUsd, setAvgSpendUsd] = useState<number>(100);

	const totalClientSpend = referredUsers * avgSpendUsd;
	const monthlyCommissionUsd = totalClientSpend * 0.15; // 15% lifetime recurring
	const monthlyCommissionVnd = Math.round(monthlyCommissionUsd * USD_TO_VND_RATE);
	const annualCommissionUsd = monthlyCommissionUsd * 12;
	const annualCommissionVnd = Math.round(annualCommissionUsd * USD_TO_VND_RATE);

	const creditBonusUsd = monthlyCommissionUsd * 1.1; // +10% bonus when converted to platform credit

	return (
		<div className="w-full max-w-5xl mx-auto my-16 px-4">
			<div className="relative rounded-3xl border border-emerald-200/90 dark:border-emerald-800/60 bg-gradient-to-b from-emerald-50/50 via-white to-white dark:from-emerald-950/20 dark:via-neutral-900 dark:to-neutral-900 p-8 md:p-12 shadow-2xl shadow-emerald-500/5 overflow-hidden">
				<div
					className="absolute inset-0 opacity-[0.03] dark:opacity-[0.05] pointer-events-none"
					style={{
						backgroundImage: "radial-gradient(#10b981 1px, transparent 1px)",
						backgroundSize: "24px 24px",
					}}
				/>

				<div className="relative z-10">
					<div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-neutral-200/60 dark:border-neutral-800 pb-6 mb-8">
						<div>
							<div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-emerald-100/80 dark:bg-emerald-900/40 text-emerald-800 dark:text-emerald-300 text-xs font-semibold uppercase tracking-wider mb-2">
								<IconCalculator className="size-3.5" />
								<span>Affiliate Earnings Simulator</span>
							</div>
							<h3 className="text-2xl md:text-3xl font-bold tracking-tight text-neutral-900 dark:text-white">
								Calculate Your 15% Lifetime Recurring Income
							</h3>
							<p className="text-sm md:text-base text-neutral-600 dark:text-neutral-400 mt-1">
								Earn passive revenue on every single credit top-up your referrals make, forever.
							</p>
						</div>

						<div className="flex items-center gap-2 bg-emerald-500/10 border border-emerald-500/20 rounded-2xl px-4 py-2 text-emerald-700 dark:text-emerald-300 text-sm font-medium">
							<IconSparkles className="size-4 shrink-0" />
							<span>Instant VietQR Napas 24/7 Payouts</span>
						</div>
					</div>

					<div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-center">
						{/* Controls Column */}
						<div className="lg:col-span-7 space-y-6">
							{/* Number of referred active clients */}
							<div className="bg-white/80 dark:bg-neutral-800/50 backdrop-blur-xs p-5 rounded-2xl border border-neutral-200/70 dark:border-neutral-700/60 shadow-xs">
								<div className="flex justify-between items-center mb-3">
									<div>
										<span className="font-semibold text-neutral-800 dark:text-neutral-200 text-sm md:text-base">
											Referred Active Clients / Agencies
										</span>
										<div className="text-xs text-neutral-500 dark:text-neutral-400">
											Teams or individuals using Nowing for lead gen & research
										</div>
									</div>
									<span className="font-mono font-bold text-emerald-600 dark:text-emerald-400 text-xl">
										{referredUsers}
									</span>
								</div>
								<Slider
									value={[referredUsers]}
									onValueChange={(val) => setReferredUsers(val[0])}
									min={1}
									max={200}
									step={1}
									className="py-2"
								/>
							</div>

							{/* Average monthly spend per client */}
							<div className="bg-white/80 dark:bg-neutral-800/50 backdrop-blur-xs p-5 rounded-2xl border border-neutral-200/70 dark:border-neutral-700/60 shadow-xs">
								<div className="flex justify-between items-center mb-3">
									<div>
										<span className="font-semibold text-neutral-800 dark:text-neutral-200 text-sm md:text-base">
											Average Monthly Spend per Client
										</span>
										<div className="text-xs text-neutral-500 dark:text-neutral-400">
											Credits purchased for phone unlocks, scrapers & deep research
										</div>
									</div>
									<span className="font-mono font-bold text-emerald-600 dark:text-emerald-400 text-xl">
										${avgSpendUsd} /mo
									</span>
								</div>
								<Slider
									value={[avgSpendUsd]}
									onValueChange={(val) => setAvgSpendUsd(val[0])}
									min={20}
									max={1000}
									step={10}
									className="py-2"
								/>
							</div>

							{/* Payout Options Comparison */}
							<div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
								<div className="p-4 rounded-2xl border border-emerald-200/60 dark:border-emerald-800/40 bg-emerald-50/40 dark:bg-emerald-950/20">
									<div className="flex items-center gap-2 text-emerald-700 dark:text-emerald-300 font-semibold text-sm mb-1">
										<IconQrcode className="size-4" />
										<span>Option A: VietQR Napas</span>
									</div>
									<p className="text-xs text-neutral-600 dark:text-neutral-400">
										Direct 24/7 bank transfer to Vietcombank, Techcombank, MBBank with zero
										withdrawal fee.
									</p>
								</div>
								<div className="p-4 rounded-2xl border border-emerald-200/60 dark:border-emerald-800/40 bg-emerald-50/40 dark:bg-emerald-950/20">
									<div className="flex items-center gap-2 text-emerald-700 dark:text-emerald-300 font-semibold text-sm mb-1">
										<IconCoins className="size-4" />
										<span>Option B: Credit Wallet (+10%)</span>
									</div>
									<p className="text-xs text-neutral-600 dark:text-neutral-400">
										Convert earnings to Nowing platform credits with an instant +10% bonus for your
										own agency campaigns.
									</p>
								</div>
							</div>
						</div>

						{/* Earnings Summary Card */}
						<div className="lg:col-span-5 bg-neutral-900 dark:bg-neutral-950 text-white p-7 rounded-3xl border border-neutral-800 shadow-2xl relative overflow-hidden flex flex-col justify-between">
							<div className="space-y-6">
								<div className="flex items-center justify-between">
									<span className="text-xs font-semibold tracking-wider text-emerald-400 uppercase">
										Your Monthly Commission (15%)
									</span>
									<span className="inline-flex items-center gap-1 bg-emerald-500/20 text-emerald-300 text-xs px-2.5 py-0.5 rounded-full font-medium">
										<IconTrendingUp className="size-3.5" /> Lifetime Recurring
									</span>
								</div>

								<div>
									<div className="flex items-baseline gap-1">
										<span className="text-4xl md:text-5xl font-black font-mono tracking-tight text-emerald-400">
											$
											{monthlyCommissionUsd.toLocaleString("en-US", {
												minimumFractionDigits: 2,
												maximumFractionDigits: 2,
											})}
										</span>
										<span className="text-neutral-400 text-sm font-medium">/ month</span>
									</div>
									<div className="text-base font-bold text-white mt-1 font-mono">
										≈ {monthlyCommissionVnd.toLocaleString("vi-VN")} VND / tháng
									</div>
								</div>

								<div className="p-4 rounded-2xl bg-neutral-800/70 border border-neutral-700/60 space-y-2 text-xs">
									<div className="flex justify-between text-neutral-400">
										<span>Annual Run Rate:</span>
										<span className="font-mono text-white font-semibold">
											${annualCommissionUsd.toLocaleString("en-US", { minimumFractionDigits: 2 })} (
											{annualCommissionVnd.toLocaleString("vi-VN")} VND)
										</span>
									</div>
									<div className="flex justify-between text-neutral-400">
										<span>Total Client Spend:</span>
										<span className="font-mono text-white">
											${totalClientSpend.toLocaleString()} /mo
										</span>
									</div>
									<div className="flex justify-between font-semibold text-emerald-300 pt-1 border-t border-neutral-700/60">
										<span>If converted to Credits (+10%):</span>
										<span className="font-mono text-sm">
											${creditBonusUsd.toFixed(2)}/mo in credits
										</span>
									</div>
								</div>
							</div>

							<div className="mt-6 pt-4 border-t border-neutral-800">
								<Link href="/partners/dashboard" className="w-full block">
									<Button className="w-full bg-emerald-500 hover:bg-emerald-600 text-neutral-950 font-bold py-5 rounded-xl transition-all shadow-lg shadow-emerald-500/20">
										Join Partner Program Now
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
