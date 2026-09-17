import { IconBrandGithub } from "@tabler/icons-react";
import { ArrowRight, Check, Database, KeyRound, Server, TerminalSquare } from "lucide-react";
import type { Metadata } from "next";
import { getTranslations } from "next-intl/server";
import Link from "next/link";
import { ConnectorFaq } from "@/components/connectors-marketing/connector-faq";
import { Reveal } from "@/components/connectors-marketing/reveal";
import { MarketingSection } from "@/components/marketing/section";
import { AgentSetupTabs } from "@/components/mcp/agent-setup-tabs";
import { BreadcrumbNav } from "@/components/seo/breadcrumb-nav";
import { FAQJsonLd, JsonLd } from "@/components/seo/json-ld";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import type { FaqItem } from "@/lib/connectors-marketing/types";

const canonicalUrl = "https://www.nowing.com/mcp-server";

const metaDescription =
	"The Nowing MCP server gives Claude, Cursor, and any MCP client native tools for your workspace: scrape Reddit, YouTube, Instagram, TikTok, Amazon, Google Maps, Google Search, Vietnamese real estate, and the web, plus full knowledge base access. One API key.";

export const metadata: Metadata = {
	title: "Nowing MCP Server: Scraper APIs and Knowledge Base as Agent Tools",
	description: metaDescription,
	keywords: [
		"nowing mcp server",
		"mcp server",
		"mcp server for web scraping",
		"reddit mcp server",
		"youtube mcp server",
		"google maps mcp server",
		"serp mcp server",
		"mcp server for claude",
		"mcp server for cursor",
		"knowledge base mcp server",
	],
	alternates: { canonical: canonicalUrl },
	openGraph: {
		title: "Nowing MCP Server: Scraper APIs and Knowledge Base as Agent Tools",
		description: metaDescription,
		url: canonicalUrl,
		siteName: "Nowing",
		type: "website",
		images: [{ url: "/og-image.png", width: 1200, height: 630, alt: "Nowing MCP server" }],
	},
	twitter: {
		card: "summary_large_image",
		title: "Nowing MCP Server: Scraper APIs and Knowledge Base as Agent Tools",
		description: metaDescription,
		images: ["/og-image.png"],
	},
};

/* The hosted Cursor config; mirrors lib/mcp/clients.ts. */
const CURSOR_CONFIG = `{
  "mcpServers": {
    "nowing": {
      "url": "https://mcp.nowing.com/mcp",
      "headers": {
        "Authorization": "Bearer nw_pat_..."
      }
    }
  }
}`;

function useSteps(t: (k: string) => string) {
	return [
		{ icon: KeyRound, title: t("step1_title"), description: t("step1_desc") },
		{ icon: TerminalSquare, title: t("step2_title"), description: t("step2_desc") },
		{ icon: Server, title: t("step3_title"), description: t("step3_desc") },
	];
}

/** Mirrors the tool registry in nowing_mcp (see its README). */
function useToolGroups(t: (k: string) => string) {
	return [
		{
			icon: Server,
			title: t("tg_scrapers"),
			description: t("tg_scrapers_desc"),
			tools: [
				"nowing_reddit_scrape","nowing_youtube_scrape","nowing_youtube_comments",
				"nowing_instagram_scrape","nowing_instagram_details","nowing_tiktok_scrape",
				"nowing_tiktok_comments","nowing_tiktok_user_search","nowing_tiktok_trending",
				"nowing_google_maps_scrape","nowing_google_maps_reviews","nowing_google_search",
				"nowing_amazon_scrape","nowing_batdongsan_scrape","nowing_chotot_bds_scrape",
				"nowing_muaban_bds_scrape","nowing_vn_bds_aggregate","nowing_web_crawl",
				"nowing_list_scraper_runs","nowing_get_scraper_run",
			],
		},
		{
			icon: Database,
			title: t("tg_kb"),
			description: t("tg_kb_desc"),
			tools: [
				"nowing_search_knowledge_base","nowing_list_documents","nowing_get_document",
				"nowing_add_document","nowing_upload_file","nowing_update_document","nowing_delete_document",
			],
		},
		{
			icon: KeyRound,
			title: t("tg_ws"),
			description: t("tg_ws_desc"),
			tools: ["nowing_list_workspaces","nowing_select_workspace"],
		},
	];
}

function useFaq(t: (k: string) => string): FaqItem[] {
	return [1, 2, 3, 4, 5].map((n) => ({
		question: t(`faq${n}_q`),
		answer: t(`faq${n}_a`),
	}));
}

