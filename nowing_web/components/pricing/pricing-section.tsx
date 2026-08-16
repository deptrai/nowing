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

const demoPlans = [
	{
		name: "FREE",
		price: "0",
		yearlyPrice: "0",
		period: "",
		billingText: "Self-host free. Run it on your own infrastructure",
		features: [
			"Full platform: connectors, agents, automations, and the MCP server",
			"Unlimited scraping and crawling, you control billing",
			"Bring your own keys for any model provider",
			"Keep competitive research on your own infrastructure",
			"Community support on Discord",
		],
		description: "",
		buttonText: "View on GitHub",
		href: "https://github.com/deptrai/nowing",
		isPopular: false,
	},
	{
		name: "PAY AS YOU GO",
		price: "5",
		yearlyPrice: "5",
		period: "to start",
		billingText: "Your first $5 of credit is free. No subscription, ever",
		features: [
			"$5 of free credit to start, one balance for everything",
			"Platform connectors: Reddit, YouTube, TikTok, Amazon, Google Maps, Google Search, and the open web",
			"Call every connector as a REST API with your key or through the MCP server",
			"Pay per item returned and per page crawled. Failed calls are never billed",
			"Premium models like GPT-5.5, Claude Sonnet 5, Gemini 3.1 Pro billed at provider cost",
			"Scheduled and event-triggered agents for briefs, alerts, and monitoring",
			"Write results back to Notion, Slack, Linear, and Jira",
			"Add credit any time. $1 buys $1 of credit, with optional automatic refills",
			"Priority support on Discord",
		],
		description: "",
		buttonText: "Get Started",
		href: "/login",
		isPopular: true,
	},
	{
		name: "ENTERPRISE",
		price: "Contact Us",
		yearlyPrice: "Contact Us",
		period: "",
		billingText: "",
		features: [
			"Everything in Pay As You Go",
			"Custom connectors and agent workflows",
			"On-prem or VPC deployment",
			"Audit logs and compliance",
			"SSO, OIDC & SAML",
			"White-glove setup and deployment",
			"Monthly managed updates and maintenance",
			"SLA commitments",
			"Dedicated support",
		],
		description: "Customized setup for large organizations",
		buttonText: "Contact Sales",
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

const faqData: FAQSection[] = [
	{
		title: "Credits & Pay As You Go",
		items: [
			{
				question: "What are credits in Nowing?",
				answer:
					"Credits are a single prepaid balance shown in dollars that powers everything in Nowing: platform connector calls, web crawls, document processing, and premium AI models. New accounts start with $5 of free credit. There is one number to watch, and it only moves when you actually use the product.",
			},
			{
				question: "How does Pay As You Go work?",
				answer:
					"There is no monthly subscription. Start with $5 of free credit, and when you need more, add any amount. $1 buys exactly $1 of credit, added to your balance immediately. You can enable automatic refills when your balance runs low, and turn them off any time.",
			},
			{
				question: "What happens if I run out of credit?",
				answer:
					"Nowing checks your balance before every billable call, so your wallet can never go negative. When credit runs out, connector calls, crawls, premium model requests, and document processing pause until you top up. Free models and connectors that do not consume credit keep working.",
			},
			{
				question: "Do failed scrapes or crawls cost anything?",
				answer:
					"No. Platform connectors bill per item actually returned, and web crawls bill per page successfully fetched. A request that errors, times out, or comes back empty is not charged. You pay for data you receive, not for attempts.",
			},
		],
	},
	{
		title: "Connector & Scraping Pricing",
		items: [
			{
				question: "How are platform connectors billed?",
				answer:
					"Each platform connector meters per item returned: a Reddit post or comment, a Google Search results page, a Google Maps place or review, a YouTube video or comment. Rates are fractions of a cent per item and are debited from your credit balance after the call succeeds, so your $5 of free credit covers hundreds of items.",
			},
			{
				question: "How much does web crawling cost?",
				answer:
					"Web crawls are billed per successfully fetched page at a fraction of a cent, so $1 of credit covers hundreds of pages. Pages that fail to load are never charged. Crawled pages can feed your agents directly or be indexed into your knowledge base for later questions.",
			},
			{
				question: "Does the REST API cost the same as the MCP server?",
				answer:
					"Yes. Whether your own app calls a connector with your Nowing API key or your agent calls it as a tool through the MCP server, it is the same endpoint, the same per-item rate, and the same credit balance. There is no separate API plan or seat fee.",
			},
			{
				question: "What can I add to the knowledge base?",
				answer:
					"You can upload files directly or sync documents from Google Drive, OneDrive, and Dropbox. Crawled pages can also be indexed for later questions. Document files are billed per page processed; connecting the drives themselves costs nothing.",
			},
		],
	},
	{
		title: "Premium AI, Agents & Automations",
		items: [
			{
				question: "How is credit used for premium AI?",
				answer:
					"The same balance pays for premium AI models like GPT-5.5, Claude Sonnet 5, and Gemini 3.1 Pro, plus over 100 more via OpenRouter, and for premium features such as image generation, podcasts, and video presentations. Each request debits the actual USD provider cost, so cheaper models bill proportionally less.",
			},
			{
				question: "Do agents and automations cost extra?",
				answer:
					"No. There is no add-on fee for agents or automations. A scheduled research brief or an event-triggered alert draws from the same credit balance: connector items and crawled pages at their per-unit rates, and model usage at provider cost. A workflow that uses free models and no scraping costs nothing.",
			},
			{
				question: "What can the agents actually do?",
				answer:
					"You describe the job in plain English and Nowing sets up the agent, no code needed. Agents can watch any page for changes, track mentions on Reddit and YouTube, monitor Google rankings and Maps reviews, then turn what they find into briefs and alerts, and write results back to Notion, Slack, Linear, and Jira.",
			},
		],
	},
	{
		title: "Documents & Knowledge Base",
		items: [
			{
				question: "How much does document processing cost?",
				answer:
					"Document processing is billed per page from your credit balance. Basic mode costs $0.001 per page and Premium mode costs $0.01 per page, with Premium using advanced extraction for complex financial, medical, and legal layouts. Pages in Word, PowerPoint, and Excel files are estimated automatically, and every file uses at least 1 page.",
			},
			{
				question: "Which file types use credit?",
				answer:
					"Only document files that need processing: PDFs, Word documents, presentations, spreadsheets, ebooks, and images. Plain text, code, Markdown, CSV, HTML, audio, and video files are indexed free. Duplicate documents are detected automatically and never charged twice.",
			},
			{
				question: "If I delete a document, do I get my credit back?",
				answer:
					"No. Deleting a document removes it from your knowledge base, but the credit it used is not refunded. Credit tracks your total usage over time, not how much is currently stored, so once credit is spent it stays spent even if you later remove the document.",
			},
		],
	},
	{
		title: "Self-Hosting",
		items: [
			{
				question: "Is the self-hosted version really free and unlimited?",
				answer:
					"Yes. Nowing is open-core, and the default self-hosted configuration ships with all credit billing switched off. Scraping, crawling, document processing, and agent runs are limited only by your own infrastructure and the model provider keys you bring.",
			},
			{
				question: "What is the difference between self-hosted and cloud?",
				answer:
					"Both run the same platform: connectors, agents, automations, and the MCP server. Cloud is zero-setup with managed infrastructure and metered pay-as-you-go credit. Self-hosted runs on your machines with your own model keys, keeps competitive research fully in-house, and leaves billing under your control.",
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
					Frequently Asked Questions
				</h2>
				<p className="mx-auto mt-3 max-w-2xl text-sm sm:text-base text-muted-foreground font-sans leading-relaxed">
					Everything you need to know about Nowing credits and billing. Can&apos;t find what you
					need? Reach out at{" "}
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

const unitRates = [
	{
		service: "Real Estate Phone Number Unlock",
		platforms: "Batdongsan, Chotot, MuaBan",
		rateCredits: "5 credits",
		rateUsd: "$0.05",
		rateVnd: "1,270 VND",
		billingUnit: "Per successfully verified phone",
		icon: IconPhoneCall,
	},
	{
		service: "Autonomous Deep Research & Briefs",
		platforms: "ChainLens, Web Citations, Synthesizer",
		rateCredits: "2 - 5 credits",
		rateUsd: "$0.02 - $0.05",
		rateVnd: "508 - 1,270 VND",
		billingUnit: "Per complete research run",
		icon: IconSearch,
	},
	{
		service: "B2B & Social Data Scrapers",
		platforms: "Google Maps, TopCV, VietnamWorks, FB",
		rateCredits: "0.1 - 0.5 credits",
		rateUsd: "$0.001 - $0.005",
		rateVnd: "25 - 127 VND",
		billingUnit: "Per item / profile returned",
		icon: IconWorld,
	},
	{
		service: "Document Parsing & Table OCR",
		platforms: "PDF, Office, Financial Statements",
		rateCredits: "0.1 - 1 credit",
		rateUsd: "$0.001 - $0.01",
		rateVnd: "25 - 254 VND",
		billingUnit: "Per page extracted (text files free)",
		icon: IconCoins,
	},
];

function PricingUnitRatesTable() {
	return (
		<div className="w-full max-w-5xl mx-auto px-4 my-12">
			<div className="text-center mb-8">
				<h3 className="text-2xl md:text-3xl font-bold tracking-tight text-neutral-900 dark:text-white">
					Transparent Pay-As-You-Go Unit Rates
				</h3>
				<p className="text-sm md:text-base text-neutral-600 dark:text-neutral-400 mt-2 max-w-2xl mx-auto">
					No hidden multipliers or bloated seat fees. $1 buys exactly $1 worth of platform credits.
					Failed queries or empty results are never billed.
				</p>
			</div>

			<div className="overflow-hidden rounded-2xl border border-neutral-200 dark:border-neutral-800 bg-white dark:bg-neutral-900 shadow-sm">
				<div className="overflow-x-auto">
					<table className="w-full text-left text-sm">
						<thead className="bg-neutral-50 dark:bg-neutral-800/60 text-xs uppercase font-semibold text-neutral-500 dark:text-neutral-400 border-b border-neutral-200 dark:border-neutral-800">
							<tr>
								<th className="px-6 py-4">Capability & Platform</th>
								<th className="px-6 py-4">Credit Cost</th>
								<th className="px-6 py-4">USD Equivalent</th>
								<th className="px-6 py-4">VND Equivalent</th>
								<th className="px-6 py-4">Billing Meter</th>
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
							<span>Nowing Affiliate & Partner Program</span>
						</div>
						<h4 className="text-2xl md:text-3xl font-bold text-white tracking-tight">
							Earn 15% Lifetime Recurring Commission
						</h4>
						<p className="text-sm text-neutral-400 max-w-xl">
							Introduce Nowing to your clients, agency network, or sales team. Get paid 15%
							recurring lifetime commissions with instant VietQR Napas 24/7 payouts or +10% platform
							credit bonus.
						</p>
					</div>
					<Link href="/partners">
						<Button className="bg-emerald-500 hover:bg-emerald-600 text-neutral-950 font-bold px-6 py-6 rounded-2xl flex items-center gap-2 transition-all shrink-0 shadow-lg shadow-emerald-500/20">
							<span>Become a Partner</span>
							<IconArrowRight className="size-4" />
						</Button>
					</Link>
				</div>
			</div>
		</div>
	);
}

function PricingBasic() {
	return (
		<>
			<Pricing
				plans={demoPlans}
				title="Nowing Pricing"
				description="Give your agents the live web. Self-host for free, or start with $5 of credit and pay as you go. No subscriptions."
			/>
			<PricingUnitRatesTable />
			<PricingLeadCalculator />
			<PartnerBanner />
			<PricingFAQ />
		</>
	);
}

export default PricingBasic;
