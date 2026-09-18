"use client";
import {
	IconAffiliate,
	IconArrowRight,
	IconCoins,
	IconPhoneCall,
	IconPlus,
	IconSearch,
	IconWorld,
} from "@tabler/icons-react";
import { AnimatePresence, motion } from "motion/react";
import Link from "next/link";
import type React from "react";
import { useEffect, useRef, useState } from "react";
import { Pricing } from "@/components/pricing";
import { FAQJsonLd } from "@/components/seo/json-ld";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { PricingLeadCalculator } from "./PricingLeadCalculator";
import { useTranslations } from "next-intl";

const getDemoPlans = (t: (k: string) => string) => [
	{
		name: t("plan_free_name"),
		price: "0",
		yearlyPrice: "0",
		period: "",
		billingText: t("plan_free_billing"),
		features: [
			t("plan_free_f1"),
			t("plan_free_f2"),
			t("plan_free_f3"),
			t("plan_free_f4"),
			t("plan_free_f5"),
		],
		description: "",
		buttonText: t("plan_free_btn"),
		href: "https://github.com/deptrai/nowing",
		isPopular: false,
	},
	{
		name: t("plan_payg_name"),
		price: "5",
		yearlyPrice: "5",
		period: t("plan_payg_period"),
		billingText: t("plan_payg_billing"),
		features: [
			t("plan_payg_f1"),
			t("plan_payg_f2"),
			t("plan_payg_f3"),
			t("plan_payg_f4"),
			t("plan_payg_f5"),
			t("plan_payg_f6"),
			t("plan_payg_f7"),
			t("plan_payg_f8"),
			t("plan_payg_f9"),
		],
		description: "",
		buttonText: t("plan_payg_btn"),
		href: "/login",
		isPopular: true,
	},
	{
		name: t("plan_enterprise_name"),
		price: t("plan_enterprise_price"),
		yearlyPrice: t("plan_enterprise_price"),
		period: "",
		billingText: "",
		features: [
			t("plan_enterprise_f1"),
			t("plan_enterprise_f2"),
			t("plan_enterprise_f3"),
			t("plan_enterprise_f4"),
			t("plan_enterprise_f5"),
			t("plan_enterprise_f6"),
			t("plan_enterprise_f7"),
			t("plan_enterprise_f8"),
			t("plan_enterprise_f9"),
		],
		description: t("plan_enterprise_desc"),
		buttonText: t("plan_enterprise_btn"),
		href: "/contact",
		isPopular: false,
	},
];

interface FAQItem {
	question: string;
	answer: string;
}

interface FAQSection {
	title: string;
	items: FAQItem[];
}

const getFaqData = (t: (k: string) => string): FAQSection[] => [
	{
		title: t("faq_sec_payg"),
		items: [
			{
				question: t("faq_q_what_credits"),
				answer: t("faq_a_what_credits"),
			},
			{
				question: t("faq_q_how_payg"),
				answer: t("faq_a_how_payg"),
			},
			{
				question: t("faq_q_run_out"),
				answer: t("faq_a_run_out"),
			},
			{
				question: t("faq_q_failed_cost"),
				answer: t("faq_a_failed_cost"),
			},
		],
	},
	{
		title: t("faq_sec_connectors"),
		items: [
			{
				question: t("faq_q_how_connectors"),
				answer: t("faq_a_how_connectors"),
			},
			{
				question: t("faq_q_how_crawls"),
				answer: t("faq_a_how_crawls"),
			},
			{
				question: t("faq_q_api_vs_mcp"),
				answer: t("faq_a_api_vs_mcp"),
			},
			{
				question: t("faq_q_what_kb"),
				answer: t("faq_a_what_kb"),
			},
		],
	},
	{
		title: t("faq_sec_ai_agents"),
		items: [
			{
				question: t("faq_q_ai_credit"),
				answer: t("faq_a_ai_credit"),
			},
			{
				question: t("faq_q_agents_extra"),
				answer: t("faq_a_agents_extra"),
			},
			{
				question: t("faq_q_agents_do"),
				answer: t("faq_a_agents_do"),
			},
		],
	},
	{
		title: t("faq_sec_docs"),
		items: [
			{
				question: t("faq_q_doc_cost"),
				answer: t("faq_a_doc_cost"),
			},
			{
				question: t("faq_q_file_types"),
				answer: t("faq_a_file_types"),
			},
			{
				question: t("faq_q_delete_doc"),
				answer: t("faq_a_delete_doc"),
			},
		],
	},
	{
		title: t("faq_sec_self_host"),
		items: [
			{
				question: t("faq_q_self_host_free"),
				answer: t("faq_a_self_host_free"),
			},
			{
				question: t("faq_q_self_vs_cloud"),
				answer: t("faq_a_self_vs_cloud"),
			},
		],
	},
];

