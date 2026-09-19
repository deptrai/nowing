import { IconBrandGithub } from "@tabler/icons-react";
import { ArrowRight, Check, Plug, ShieldCheck, Wrench } from "lucide-react";
import type { Metadata } from "next";
import { getTranslations } from "next-intl/server";
import Link from "next/link";
import { ConnectorFaq } from "@/components/connectors-marketing/connector-faq";
import { Reveal } from "@/components/connectors-marketing/reveal";
import { MarketingSection } from "@/components/marketing/section";
import { BreadcrumbNav } from "@/components/seo/breadcrumb-nav";
import { FAQJsonLd, JsonLd } from "@/components/seo/json-ld";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import type { FaqItem } from "@/lib/connectors-marketing/types";

const canonicalUrl = "https://www.nowing.com/external-mcp-connectors";

const metaDescription =
	"External MCP connectors let your Nowing agents use any MCP server. Paste a config, tools are auto-discovered, and every call runs with per-tool approval. Try it free.";

export const metadata: Metadata = {
	title: "External MCP Connectors: Add Any MCP Server | Nowing",
	description: metaDescription,
	keywords: [
		"mcp connector",
		"external mcp connectors",
		"what is an mcp connector",
		"mcp client",
		"add mcp server",
		"connect mcp server",
		"mcp integrations",
	],
	alternates: { canonical: canonicalUrl },
	openGraph: {
		title: "External MCP Connectors: Add Any MCP Server | Nowing",
		description: metaDescription,
		url: canonicalUrl,
		siteName: "Nowing",
		type: "website",
		images: [
			{ url: "/og-image.png", width: 1200, height: 630, alt: "Nowing external MCP connectors" },
		],
	},
	twitter: {
		card: "summary_large_image",
		title: "External MCP Connectors: Add Any MCP Server | Nowing",
		description: metaDescription,
		images: ["/og-image.png"],
	},
};

/* Mirrors the real server_config contract (stdio + HTTP transports). */
const STDIO_CONFIG = `{
  "command": "npx",
  "args": ["-y", "@modelcontextprotocol/server-filesystem", "/data"],
  "env": { "LOG_LEVEL": "info" },
  "transport": "stdio"
}`;

const HTTP_CONFIG = `{
  "url": "https://mcp.example.com/mcp",
  "headers": { "Authorization": "Bearer <token>" },
  "transport": "streamable-http"
}`;

function useSteps(t: (k: string) => string) {
	return [
		{ icon: Plug, title: t("step1_title"), description: t("step1_desc") },
		{ icon: Wrench, title: t("step2_title"), description: t("step2_desc") },
		{ icon: ShieldCheck, title: t("step3_title"), description: t("step3_desc") },
	];
}

/** Hosted MCP apps with one-click OAuth (mirrors the backend MCP service registry). */
const ONE_CLICK_APPS = [
	"Notion",
	"Slack",
	"Jira",
	"Confluence",
	"Linear",
	"ClickUp",
	"Airtable",
] as const;

function useFaq(t: (k: string) => string): FaqItem[] {
	return [1, 2, 3, 4, 5].map((n) => ({
		question: t(`faq${n}_q`),
		answer: t(`faq${n}_a`),
	}));
}

function ConfigCard({ t }: { t: (k: string) => string }) {
	return (
		<div className="rounded-xl border bg-card p-5 shadow-sm">
			<p className="font-mono text-xs text-muted-foreground">{t("cfg_local")}</p>
			<pre className="mt-2 overflow-x-auto rounded-lg bg-muted/50 p-4 font-mono text-xs leading-relaxed">
				{STDIO_CONFIG}
			</pre>
			<p className="mt-4 font-mono text-xs text-muted-foreground">{t("cfg_remote")}</p>
			<pre className="mt-2 overflow-x-auto rounded-lg bg-muted/50 p-4 font-mono text-xs leading-relaxed">
				{HTTP_CONFIG}
			</pre>
			<p className="mt-3 flex items-center gap-1.5 text-xs text-muted-foreground">
				<Check className="size-3.5 text-brand" aria-hidden />
				{t("cfg_auto")}
			</p>
		</div>
	);
}

// Rendered per-request so the NEXT_LOCALE cookie can switch the language.
export const dynamic = "force-dynamic";

export default async function ExternalMcpConnectorsPage() {
	const t = await getTranslations("extMcp");
	const STEPS = useSteps(t);
	const FAQ = useFaq(t);
	return (
		<>
			<JsonLd
				data={{
					"@context": "https://schema.org",
					"@type": "SoftwareApplication",
					name: "Nowing External MCP Connectors",
					applicationCategory: "DeveloperApplication",
					operatingSystem: "Web",
					description: metaDescription,
					url: canonicalUrl,
					offers: {
						"@type": "Offer",
						price: "0",
						priceCurrency: "USD",
						description: t("free_tier"),
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
									{ name: t("bc_external"), href: "/external-mcp-connectors" },
								]}
							/>
							<Badge variant="outline" className="mb-5 gap-1.5 py-1">
								<Plug className="size-3.5" aria-hidden="true" />
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
										{t("start_free")}
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

				{/* One-click apps */}
				<MarketingSection>
					<Reveal>
						<h2 className="text-2xl font-bold tracking-tight sm:text-3xl">
							{t("apps_title")}
						</h2>
						<p className="mt-3 max-w-2xl text-muted-foreground leading-relaxed">
							{t("apps_desc")}
						</p>
					</Reveal>
					<Reveal>
						<div className="mt-8 flex flex-wrap gap-2">
							{ONE_CLICK_APPS.map((app) => (
								<span
									key={app}
									className="inline-flex items-center gap-1.5 rounded-full border bg-card px-4 py-2 text-sm font-medium"
								>
									<Check className="size-3.5 text-brand" aria-hidden />
									{app}
								</span>
							))}
						</div>
					</Reveal>
				</MarketingSection>

				{/* Connector vs server */}
				<MarketingSection>
					<Reveal>
						<h2 className="text-2xl font-bold tracking-tight sm:text-3xl">
							{t("vs_title")}
						</h2>
						<p className="mt-3 max-w-2xl text-muted-foreground leading-relaxed">
							{t("vs_desc_1")} <em>{t("vs_client")}</em>: {t("vs_desc_2")}{" "}
							<Link
								href="/mcp-server"
								className="font-medium text-foreground underline underline-offset-4"
							>
								{t("vs_server")}
							</Link>{" "}
							{t("vs_desc_3")}{" "}
							<Link
								href="/reddit"
								className="font-medium text-foreground underline underline-offset-4"
							>
								Reddit
							</Link>{" "}
							{t("vs_and")}{" "}
							<Link
								href="/google-maps"
								className="font-medium text-foreground underline underline-offset-4"
							>
								Google Maps
							</Link>{" "}
							{t("vs_desc_4")}
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
									<Link href="/mcp-server">Nowing MCP Server</Link>
								</Button>
								<Button asChild variant="ghost" size="sm">
									<Link href="/reddit">Reddit API</Link>
								</Button>
								<Button asChild variant="ghost" size="sm">
									<Link href="/youtube">YouTube API</Link>
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
