interface JsonLdProps {
	data: Record<string, unknown>;
}

export function JsonLd({ data }: JsonLdProps) {
	return (
		// biome-ignore lint/security/noDangerouslySetInnerHtml: JSON-LD structured data requires dangerouslySetInnerHTML for script injection
		<script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(data) }} />
	);
}

export function OrganizationJsonLd() {
	return (
		<JsonLd
			data={{
				"@context": "https://schema.org",
				"@type": "Organization",
				name: "Nowing",
				url: "https://www.nowing.com",
				logo: "https://www.nowing.com/logo.png",
				description:
					"Nowing is an open-source NotebookLM alternative for AI agents. It researches the live web with structured data through one API or MCP server.",
				sameAs: [
					"https://github.com/deptrai/nowing",
					"https://discord.gg/ejRNvftDp9",
					"https://www.reddit.com/r/Nowing/",
					"https://www.linkedin.com/company/nowing/",
				],
				contactPoint: {
					"@type": "ContactPoint",
					email: "admin@nowing.com",
					contactType: "sales",
				},
			}}
		/>
	);
}

export function WebSiteJsonLd() {
	return (
		<JsonLd
			data={{
				"@context": "https://schema.org",
				"@type": "WebSite",
				name: "Nowing",
				url: "https://www.nowing.com",
				description:
					"Nowing is an open-source NotebookLM alternative for AI agents, an open web research platform with live data connectors served through one API or MCP server.",
				potentialAction: {
					"@type": "SearchAction",
					target: {
						"@type": "EntryPoint",
						urlTemplate: "https://www.nowing.com/docs?search={search_term_string}",
					},
					"query-input": "required name=search_term_string",
				},
			}}
		/>
	);
}

export function SoftwareApplicationJsonLd() {
	return (
		<JsonLd
			data={{
				"@context": "https://schema.org",
				"@type": "SoftwareApplication",
				name: "Nowing",
				applicationCategory: "BusinessApplication",
				operatingSystem: "Windows, macOS, Linux, Web",
				offers: {
					"@type": "Offer",
					price: "0",
					priceCurrency: "USD",
					description:
						"Free self-hosted from the open-source repo; cloud starts with $5 of free credit, then pay as you go",
				},
				description:
					"Nowing is an open-source NotebookLM alternative for AI agents. It researches the live web with platform-native connectors for Reddit, YouTube, TikTok, Amazon, Google Maps, Google Search, and any page on the open web, through one API or MCP server.",
				url: "https://www.nowing.com",
				downloadUrl: "https://github.com/deptrai/nowing/releases",
				featureList: [
					"Platform-native connectors: Reddit, YouTube, TikTok, Amazon, Google Maps, Google Search, Web Crawl",
					"MCP server that exposes every connector as a native agent tool",
					"Agent harness with retries, structured output, and credit metering",
					"Live web research with cited briefs and alerts",
					"AI automations and agents (scheduled and event-triggered workflows)",
					"AI-powered semantic search across connected tools and documents",
					"Knowledge base with file uploads and Google Drive, OneDrive, and Dropbox sync",
					"Document Q&A with citations, report, podcast, and video generation",
					"Real-time collaborative team chats",
					"Native desktop app with Quick, General, and Screenshot Assist",
					"Open source and self-hostable with no data limits",
				],
			}}
		/>
	);
}

export function ArticleJsonLd({
	title,
	description,
	url,
	datePublished,
	dateModified,
	author,
	image,
}: {
	title: string;
	description: string;
	url: string;
	datePublished: string;
	dateModified?: string;
	author: string;
	image?: string;
}) {
	return (
		<JsonLd
			data={{
				"@context": "https://schema.org",
				"@type": "Article",
				headline: title,
				description,
				url,
				datePublished,
				...(dateModified ? { dateModified } : {}),
				author: {
					"@type": "Organization",
					name: author,
				},
				publisher: {
					"@type": "Organization",
					name: "Nowing",
					logo: {
						"@type": "ImageObject",
						url: "https://www.nowing.com/logo.png",
					},
				},
				image: image || "https://www.nowing.com/og-image.png",
				mainEntityOfPage: {
					"@type": "WebPage",
					"@id": url,
				},
			}}
		/>
	);
}

export function BreadcrumbJsonLd({ items }: { items: { name: string; url: string }[] }) {
	return (
		<JsonLd
			data={{
				"@context": "https://schema.org",
				"@type": "BreadcrumbList",
				itemListElement: items.map((item, index) => ({
					"@type": "ListItem",
					position: index + 1,
					name: item.name,
					item: item.url,
				})),
			}}
		/>
	);
}

export function FAQJsonLd({ questions }: { questions: { question: string; answer: string }[] }) {
	return (
		<JsonLd
			data={{
				"@context": "https://schema.org",
				"@type": "FAQPage",
				mainEntity: questions.map((q) => ({
					"@type": "Question",
					name: q.question,
					acceptedAnswer: {
						"@type": "Answer",
						text: q.answer,
					},
				})),
			}}
		/>
	);
}