const GridLineHorizontal = ({ className, offset }: { className?: string; offset?: string }) => {
	return (
		<div
			style={
				{
					"--background": "#ffffff",
					"--color": "rgba(0, 0, 0, 0.2)",
					"--height": "1px",
					"--width": "5px",
					"--fade-stop": "90%",
					"--offset": offset || "200px",
					"--color-dark": "rgba(255, 255, 255, 0.2)",
					maskComposite: "exclude",
				} as React.CSSProperties
			}
			className={cn(
				"[--background:var(--color-neutral-200)] [--color:var(--color-neutral-400)] dark:[--background:var(--color-neutral-800)] dark:[--color:var(--color-neutral-600)]",
				"absolute left-[calc(var(--offset)/2*-1)] h-(--height) w-[calc(100%+var(--offset))]",
				"bg-[linear-gradient(to_right,var(--color),var(--color)_50%,transparent_0,transparent)]",
				"bg-size-[var(--width)_var(--height)]",
				"[mask:linear-gradient(to_left,var(--background)_var(--fade-stop),transparent),linear-gradient(to_right,var(--background)_var(--fade-stop),transparent),linear-gradient(black,black)]",
				"mask-exclude",
				"z-30",
				"dark:bg-[linear-gradient(to_right,var(--color-dark),var(--color-dark)_50%,transparent_0,transparent)]",
				className
			)}
		/>
	);
};

const GridLineVertical = ({ className, offset }: { className?: string; offset?: string }) => {
	return (
		<div
			style={
				{
					"--background": "#ffffff",
					"--color": "rgba(0, 0, 0, 0.2)",
					"--height": "5px",
					"--width": "1px",
					"--fade-stop": "90%",
					"--offset": offset || "150px",
					"--color-dark": "rgba(255, 255, 255, 0.2)",
					maskComposite: "exclude",
				} as React.CSSProperties
			}
			className={cn(
				"absolute top-[calc(var(--offset)/2*-1)] h-[calc(100%+var(--offset))] w-(--width)",
				"bg-[linear-gradient(to_bottom,var(--color),var(--color)_50%,transparent_0,transparent)]",
				"bg-size-[var(--width)_var(--height)]",
				"[mask:linear-gradient(to_top,var(--background)_var(--fade-stop),transparent),linear-gradient(to_bottom,var(--background)_var(--fade-stop),transparent),linear-gradient(black,black)]",
				"mask-exclude",
				"z-30",
				"dark:bg-[linear-gradient(to_bottom,var(--color-dark),var(--color-dark)_50%,transparent_0,transparent)]",
				className
			)}
		/>
	);
};

