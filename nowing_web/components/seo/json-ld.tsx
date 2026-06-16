interface JsonLdProps {
	data: Record<string, unknown>;
}

export function JsonLd({ data }: JsonLdProps) {
	return (
		<script
			type="application/ld+json"
			dangerouslySetInnerHTML={{ __html: JSON.stringify(data) }}
		/>
	);
}

export function OrganizationJsonLd() {
	return (
		<JsonLd
			data={{
				"@context": "https://schema.org",
				"@type": "Organization",
				name: "Nowing",
				url: "https://nowing.com",
				logo: "https://nowing.com/logo.png",
			description:
				"The AI knowledge platform for teams. Turn your documents, connectors, and conversations into cited answers, reports, and podcasts.",
				sameAs: [
					"https://discord.gg/Cg2M4GUJ",
				],
				contactPoint: {
					"@type": "ContactPoint",
					email: "rohan@nowing.com",
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
				url: "https://nowing.com",
			description:
				"The AI knowledge platform for teams. Turn your documents, connectors, and conversations into cited answers, reports, and podcasts.",
				potentialAction: {
					"@type": "SearchAction",
					target: {
						"@type": "EntryPoint",
						urlTemplate: "https://nowing.com/docs?search={search_term_string}",
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
					description: "Free plan with 500 pages included",
				},
			description:
				"The AI knowledge platform for teams. Connect Slack, Google Drive, Notion, Confluence, and dozens more data sources, then get cited answers, reports, and podcasts.",
				url: "https://nowing.com",
				downloadUrl: "https://nowing.com",
			featureList: [
				"Best-in-class AI models managed for you",
				"AI-powered semantic search across all connected tools",
				"Federated search across Slack, Google Drive, Notion, and Confluence",
				"No data limits on sources, notebooks, or file size",
				"Real-time collaborative team chats",
				"Document Q&A with citations",
				"Report generation",
				"Podcast and video generation from sources",
				"Enterprise knowledge management",
				"Role-based access control for teams",
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
	author,
	image,
}: {
	title: string;
	description: string;
	url: string;
	datePublished: string;
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
				author: {
					"@type": "Organization",
					name: author,
				},
				publisher: {
					"@type": "Organization",
					name: "Nowing",
					logo: {
						"@type": "ImageObject",
						url: "https://nowing.com/logo.png",
					},
				},
				image: image || "https://nowing.com/og-image.png",
				mainEntityOfPage: {
					"@type": "WebPage",
					"@id": url,
				},
			}}
		/>
	);
}

export function BreadcrumbJsonLd({
	items,
}: {
	items: { name: string; url: string }[];
}) {
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

export function FAQJsonLd({
	questions,
}: {
	questions: { question: string; answer: string }[];
}) {
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
