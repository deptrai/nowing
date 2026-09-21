import { SquareArrowOutUpRight } from "lucide-react";
import type { Metadata } from "next";
import Link from "next/link";
import { getTranslations } from "next-intl/server";
import { AdUnit } from "@/components/ads/ad-unit";
import { ADSENSE_SLOTS } from "@/components/ads/adsense-config";
import { FAQJsonLd, JsonLd } from "@/components/seo/json-ld";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import {
	Table,
	TableBody,
	TableCell,
	TableHead,
	TableHeader,
	TableRow,
} from "@/components/ui/table";
import type { AnonModel } from "@/contracts/types/anonymous-chat.types";
import { SERVER_BACKEND_URL } from "@/lib/env-config";

export async function generateMetadata(): Promise<Metadata> {
	const t = await getTranslations("free");
	return {
		title: t("meta_title"),
		description: t("meta_description"),
		keywords: [
			"chatgpt free",
			"chat gpt free",
			"free chatgpt",
			"free chat gpt",
			"chatgpt online",
			"chat gpt online",
			"online chatgpt",
			"chatgpt free online",
			"chatgpt online free",
			"chat gpt free online",
			"chatgpt no login",
			"chatgpt without login",
			"chat gpt login free",
			"chat gpt login",
			"free chatgpt without login",
			"free chatgpt no login",
			"ai chat no login",
			"ai chat without login",
			"claude ai without login",
			"claude no login",
			"chatgpt for free",
			"gpt chat free",
			"claude ai free",
			"claude free",
			"free claude ai",
			"free claude",
			"ai like chatgpt",
			"sites like chatgpt",
			"free ai chatbot like chatgpt",
			"free ai chatbots like chatgpt",
			"apps like chatgpt for free",
			"best free alternative to chatgpt",
			"free ai apps",
			"ai with no restrictions",
			"open core research memory",
			"long-term research memory",
		],
		alternates: {
			canonical: "https://www.nowing.com/free",
		},
		openGraph: {
			title: t("meta_title"),
			description: t("meta_og_description"),
			url: "https://www.nowing.com/free",
			siteName: "Nowing",
			type: "website",
			images: [
				{
					url: "/og-image.png",
					width: 1200,
					height: 630,
					alt: "Nowing - ChatGPT Free Online, Claude AI Free, No Login Required",
				},
			],
		},
		twitter: {
			card: "summary_large_image",
			title: t("meta_title"),
			description: t("meta_twitter_description"),
			images: ["/og-image.png"],
		},
	};
}

async function getModels(): Promise<AnonModel[]> {
	try {
		const res = await fetch(`${SERVER_BACKEND_URL}/api/v1/public/anon-chat/models`, {
			next: { revalidate: 300 },
		});
		if (!res.ok) return [];
		return res.json();
	} catch {
		return [];
	}
}

