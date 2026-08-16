import {
	IconAffiliate,
	IconArrowRight,
	IconBuildingBank,
	IconChartLine,
	IconCoins,
	IconDeviceDesktopAnalytics,
	IconQrcode,
	IconShieldCheck,
	IconSparkles,
} from "@tabler/icons-react";
import type { Metadata } from "next";
import Link from "next/link";
import { PartnerEarningsCalculator } from "@/components/partners/PartnerEarningsCalculator";
import { JsonLd } from "@/components/seo/json-ld";
import { Button } from "@/components/ui/button";

const canonicalUrl = "https://nowing.net/partners";
const metaTitle = "Nowing Affiliate Partner Program: 15% Lifetime Commission & VietQR Payouts";
const metaDescription =
	"Earn 15% lifetime recurring commission on all platform credit purchases made by your referrals. Instant Napas 24/7 VietQR payouts or +10% platform credit bonus.";

export const metadata: Metadata = {
	title: metaTitle,
	description: metaDescription,
	keywords: [
		"nowing affiliate program",
		"saas partner program vietnam",
		"15% recurring affiliate commission",
		"vietqr payout affiliate",
		"ai agent affiliate program",
		"lead intelligence partner",
	],
	alternates: {
		canonical: canonicalUrl,
	},
	openGraph: {
		title: metaTitle,
		description: metaDescription,
		url: canonicalUrl,
		siteName: "Nowing",
		type: "website",
		images: [{ url: "/og-image.png", width: 1200, height: 630, alt: "Nowing Affiliate Program" }],
	},
	twitter: {
		card: "summary_large_image",
		title: metaTitle,
		description: metaDescription,
		images: ["/og-image.png"],
	},
};

const valueProps = [
	{
		title: "15% Lifetime Recurring Commission",
		description:
			"You earn 15% on every credit purchase made by your referred users, for as long as they use Nowing. No expiration dates or caps.",
		icon: IconChartLine,
	},
	{
		title: "Instant VietQR Napas 24/7 Payouts",
		description:
			"Withdraw directly to your Vietnamese bank account (VCB, TCB, MB, ACB, etc.) in seconds with zero transaction fees.",
		icon: IconQrcode,
	},
	{
		title: "+10% Credit Wallet Conversion",
		description:
			"Choose to convert commissions directly into platform credits with an automatic +10% bonus for your agency outreach campaigns.",
		icon: IconCoins,
	},
	{
		title: "Transparent Realtime Ledger",
		description:
			"Track link clicks, signups, and exact commission amounts in realtime through our dedicated partner dashboard.",
		icon: IconDeviceDesktopAnalytics,
	},
	{
		title: "30-Day Cookie Attribution",
		description:
			"Visitors who click your link are tracked for 30 days. Even if they sign up weeks later, you receive full credit.",
		icon: IconShieldCheck,
	},
	{
		title: "Marketing Assets & Support",
		description:
			"Access ready-to-use banners, case studies, product videos, and dedicated partner support on Discord.",
		icon: IconSparkles,
	},
];

const supportedBanks = [
	"Vietcombank",
	"Techcombank",
	"MBBank",
	"VietinBank",
	"BIDV",
	"ACB",
	"VPBank",
	"TPBank",
	"Sacombank",
	"VIB",
	"HDBank",
	"Agribank",
];