function PricingFAQ() {
	const t = useTranslations("pricing");
	const faqData = getFaqData(t);
	const [activeId, setActiveId] = useState<string | null>(null);
	const containerRef = useRef<HTMLDivElement>(null);

	useEffect(() => {
		function handleClickOutside(event: MouseEvent) {
			if (containerRef.current && !containerRef.current.contains(event.target as Node)) {
				setActiveId(null);
			}
		}

		document.addEventListener("mousedown", handleClickOutside);
		return () => document.removeEventListener("mousedown", handleClickOutside);
	}, []);

	const toggleQuestion = (id: string) => {
		setActiveId(activeId === id ? null : id);
	};

	return (
		<div className="mx-auto w-full max-w-4xl overflow-hidden px-4 py-20 md:px-8 md:py-32">
			<FAQJsonLd questions={faqData.flatMap((section) => section.items)} />
			<div className="text-center">
				<h2 className="font-serif text-3xl sm:text-4xl lg:text-5xl font-normal tracking-tight">
					{t("faq_title")}
				</h2>
				<p className="mx-auto mt-3 max-w-2xl text-sm sm:text-base text-muted-foreground font-sans leading-relaxed">
					{t("faq_desc_pre")}{" "}
					<a href="mailto:admin@nowing.com" className="text-brand underline">
						admin@nowing.com
					</a>
				</p>
			</div>

			<div ref={containerRef} className="relative mt-16 flex w-full flex-col gap-12 px-4 md:px-8">
				{faqData.map((section) => (
					<div key={`${section.title}faq`}>
						<h3 className="mb-6 text-lg font-medium text-neutral-800 dark:text-neutral-200">
							{section.title}
						</h3>
						<div className="flex flex-col gap-3">
							{section.items.map((item, index) => {
								const id = `${section.title}-${index}`;
								const isActive = activeId === id;

								return (
									<div
										key={`${id}faq-item`}
										className={cn(
											"relative rounded-lg transition-all duration-200",
											isActive
												? "bg-white shadow-sm ring-1 shadow-black/10 ring-black/10 dark:bg-neutral-900 dark:shadow-white/5 dark:ring-white/10"
												: "hover:bg-neutral-50 dark:hover:bg-neutral-900"
										)}
									>
										{isActive && (
											<div className="absolute inset-0">
												<GridLineHorizontal className="-top-[2px]" offset="100px" />
												<GridLineHorizontal className="-bottom-[2px]" offset="100px" />
												<GridLineVertical className="-left-[2px]" offset="100px" />
												<GridLineVertical className="-right-[2px] left-auto" offset="100px" />
											</div>
										)}
										<Button
											variant="ghost"
											type="button"
											onClick={() => toggleQuestion(id)}
											className="h-auto w-full justify-between rounded-lg px-4 py-4 text-left hover:bg-transparent"
										>
											<span className="text-sm font-medium text-neutral-700 md:text-base dark:text-neutral-300">
												{item.question}
											</span>
											<motion.div
												animate={{ rotate: isActive ? 45 : 0 }}
												transition={{ duration: 0.2 }}
												className="ml-4 shrink-0"
											>
												<IconPlus className="size-5 text-neutral-500 dark:text-neutral-400" />
											</motion.div>
										</Button>
										<AnimatePresence initial={false}>
											{isActive && (
												<motion.div
													initial={{ height: 0, opacity: 0 }}
													animate={{ height: "auto", opacity: 1 }}
													exit={{ height: 0, opacity: 0 }}
													transition={{ duration: 0.15, ease: "easeInOut" }}
													className="relative"
												>
													<p className="max-w-[90%] px-4 pb-4 text-sm text-neutral-600 dark:text-neutral-400">
														{item.answer}
													</p>
												</motion.div>
											)}
										</AnimatePresence>
									</div>
								);
							})}
						</div>
					</div>
				))}
			</div>
		</div>
	);
}

const getUnitRates = (t: (k: string) => string) => [
	{
		service: t("rate_phone_service"),
		platforms: "Batdongsan, Chotot, MuaBan",
		rateCredits: "5 credits",
		rateUsd: "$0.05",
		rateVnd: "1,270 VND",
		billingUnit: t("rate_phone_unit"),
		icon: IconPhoneCall,
	},
	{
		service: t("rate_research_service"),
		platforms: "ChainLens, Web Citations, Synthesizer",
		rateCredits: "2 - 5 credits",
		rateUsd: "$0.02 - $0.05",
		rateVnd: "508 - 1,270 VND",
		billingUnit: t("rate_research_unit"),
		icon: IconSearch,
	},
	{
		service: t("rate_scraping_service"),
		platforms: "Google Maps, TopCV, VietnamWorks, FB",
		rateCredits: "0.1 - 0.5 credits",
		rateUsd: "$0.001 - $0.005",
		rateVnd: "25 - 127 VND",
		billingUnit: t("rate_scraping_unit"),
		icon: IconWorld,
	},
	{
		service: t("rate_doc_service"),
		platforms: "PDF, Office, Financial Statements",
		rateCredits: "0.1 - 1 credit",
		rateUsd: "$0.001 - $0.01",
		rateVnd: "25 - 254 VND",
		billingUnit: t("rate_doc_unit"),
		icon: IconCoins,
	},
];