function ConfigCard({ t }: { t: (k: string) => string }) {
	return (
		<div className="rounded-xl border bg-card p-5 shadow-sm">
			<p className="font-mono text-xs text-muted-foreground">.cursor/mcp.json</p>
			<pre className="mt-2 overflow-x-auto rounded-lg bg-muted/50 p-4 font-mono text-xs leading-relaxed">
				{CURSOR_CONFIG}
			</pre>
			<p className="mt-3 flex items-center gap-1.5 text-xs text-muted-foreground">
				<Check className="size-3.5 text-brand" aria-hidden />
				{t("cfg_works")}
			</p>
		</div>
	);
}

// Rendered per-request so the NEXT_LOCALE cookie can switch the language.
export const dynamic = "force-dynamic";

export default async function McpServerPage() {
	const t = await getTranslations("mcpServer");
	const STEPS = useSteps(t);
	const TOOL_GROUPS = useToolGroups(t);
	const FAQ = useFaq(t);
	return (
		<>
			<JsonLd
				data={{
					"@context": "https://schema.org",
					"@type": "SoftwareApplication",
					name: "Nowing MCP Server",
					applicationCategory: "DeveloperApplication",
					operatingSystem: "Web",
					description: metaDescription,
					url: canonicalUrl,
					offers: {
						"@type": "Offer",
						price: "0",
						priceCurrency: "USD",
						description: "$5 free credit included, pay as you go",
					},
					provider: {
						"@type": "Organization",
						name: "Nowing",
						url: "https://www.nowing.com",
					},
					isPartOf: { "@type": "WebSite", name: "Nowing", url: "https://www.nowing.com" },
				}}
			/>
			<FAQJsonLd questions={FAQ} />

			<div className="pb-4">
				{/* Hero */}
				<MarketingSection className="pt-28 pb-12 sm:pt-32 sm:pb-16">
					<div className="grid items-center gap-10 lg:grid-cols-2 lg:gap-14">
						<div>
							<BreadcrumbNav
								className="mb-6"
								items={[
									{ name: t("bc_connectors"), href: "/connectors" },
									{ name: t("bc_mcp"), href: "/mcp-server" },
								]}
							/>
							<Badge variant="outline" className="mb-5 gap-1.5 py-1">
								<Server className="size-3.5" aria-hidden="true" />
								{t("badge")}
							</Badge>
							<h1 className="font-serif text-3xl sm:text-4xl lg:text-5xl font-normal tracking-tight text-balance">
								{t("hero_title")}
							</h1>
							<p className="mt-4 max-w-xl text-sm sm:text-base leading-relaxed text-muted-foreground font-sans">
								{t("hero_desc")}
							</p>
							<div className="mt-8 flex flex-wrap items-center gap-3">
								<Button asChild size="lg">
									<Link href="/register">
										{t("get_key")}
										<ArrowRight className="size-4" aria-hidden="true" />
									</Link>
								</Button>
								<Button asChild variant="outline" size="lg">
									<Link href="/docs">{t("read_docs")}</Link>
								</Button>
								<Button asChild variant="ghost" size="lg">
									<Link
										href="https://github.com/deptrai/nowing"
										target="_blank"
										rel="noopener noreferrer"
									>
										<IconBrandGithub className="size-4" aria-hidden="true" />
										GitHub
									</Link>
								</Button>
							</div>
						</div>
						<ConfigCard t={t} />
					</div>
				</MarketingSection>

				{/* How it works */}
				<MarketingSection>
					<Reveal>
						<h2 className="text-2xl font-bold tracking-tight sm:text-3xl">
							{t("how_title")}
						</h2>
					</Reveal>
					<div className="mt-8 grid gap-4 sm:grid-cols-3">
						{STEPS.map((step) => (
							<Reveal key={step.title}>
								<div className="h-full rounded-xl border bg-card p-6 transition-colors hover:border-brand/40">
									<span className="flex size-10 items-center justify-center rounded-lg border bg-muted/40">
										<step.icon className="size-5 text-foreground" aria-hidden />
									</span>
									<h3 className="mt-4 font-semibold">{step.title}</h3>
									<p className="mt-2 text-sm leading-relaxed text-muted-foreground">
										{step.description}
									</p>
								</div>
							</Reveal>
						))}
					</div>
				</MarketingSection>

				{/* Per-agent setup */}
				<MarketingSection>
					<Reveal>
						<h2 className="text-2xl font-bold tracking-tight sm:text-3xl">
							{t("setup_title")}
						</h2>
						<p className="mt-3 max-w-2xl text-muted-foreground leading-relaxed">
							{t("setup_desc")}
						</p>
					</Reveal>
					<Reveal>
						<div className="mt-8 rounded-xl border bg-card p-5 shadow-sm sm:p-6">
							<AgentSetupTabs />
						</div>
					</Reveal>
				</MarketingSection>

				{/* Tools */}
				<MarketingSection>
					<Reveal>
						<h2 className="text-2xl font-bold tracking-tight sm:text-3xl">
							{t("tools_title")}
						</h2>
						<p className="mt-3 max-w-2xl text-muted-foreground leading-relaxed">
							{t("tools_desc")}
						</p>
					</Reveal>
					<div className="mt-8 grid gap-4 lg:grid-cols-3">
						{TOOL_GROUPS.map((group) => (
							<Reveal key={group.title}>
								<div className="h-full rounded-xl border bg-card p-6">
									<span className="flex size-10 items-center justify-center rounded-lg border bg-muted/40">
										<group.icon className="size-5 text-foreground" aria-hidden />
									</span>
									<h3 className="mt-4 font-semibold">{group.title}</h3>
									<p className="mt-2 text-sm leading-relaxed text-muted-foreground">
										{group.description}
									</p>
									<ul className="mt-4 space-y-1.5">
										{group.tools.map((tool) => (
											<li key={tool} className="truncate font-mono text-xs text-muted-foreground">
												{tool}
											</li>
										))}
									</ul>
								</div>
							</Reveal>
						))}
					</div>
				</MarketingSection>

				{/* Server vs external connectors */}
				<MarketingSection>
					<Reveal>
						<h2 className="text-2xl font-bold tracking-tight sm:text-3xl">
							{t("vs_title")}
						</h2>
						<p className="mt-3 max-w-2xl text-muted-foreground leading-relaxed">
							{t("vs_desc_1")} <em>{t("vs_server")}</em> {t("vs_desc_2")}{" "}
							<Link
								href="/external-mcp-connectors"
								className="font-medium text-foreground underline underline-offset-4"
							>
								{t("vs_external")}
							</Link>{" "}
							{t("vs_desc_3")}
						</p>
					</Reveal>
				</MarketingSection>

				{/* FAQ */}
				<MarketingSection>
					<Reveal>
						<h2 className="text-2xl font-bold tracking-tight sm:text-3xl">
							{t("faq_title")}
						</h2>
					</Reveal>
					<Reveal>
						<div className="mt-6 max-w-3xl">
							<ConnectorFaq items={FAQ} />
						</div>
					</Reveal>
				</MarketingSection>

				{/* Closing CTA + related */}
				<MarketingSection>
					<Reveal>
						<div className="rounded-2xl border bg-card p-8 text-center sm:p-12">
							<h2 className="text-2xl font-bold tracking-tight sm:text-3xl">
								{t("cta_title")}
							</h2>
							<p className="mx-auto mt-3 max-w-xl text-muted-foreground leading-relaxed">
								{t("cta_desc_1")}{" "}
								<Link href="/" className="font-medium text-foreground underline underline-offset-4">
									{t("cta_platform")}
								</Link>
								. {t("cta_desc_2")}
							</p>
							<div className="mt-7 flex flex-wrap justify-center gap-3">
								<Button asChild size="lg">
									<Link href="/register">
										{t("start_free")}
										<ArrowRight className="size-4" aria-hidden="true" />
									</Link>
								</Button>
								<Button asChild variant="outline" size="lg">
									<Link href="/pricing">{t("see_pricing")}</Link>
								</Button>
							</div>

							<Separator className="my-8" />

							<nav aria-label={t("nav_other")} className="flex flex-wrap justify-center gap-2">
								<Button asChild variant="ghost" size="sm">
									<Link href="/connectors">{t("nav_all")}</Link>
								</Button>
								<Button asChild variant="ghost" size="sm">
									<Link href="/external-mcp-connectors">{t("nav_ext")}</Link>
								</Button>
								<Button asChild variant="ghost" size="sm">
									<Link href="/reddit">Reddit API</Link>
								</Button>
								<Button asChild variant="ghost" size="sm">
									<Link href="/youtube">YouTube API</Link>
								</Button>
								<Button asChild variant="ghost" size="sm">
									<Link href="/instagram">Instagram API</Link>
								</Button>
								<Button asChild variant="ghost" size="sm">
									<Link href="/tiktok">TikTok API</Link>
								</Button>
								<Button asChild variant="ghost" size="sm">
									<Link href="/google-maps">Google Maps API</Link>
								</Button>
								<Button asChild variant="ghost" size="sm">
									<Link href="/google-search">SERP API</Link>
								</Button>
								<Button asChild variant="ghost" size="sm">
									<Link href="/web-crawl">Web Crawl API</Link>
								</Button>
							</nav>
						</div>
					</Reveal>
				</MarketingSection>
			</div>
		</>
	);
}