export default function PartnersPage() {
	return (
		<div className="relative min-h-screen pb-24 overflow-hidden">
			<JsonLd
				data={{
					"@context": "https://schema.org",
					"@type": "WebPage",
					name: metaTitle,
					description: metaDescription,
					url: canonicalUrl,
				}}
			/>

			{/* Hero Section */}
			<div className="relative pt-16 md:pt-24 pb-12 px-4 sm:px-6 lg:px-8 max-w-6xl mx-auto text-center">
				<div className="inline-flex items-center gap-2 px-4 py-1.5 rounded-full bg-emerald-100 dark:bg-emerald-950/60 border border-emerald-300/60 dark:border-emerald-800/60 text-emerald-800 dark:text-emerald-300 text-xs md:text-sm font-semibold uppercase tracking-wider mb-6">
					<IconAffiliate className="size-4 text-emerald-600 dark:text-emerald-400" />
					<span>Official Affiliate & Agency Partner Program</span>
				</div>

				<h1 className="font-serif text-3xl sm:text-4xl md:text-5xl lg:text-6xl font-normal tracking-tight text-neutral-900 dark:text-white max-w-4xl mx-auto leading-tight">
					Earn{" "}
					<span className="text-emerald-600 dark:text-emerald-400 italic">
						15% Lifetime Recurring
					</span>{" "}
					Commission
				</h1>

				<p className="mt-4 text-sm sm:text-base md:text-lg text-neutral-600 dark:text-neutral-300 max-w-3xl mx-auto font-sans leading-relaxed">
					Recommend Nowing’s AI Agents, B2B Scrapers & Phone Unlock Engine to your clients, agency
					network, or sales audience. Receive passive payouts via VietQR Napas 24/7 on every single
					top-up.
				</p>

				<div className="mt-8 flex flex-col sm:flex-row items-center justify-center gap-3">
					<Link href="/partners/dashboard">
						<Button className="w-full sm:w-auto bg-emerald-500 hover:bg-emerald-600 text-neutral-950 font-bold px-6 py-5 rounded-xl flex items-center justify-center gap-2 text-sm transition-all shadow-lg shadow-emerald-500/20">
							<span>Go to Partner Dashboard</span>
							<IconArrowRight className="size-4" />
						</Button>
					</Link>
					<Link href="/pricing">
						<Button variant="outline" className="w-full sm:w-auto px-6 py-5 rounded-xl text-sm">
							Explore Platform Pricing ($0 Free Tier)
						</Button>
					</Link>
				</div>
			</div>

			{/* Interactive Earnings Calculator */}
			<PartnerEarningsCalculator />

			{/* Value Propositions Grid */}
			<div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 my-20">
				<div className="text-center mb-12">
					<h2 className="font-serif text-2xl sm:text-3xl lg:text-4xl font-normal tracking-tight text-neutral-900 dark:text-white">
						Why Partner with Nowing?
					</h2>
					<p className="text-neutral-600 dark:text-neutral-400 mt-2 text-base max-w-2xl mx-auto">
						Built from the ground up to empower Vietnamese and international growth agencies,
						creators, and sales consultants.
					</p>
				</div>

				<div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
					{valueProps.map((prop) => {
						const Icon = prop.icon;
						return (
							<div
								key={prop.title}
								className="p-6 rounded-3xl border border-neutral-200/80 dark:border-neutral-800 bg-white/60 dark:bg-neutral-900/60 backdrop-blur-xs shadow-xs hover:border-emerald-400/60 transition-all group"
							>
								<div className="p-3 w-fit rounded-2xl bg-emerald-50 dark:bg-emerald-950/50 text-emerald-600 dark:text-emerald-400 border border-emerald-200/60 dark:border-emerald-800/40 mb-4 group-hover:scale-110 transition-transform">
									<Icon className="size-6" />
								</div>
								<h3 className="text-lg font-bold text-neutral-900 dark:text-white mb-2">
									{prop.title}
								</h3>
								<p className="text-sm text-neutral-600 dark:text-neutral-400 leading-relaxed">
									{prop.description}
								</p>
							</div>
						);
					})}
				</div>
			</div>

			{/* Supported Banks Banner */}
			<div className="max-w-5xl mx-auto px-4 my-16">
				<div className="rounded-3xl border border-neutral-200 dark:border-neutral-800 bg-neutral-50 dark:bg-neutral-900/40 p-8 text-center">
					<div className="flex items-center justify-center gap-2 text-neutral-700 dark:text-neutral-300 font-semibold mb-4 text-sm md:text-base">
						<IconBuildingBank className="size-5 text-emerald-600 dark:text-emerald-400" />
						<span>Supported VietQR Napas 24/7 Banks for Instant Payouts</span>
					</div>
					<div className="flex flex-wrap items-center justify-center gap-2 md:gap-3">
						{supportedBanks.map((bank) => (
							<span
								key={bank}
								className="px-3.5 py-1.5 rounded-xl bg-white dark:bg-neutral-800 border border-neutral-200 dark:border-neutral-700/70 text-neutral-800 dark:text-neutral-200 text-xs font-medium shadow-2xs"
							>
								{bank}
							</span>
						))}
					</div>
				</div>
			</div>

			{/* Simple 3-Step Flow */}
			<div className="max-w-5xl mx-auto px-4 my-20">
				<div className="text-center mb-12">
					<h2 className="text-3xl font-bold tracking-tight text-neutral-900 dark:text-white">
						How It Works in 3 Steps
					</h2>
				</div>

				<div className="grid grid-cols-1 md:grid-cols-3 gap-8">
					<div className="p-6 rounded-3xl border border-neutral-200 dark:border-neutral-800 bg-white dark:bg-neutral-900 text-center relative">
						<div className="size-10 rounded-full bg-emerald-500 text-neutral-950 font-black text-lg flex items-center justify-center mx-auto mb-4">
							1
						</div>
						<h3 className="font-bold text-lg mb-2">Create Partner Account</h3>
						<p className="text-sm text-neutral-600 dark:text-neutral-400">
							Claim your unique referral code in 5 seconds and generate your custom referral link
							and QR code.
						</p>
					</div>

					<div className="p-6 rounded-3xl border border-neutral-200 dark:border-neutral-800 bg-white dark:bg-neutral-900 text-center relative">
						<div className="size-10 rounded-full bg-emerald-500 text-neutral-950 font-black text-lg flex items-center justify-center mx-auto mb-4">
							2
						</div>
						<h3 className="font-bold text-lg mb-2">Share With Your Network</h3>
						<p className="text-sm text-neutral-600 dark:text-neutral-400">
							Recommend Nowing to real estate brokers, sales leads, digital marketers, and agencies
							looking for automated intelligence.
						</p>
					</div>

					<div className="p-6 rounded-3xl border border-neutral-200 dark:border-neutral-800 bg-white dark:bg-neutral-900 text-center relative">
						<div className="size-10 rounded-full bg-emerald-500 text-neutral-950 font-black text-lg flex items-center justify-center mx-auto mb-4">
							3
						</div>
						<h3 className="font-bold text-lg mb-2">Earn & Withdraw 24/7</h3>
						<p className="text-sm text-neutral-600 dark:text-neutral-400">
							Receive 15% lifetime recurring commissions on every credit pack they purchase.
							Withdraw to your bank in seconds.
						</p>
					</div>
				</div>
			</div>

			{/* Bottom CTA Banner */}
			<div className="max-w-5xl mx-auto px-4 mt-20">
				<div className="rounded-3xl bg-emerald-600 text-white p-10 md:p-14 text-center relative overflow-hidden shadow-2xl">
					<h3 className="text-3xl md:text-4xl font-extrabold tracking-tight mb-4">
						Ready to Start Earning with Nowing?
					</h3>
					<p className="text-emerald-100 text-base md:text-lg max-w-2xl mx-auto mb-8">
						Join dozens of agencies and creators monetizing their networks with our high-retention
						AI lead intelligence platform.
					</p>
					<Link href="/partners/dashboard">
						<Button className="bg-neutral-950 hover:bg-neutral-900 text-white font-bold px-8 py-6 rounded-2xl text-base shadow-xl">
							Get Your Partner Link Today
						</Button>
					</Link>
				</div>
			</div>
		</div>
	);
}