function PricingUnitRatesTable() {
	const t = useTranslations("pricing");
	const unitRates = getUnitRates(t);
	return (
		<div className="w-full max-w-5xl mx-auto px-4 my-12">
			<div className="text-center mb-8">
				<h3 className="text-2xl md:text-3xl font-bold tracking-tight text-neutral-900 dark:text-white">
					{t("unit_rates_title")}
				</h3>
				<p className="text-sm md:text-base text-neutral-600 dark:text-neutral-400 mt-2 max-w-2xl mx-auto">
					{t("unit_rates_subtitle")}
				</p>
			</div>

			<div className="overflow-hidden rounded-2xl border border-neutral-200 dark:border-neutral-800 bg-white dark:bg-neutral-900 shadow-sm">
				<div className="overflow-x-auto">
					<table className="w-full text-left text-sm">
						<thead className="bg-neutral-50 dark:bg-neutral-800/60 text-xs uppercase font-semibold text-neutral-500 dark:text-neutral-400 border-b border-neutral-200 dark:border-neutral-800">
							<tr>
								<th className="px-6 py-4">{t("th_capability")}</th>
								<th className="px-6 py-4">{t("th_credit_cost")}</th>
								<th className="px-6 py-4">{t("th_usd")}</th>
								<th className="px-6 py-4">{t("th_vnd")}</th>
								<th className="px-6 py-4">{t("th_billing_meter")}</th>
							</tr>
						</thead>
						<tbody className="divide-y divide-neutral-100 dark:divide-neutral-800/80">
							{unitRates.map((rate) => {
								const Icon = rate.icon;
								return (
									<tr
										key={rate.service}
										className="hover:bg-neutral-50/70 dark:hover:bg-neutral-800/40 transition-colors"
									>
										<td className="px-6 py-4">
											<div className="flex items-center gap-3">
												<div className="p-2 rounded-lg bg-emerald-50 dark:bg-emerald-950/40 text-emerald-600 dark:text-emerald-400 border border-emerald-200/50 dark:border-emerald-800/40">
													<Icon className="size-4 shrink-0" />
												</div>
												<div>
													<div className="font-semibold text-neutral-900 dark:text-white">
														{rate.service}
													</div>
													<div className="text-xs text-neutral-500 dark:text-neutral-400">
														{rate.platforms}
													</div>
												</div>
											</div>
										</td>
										<td className="px-6 py-4 font-mono font-semibold text-emerald-600 dark:text-emerald-400">
											{rate.rateCredits}
										</td>
										<td className="px-6 py-4 font-mono text-neutral-800 dark:text-neutral-200">
											{rate.rateUsd}
										</td>
										<td className="px-6 py-4 font-mono text-neutral-500 dark:text-neutral-400">
											{rate.rateVnd}
										</td>
										<td className="px-6 py-4 text-xs text-neutral-600 dark:text-neutral-400">
											{rate.billingUnit}
										</td>
									</tr>
								);
							})}
						</tbody>
					</table>
				</div>
			</div>
		</div>
	);
}

function PartnerBanner() {
	const t = useTranslations("pricing");
	return (
		<div className="w-full max-w-5xl mx-auto px-4 my-16">
			<div className="relative rounded-3xl bg-neutral-900 dark:bg-neutral-950 border border-neutral-800 p-8 md:p-10 shadow-2xl overflow-hidden">
				<div
					className="absolute inset-0 opacity-[0.04] pointer-events-none"
					style={{
						backgroundImage: "radial-gradient(#10b981 1px, transparent 1px)",
						backgroundSize: "20px 20px",
					}}
				/>
				<div className="relative z-10 flex flex-col md:flex-row items-center justify-between gap-6">
					<div className="space-y-2 text-center md:text-left">
						<div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-emerald-500/20 text-emerald-300 text-xs font-semibold uppercase tracking-wider">
							<IconAffiliate className="size-3.5" />
							<span>{t("partner_badge")}</span>
						</div>
						<h4 className="text-2xl md:text-3xl font-bold text-white tracking-tight">
							{t("partner_title")}
						</h4>
						<p className="text-sm text-neutral-400 max-w-xl">
							{t("partner_desc")}
						</p>
					</div>
					<Link href="/partners">
						<Button className="bg-emerald-500 hover:bg-emerald-600 text-neutral-950 font-bold px-6 py-6 rounded-2xl flex items-center gap-2 transition-all shrink-0 shadow-lg shadow-emerald-500/20">
							<span>{t("partner_btn")}</span>
							<IconArrowRight className="size-4" />
						</Button>
					</Link>
				</div>
			</div>
		</div>
	);
}

function PricingBasic() {
	const t = useTranslations("pricing");
	const demoPlans = getDemoPlans(t);
	return (
		<>
			<Pricing
				plans={demoPlans}
				title={t("page_title")}
				description={t("page_description")}
			/>
			<PricingUnitRatesTable />
			<PricingLeadCalculator />
			<PartnerBanner />
			<PricingFAQ />
		</>
	);
}

export default PricingBasic;
