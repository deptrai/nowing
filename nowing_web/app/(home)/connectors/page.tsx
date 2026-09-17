import { ArrowRight, Plug, Server } from "lucide-react";
import type { Metadata } from "next";
import { getTranslations } from "next-intl/server";
import Link from "next/link";
import { getAllConnectors } from "@/lib/connectors-marketing";

const canonicalUrl = "https://www.nowing.com/connectors";

const metaDescription =
	"Platform-native scraper APIs for AI agents. Pull live, structured data from the platforms where answers live through one typed API or the Nowing MCP server. Explore every connector.";

export const metadata: Metadata = {
	title: "Scraper APIs for AI Agents: All Connectors | Nowing",
	description: metaDescription,
	keywords: [
		"scraper api",
		"web scraping api",
		"scraper api for ai agents",
		"data connectors",
		"mcp server",
		"open web research platform",
	],
	alternates: { canonical: canonicalUrl },
	openGraph: {
		title: "Scraper APIs for AI Agents: All Connectors | Nowing",
		description: metaDescription,
		url: canonicalUrl,
		siteName: "Nowing",
		type: "website",
		images: [{ url: "/og-image.png", width: 1200, height: 630, alt: "Nowing connectors" }],
	},
};

// Rendered per-request so the NEXT_LOCALE cookie can switch the language.
export const dynamic = "force-dynamic";

export default async function ConnectorsIndexPage() {
	const t = await getTranslations("connectorsHub");
	const connectors = getAllConnectors();

	return (
		<div className="pt-28 pb-16 sm:pt-32">
			<div className="mx-auto w-full max-w-7xl px-2 md:px-8 xl:px-0">
				<header className="max-w-2xl">
					<h1 className="font-serif text-3xl sm:text-4xl lg:text-5xl font-normal tracking-tight text-balance">
						{t("title")}
					</h1>
					<p className="mt-4 text-sm sm:text-base leading-relaxed text-muted-foreground font-sans">
						{t("lede_1")}{" "}
						<Link href="/" className="font-medium text-foreground underline underline-offset-4">
							{t("lede_platform")}
						</Link>
						.
					</p>
				</header>

				<div className="mt-12 grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
					{connectors.map((connector) => {
						const Icon = connector.icon;
						return (
							<Link
								key={connector.slug}
								href={`/${connector.slug}`}
								className="group flex flex-col rounded-xl border bg-card p-6 transition-colors hover:border-brand/40"
							>
								<span className="flex size-11 items-center justify-center rounded-lg border bg-muted/40 transition-transform duration-200 ease-out group-hover:scale-110 motion-reduce:transition-none motion-reduce:group-hover:scale-100">
									<Icon className="size-5 text-foreground" aria-hidden="true" />
								</span>
								<h2 className="mt-4 text-lg font-semibold">
									{connector.cardTitle ?? `${connector.name} API`}
								</h2>
								<p className="mt-2 flex-1 text-sm leading-relaxed text-muted-foreground line-clamp-4">
									{connector.heroLede}
								</p>
								<span className="mt-4 inline-flex items-center gap-1 text-sm font-medium text-foreground">
									{t("explore")}
									<ArrowRight
										className="size-4 transition-transform group-hover:translate-x-0.5"
										aria-hidden="true"
									/>
								</span>
							</Link>
						);
					})}
					{/* Bespoke pages (not in the scrape-API registry): the two MCP directions. */}
					<Link
						href="/mcp-server"
						className="group flex flex-col rounded-xl border bg-card p-6 transition-colors hover:border-brand/40"
					>
						<span className="flex size-11 items-center justify-center rounded-lg border bg-muted/40 transition-transform duration-200 ease-out group-hover:scale-110 motion-reduce:transition-none motion-reduce:group-hover:scale-100">
							<Server className="size-5 text-foreground" aria-hidden="true" />
						</span>
						<h2 className="mt-4 text-lg font-semibold">{t("mcp_server")}</h2>
						<p className="mt-2 flex-1 text-sm leading-relaxed text-muted-foreground line-clamp-4">
							{t("mcp_server_desc")}
						</p>
						<span className="mt-4 inline-flex items-center gap-1 text-sm font-medium text-foreground">
							{t("explore")}
							<ArrowRight
								className="size-4 transition-transform group-hover:translate-x-0.5"
								aria-hidden="true"
							/>
						</span>
					</Link>
					<Link
						href="/external-mcp-connectors"
						className="group flex flex-col rounded-xl border bg-card p-6 transition-colors hover:border-brand/40"
					>
						<span className="flex size-11 items-center justify-center rounded-lg border bg-muted/40 transition-transform duration-200 ease-out group-hover:scale-110 motion-reduce:transition-none motion-reduce:group-hover:scale-100">
							<Plug className="size-5 text-foreground" aria-hidden="true" />
						</span>
						<h2 className="mt-4 text-lg font-semibold">{t("external_mcp")}</h2>
						<p className="mt-2 flex-1 text-sm leading-relaxed text-muted-foreground line-clamp-4">
							{t("external_mcp_desc")}
						</p>
						<span className="mt-4 inline-flex items-center gap-1 text-sm font-medium text-foreground">
							{t("explore")}
							<ArrowRight
								className="size-4 transition-transform group-hover:translate-x-0.5"
								aria-hidden="true"
							/>
						</span>
					</Link>
				</div>
			</div>
		</div>
	);
}
