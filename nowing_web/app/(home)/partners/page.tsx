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
import { getTranslations } from "next-intl/server";
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

const valueProps = (t: (k: string) => string) => [
	{
		title: t("vp1_title"),
		description: t("vp1_desc"),
		icon: IconChartLine,
	},
	{
		title: t("vp2_title"),
		description: t("vp2_desc"),
		icon: IconQrcode,
	},
	{
		title: t("vp3_title"),
		description: t("vp3_desc"),
		icon: IconCoins,
	},
	{
		title: t("vp4_title"),
		description: t("vp4_desc"),
		icon: IconDeviceDesktopAnalytics,
	},
	{
		title: t("vp5_title"),
		description: t("vp5_desc"),
		icon: IconShieldCheck,
	},
	{
		title: t("vp6_title"),
		description: t("vp6_desc"),
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

export default async function PartnersPage() {
	const t = await getTranslations("partners");
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
					<IconAffiliate
						className="size-4 text-emerald-600 dark:text-emerald-400"
						aria-hidden="true"
					/>
					<span>{t("hero_badge")}</span>
				</div>

				<h1 className="font-serif text-3xl sm:text-4xl md:text-5xl lg:text-6xl font-normal tracking-tight text-neutral-900 dark:text-white max-w-4xl mx-auto leading-tight">
					{t.rich("hero_title", {
						i: (c) => <span className="text-emerald-600 dark:text-emerald-400 italic">{c}</span>,
					})}
				</h1>

				<p className="mt-4 text-sm sm:text-base md:text-lg text-neutral-600 dark:text-neutral-300 max-w-3xl mx-auto font-sans leading-relaxed">
					{t("hero_subtitle")}
				</p>

				<div className="mt-8 flex flex-col sm:flex-row items-center justify-center gap-3">
					<Link href="/partners/dashboard">
						<Button className="w-full sm:w-auto bg-emerald-500 hover:bg-emerald-600 text-neutral-950 font-bold px-6 py-5 rounded-xl flex items-center justify-center gap-2 text-sm transition-all shadow-lg shadow-emerald-500/20">
							<span>{t("cta_dashboard")}</span>
							<IconArrowRight className="size-4" aria-hidden="true" />
						</Button>
					</Link>
					<Link href="/pricing">
						<Button variant="outline" className="w-full sm:w-auto px-6 py-5 rounded-xl text-sm">
							{t("cta_pricing")}
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
						{t("why_title")}
					</h2>
					<p className="text-neutral-600 dark:text-neutral-400 mt-2 text-base max-w-2xl mx-auto">
						{t("why_subtitle")}
					</p>
				</div>

				<div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
					{valueProps(t).map((prop) => {
						const Icon = prop.icon;
						return (
							<div
								key={prop.title}
								className="p-6 rounded-3xl border border-neutral-200/80 dark:border-neutral-800 bg-white/60 dark:bg-neutral-900/60 backdrop-blur-xs shadow-xs hover:border-emerald-400/60 transition-all group"
							>
								<div className="p-3 w-fit rounded-2xl bg-emerald-50 dark:bg-emerald-950/50 text-emerald-600 dark:text-emerald-400 border border-emerald-200/60 dark:border-emerald-800/40 mb-4 group-hover:scale-110 transition-transform">
									<Icon className="size-6" aria-hidden="true" />
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
						<IconBuildingBank
							className="size-5 text-emerald-600 dark:text-emerald-400"
							aria-hidden="true"
						/>
						<span>{t("banks_title")}</span>
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
						{t("how_title")}
					</h2>
				</div>

				<div className="grid grid-cols-1 md:grid-cols-3 gap-8">
					<div className="p-6 rounded-3xl border border-neutral-200 dark:border-neutral-800 bg-white dark:bg-neutral-900 text-center relative">
						<div className="size-10 rounded-full bg-emerald-500 text-neutral-950 font-black text-lg flex items-center justify-center mx-auto mb-4">
							1
						</div>
						<h3 className="font-bold text-lg mb-2">{t("step1_title")}</h3>
						<p className="text-sm text-neutral-600 dark:text-neutral-400">{t("step1_desc")}</p>
					</div>

					<div className="p-6 rounded-3xl border border-neutral-200 dark:border-neutral-800 bg-white dark:bg-neutral-900 text-center relative">
						<div className="size-10 rounded-full bg-emerald-500 text-neutral-950 font-black text-lg flex items-center justify-center mx-auto mb-4">
							2
						</div>
						<h3 className="font-bold text-lg mb-2">{t("step2_title")}</h3>
						<p className="text-sm text-neutral-600 dark:text-neutral-400">{t("step2_desc")}</p>
					</div>

					<div className="p-6 rounded-3xl border border-neutral-200 dark:border-neutral-800 bg-white dark:bg-neutral-900 text-center relative">
						<div className="size-10 rounded-full bg-emerald-500 text-neutral-950 font-black text-lg flex items-center justify-center mx-auto mb-4">
							3
						</div>
						<h3 className="font-bold text-lg mb-2">{t("step3_title")}</h3>
						<p className="text-sm text-neutral-600 dark:text-neutral-400">{t("step3_desc")}</p>
					</div>
				</div>
			</div>

			{/* Bottom CTA Banner */}
			<div className="max-w-5xl mx-auto px-4 mt-20">
				<div className="rounded-3xl bg-emerald-600 text-white p-10 md:p-14 text-center relative overflow-hidden shadow-2xl">
					<h3 className="text-3xl md:text-4xl font-extrabold tracking-tight mb-4">
						{t("cta_title")}
					</h3>
					<p className="text-emerald-100 text-base md:text-lg max-w-2xl mx-auto mb-8">
						{t("cta_subtitle")}
					</p>
					<Link href="/partners/dashboard">
						<Button className="bg-neutral-950 hover:bg-neutral-900 text-white font-bold px-8 py-6 rounded-2xl text-base shadow-xl">
							{t("cta_button")}
						</Button>
					</Link>
				</div>
			</div>
		</div>
	);
}