export default async function FreeHubPage() {
	const t = await getTranslations("free");
	const models = await getModels();
	const seoModels = models.filter((m) => m.seo_slug);
	const faqKeys = ["faq1", "faq2", "faq3", "faq4", "faq5", "faq6", "faq7", "faq8", "faq9"];
	const faqItems = faqKeys.map((k) => ({ question: t(`${k}_q`), answer: t(`${k}_a`) }));

	return (
		<div className="min-h-screen pt-20">
			<JsonLd
				data={{
					"@context": "https://schema.org",
					"@type": "CollectionPage",
					name: "ChatGPT Free Online Without Login - Nowing",
					description:
						"Use ChatGPT, Claude AI, Gemini and more AI models free online without login or sign-up. Open-core long-term research memory for AI agents with no login required.",
					url: "https://www.nowing.com/free",
					isPartOf: { "@type": "WebSite", name: "Nowing", url: "https://www.nowing.com" },
					mainEntity: {
						"@type": "ItemList",
						numberOfItems: seoModels.length,
						itemListElement: seoModels.map((m, i) => ({
							"@type": "ListItem",
							position: i + 1,
							name: m.name,
							url: `https://www.nowing.com/free/${m.seo_slug}`,
						})),
					},
				}}
			/>
			<FAQJsonLd questions={faqItems} />

			<article className="container mx-auto px-4 pb-20">
				{/* Hero */}
				<section className="mt-8 text-center max-w-3xl mx-auto">
					<h1 className="font-serif text-3xl sm:text-4xl md:text-5xl font-normal tracking-tight">
						{t("hero_title")}
					</h1>
					<p className="mt-3 text-sm sm:text-base text-muted-foreground max-w-2xl mx-auto font-sans leading-relaxed">
						{t("hero_sub")}
					</p>
					<div className="flex flex-wrap items-center justify-center gap-2 mt-6">
						<Badge variant="secondary" className="px-2.5 py-1 text-xs">
							{t("badge_no_login")}
						</Badge>
						<Badge variant="secondary" className="px-2.5 py-1 text-xs">
							{t("badge_tokens")}
						</Badge>
						<Badge variant="secondary" className="px-2.5 py-1 text-xs">
							{t("badge_models", { count: seoModels.length })}
						</Badge>
						<Badge variant="secondary" className="px-2.5 py-1 text-xs">
							{t("badge_opencore")}
						</Badge>
					</div>
				</section>

				<Separator className="my-12 max-w-4xl mx-auto" />

				{/* In-content ad: above the model table */}
				<aside
					aria-label={t("aria_advertisement")}
					className="max-w-4xl mx-auto mb-8 min-h-[100px]"
				>
					<AdUnit slot={ADSENSE_SLOTS.freeHubInContent} />
				</aside>

				{/* Model Table */}
				{seoModels.length > 0 ? (
					<section className="max-w-4xl mx-auto" aria-label={t("aria_free_models")}>
						<h2 className="font-serif text-2xl sm:text-3xl font-normal mb-2">{t("table_title")}</h2>
						<p className="text-sm text-muted-foreground mb-6">{t("table_sub")}</p>

						<div className="overflow-hidden rounded-lg border">
							<Table>
								<TableHeader>
									<TableRow>
										<TableHead className="w-[45%]">{t("col_model")}</TableHead>
										<TableHead>{t("col_provider")}</TableHead>
										<TableHead>{t("col_tier")}</TableHead>
										<TableHead className="text-right w-[100px]" />
									</TableRow>
								</TableHeader>
								<TableBody>
									{seoModels.map((model) => (
										<TableRow key={model.id}>
											<TableCell>
												<Link
													href={`/free/${model.seo_slug}`}
													className="group flex flex-col gap-0.5"
												>
													<span className="font-medium group-hover:underline">{model.name}</span>
												</Link>
											</TableCell>
											<TableCell>
												<Badge variant="outline">{model.provider}</Badge>
											</TableCell>
											<TableCell>
												{model.is_premium ? (
													<Badge className="bg-purple-100 text-purple-700 dark:bg-purple-900/50 dark:text-purple-300 border-0">
														{t("tier_premium")}
													</Badge>
												) : (
													<Badge variant="secondary">{t("tier_free")}</Badge>
												)}
											</TableCell>
											<TableCell className="text-right">
												<Button variant="ghost" size="sm" asChild>
													<Link href={`/free/${model.seo_slug}`}>
														{t("chat_link")}
														<SquareArrowOutUpRight className="size-3" aria-hidden="true" />
													</Link>
												</Button>
											</TableCell>
										</TableRow>
									))}
								</TableBody>
							</Table>
						</div>
					</section>
				) : (
					<section className="mt-12 text-center max-w-4xl mx-auto">
						<p className="text-muted-foreground">{t("no_models")}</p>
					</section>
				)}

				<Separator className="my-12 max-w-4xl mx-auto" />

				{/* Why Nowing */}
				<section className="max-w-4xl mx-auto">
					<h2 className="text-2xl font-bold mb-6">{t("why_title")}</h2>
					<div className="grid grid-cols-1 md:grid-cols-3 gap-6">
						<div className="rounded-lg border bg-card p-5">
							<h3 className="font-semibold mb-1.5">{t("why1_title")}</h3>
							<p className="text-sm text-muted-foreground leading-relaxed">{t("why1_desc")}</p>
						</div>
						<div className="rounded-lg border bg-card p-5">
							<h3 className="font-semibold mb-1.5">{t("why2_title")}</h3>
							<p className="text-sm text-muted-foreground leading-relaxed">{t("why2_desc")}</p>
						</div>
						<div className="rounded-lg border bg-card p-5">
							<h3 className="font-semibold mb-1.5">{t("why3_title")}</h3>
							<p className="text-sm text-muted-foreground leading-relaxed">{t("why3_desc")}</p>
						</div>
					</div>
				</section>

				<Separator className="my-12 max-w-4xl mx-auto" />

				{/* CTA */}
				<section className="max-w-3xl mx-auto text-center">
					<h2 className="text-2xl font-bold mb-3">{t("cta_title")}</h2>
					<p className="text-muted-foreground mb-6 leading-relaxed">{t("cta_desc")}</p>
					<Button size="lg" asChild>
						<Link href="/register">{t("cta_button")}</Link>
					</Button>
				</section>

				<Separator className="my-12 max-w-4xl mx-auto" />

				{/* In-content ad: after CTA, before FAQ */}
				<aside
					aria-label={t("aria_advertisement")}
					className="max-w-3xl mx-auto my-8 min-h-[100px]"
				>
					<AdUnit slot={ADSENSE_SLOTS.freeHubBeforeFaq} />
				</aside>

				{/* FAQ */}
				<section className="max-w-3xl mx-auto">
					<h2 className="text-2xl font-bold text-center mb-8">{t("faq_title")}</h2>
					<dl className="flex flex-col gap-4">
						{faqItems.map((item) => (
							<div key={item.question} className="rounded-lg border bg-card p-5">
								<dt className="font-medium text-sm">{item.question}</dt>
								<dd className="mt-2 text-sm text-muted-foreground leading-relaxed">
									{item.answer}
								</dd>
							</div>
						))}
					</dl>
				</section>

				{/* Internal links */}
				<nav aria-label={t("aria_related_pages")} className="mt-16 max-w-3xl mx-auto">
					<h2 className="text-lg font-semibold mb-3">{t("nav_title")}</h2>
					<ul className="flex flex-wrap gap-2">
						<li>
							<Button variant="outline" size="sm" asChild>
								<Link href="/pricing">{t("nav_pricing")}</Link>
							</Button>
						</li>
						<li>
							<Button variant="outline" size="sm" asChild>
								<Link href="/docs">{t("nav_docs")}</Link>
							</Button>
						</li>
						<li>
							<Button variant="outline" size="sm" asChild>
								<Link href="/blog">{t("nav_blog")}</Link>
							</Button>
						</li>
						<li>
							<Button variant="outline" size="sm" asChild>
								<Link href="/register">{t("nav_signup")}</Link>
							</Button>
						</li>
					</ul>
				</nav>
			</article>
		</div>
	);
}
