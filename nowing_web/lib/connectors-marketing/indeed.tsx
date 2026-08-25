import { Briefcase } from "lucide-react";
import type { ConnectorPageContent } from "./types";

export const indeed: ConnectorPageContent = {
	slug: "indeed",
	name: "Indeed",
	icon: Briefcase,

	metaTitle: "Indeed Job Scraper API | Nowing",
	metaDescription:
		"Scrape Indeed job listings and details with the Nowing API. No official API limits, structured job data for research and hiring intelligence.",
	keywords: [
		"indeed scraper",
		"indeed api",
		"job scraper",
		"scrape indeed jobs",
		"job market research",
		"hiring trends",
		"indeed mcp",
	],

	h1: "Indeed Job Scraper API for Hiring Market Research",
	heroLede:
		"The Nowing Indeed API extracts job listings and job details from Indeed. Give it a keyword and location and get structured title, company, location, salary text, remote status, posting date, and apply URL — so your agents track hiring trends, competitor headcount, and salary signals.",

	transcript: {
		prompt: "Find remote senior data engineer openings on Indeed",
		toolCall:
			'indeed.scrape({ keyword: "senior data engineer", location: "Remote", sort: "date", max_items: 10 })',
		rows: [
			{
				primary: "Senior Data Engineer — Cloud Analytics Co",
				secondary: "Remote · $140,000 - $180,000 a year · 2 days ago",
				tag: "salary visible",
			},
			{
				primary: "Staff Data Engineer — Logistics Startup",
				secondary: "Remote US · $160,000 - $200,000 a year · 1 week ago",
				tag: "high range",
			},
			{
				primary: "Data Platform Engineer — Fintech",
				secondary: "Remote · $130,000 - $165,000 a year · 3 days ago",
				tag: "hiring signal",
			},
		],
		resultSummary: "10 jobs · 7 with salary text · surfaced in 4.2s",
	},

	extractIntro:
		"Every call returns one item per distinct job. Search by keyword and location — the scraper fetches the full job description, requirements, and benefits for each listing automatically.",
	extractFields: [
		{
			label: "Job title",
			description: "The listing title as shown on Indeed.",
		},
		{
			label: "Company",
			description: "Hiring company or recruiter name.",
		},
		{
			label: "Location",
			description: "City, state, or remote status.",
		},
		{
			label: "Salary",
			description: "Free-text salary range when displayed by Indeed.",
		},
		{
			label: "Posting date",
			description: "When the job was posted or refreshed.",
		},
		{
			label: "Job description",
			description: "Full job description fetched from the detail page.",
		},
		{
			label: "Requirements",
			description: "Qualifications and experience requirements extracted from the detail page.",
		},
		{
			label: "Benefits",
			description: "Benefit tags listed on the job card and detail page.",
		},
	],

	useCasesHeading: "What teams do with the Indeed API",
	useCases: [
		{
			title: "Hiring trend tracking",
			description:
				"Monitor how many roles competitors open, which skills they emphasize, and how salaries move over time.",
		},
		{
			title: "Salary benchmark research",
			description:
				"Aggregate salary text across listings to benchmark compensation for roles, locations, and seniority levels.",
		},
		{
			title: "Market and skill intelligence",
			description:
				"Map which technologies, certifications, and experience levels employers are hiring for right now.",
		},
		{
			title: "Remote-work tracking",
			description:
				"Filter by remote, hybrid, or on-site to study distributed-work trends in a field or geography.",
		},
	],

	comparison: {
		heading: "An Indeed data source built for agents",
		intro:
			"Indeed has no official public API for job listing research. Teams either scrape manually or buy limited datasets. Nowing turns it into an agent-ready capability.",
		columnLabel: "Manual / dataset approach",
		rows: [
			{
				feature: "Data access",
				official: "No official public API; manual HTML scraping or third-party datasets",
				nowing: "Structured job cards and detail pages through one API or MCP tool",
			},
			{
				feature: "Anti-bot handling",
				official: "Build and maintain proxy rotation, browser warming, and Cloudflare handling",
				nowing: "Managed warm-session rotation and block detection per run",
			},
			{
				feature: "Pricing",
				official:
					"Dataset vendors charge flat fees or per-query; in-house scrapers cost engineering time",
				nowing: "Pay per returned job card with no dataset commitment",
			},
			{
				feature: "Agent integration",
				official: "No native agent tool; custom wrappers needed",
				nowing: "MCP server exposes `indeed.scrape` as a native tool",
			},
		],
	},

	api: {
		platform: "indeed",
		verb: "scrape",
		mcpTool: "indeed.scrape",
		requestBody: {
			keyword: "data engineer",
			location: "Remote",
			sort: "date",
			max_items: 10,
		},
	},

	schema: {
		requestNote:
			"Provide a `keyword` (defaults to 'data engineer'). The scraper fetches full job details per listing automatically.",
		request: [
			{
				name: "keyword",
				type: "string",
				defaultValue: '"data engineer"',
				description: "Job keyword or title to search.",
			},
			{
				name: "location",
				type: "string",
				description: "City, state, region, or 'Remote'.",
			},
			{
				name: "radius",
				type: "integer",
				defaultValue: "25",
				description: "Search radius in miles (0-100).",
			},
			{
				name: "sort",
				type: "string",
				defaultValue: '"relevance"',
				description: "Result ordering: relevance or date.",
			},
			{
				name: "salary_min",
				type: "integer",
				description: "Optional minimum annual salary in USD.",
			},
			{
				name: "salary_max",
				type: "integer",
				description: "Optional maximum annual salary in USD.",
			},
			{
				name: "employment_type",
				type: "string",
				description: "Optional: full_time, contract, part_time, or intern.",
			},
			{
				name: "max_pages",
				type: "integer",
				defaultValue: "3",
				description: "Max result pages to fetch (0-5).",
			},
			{
				name: "max_items",
				type: "integer",
				defaultValue: "50",
				description: "Max total items returned. 1 to 100.",
			},
		],
		responseNote:
			"The response is { items: [...] } with one flat item per distinct job. Billing is per returned job card.",
		response: [
			{
				name: "title",
				type: "string",
				description: "Job title.",
			},
			{
				name: "company",
				type: "string",
				description: "Company or recruiter name.",
			},
			{
				name: "location",
				type: "string",
				description: "Job location.",
			},
			{
				name: "salary_raw",
				type: "string",
				description: "Free-text salary range when displayed.",
			},
			{
				name: "posted_at",
				type: "string",
				description: "When the job was posted (ISO datetime).",
			},
			{
				name: "job_description",
				type: "string",
				description: "Full job description from the detail page.",
			},
			{
				name: "job_requirement",
				type: "string",
				description: "Qualifications and requirements from the detail page.",
			},
			{
				name: "benefits",
				type: "string[]",
				description: "Benefit tags listed on the job card.",
			},
		],
	},

	faq: [
		{
			question: "Is scraping Indeed legal?",
			answer:
				"Nowing reads only public Indeed listings visible to logged-out visitors. It does not log in, apply, or access non-public data. Review Indeed's terms and your compliance needs before running at scale.",
		},
		{
			question: "Why is salary returned as text?",
			answer:
				"Indeed displays salaries as human-readable ranges (e.g. '$70,000 - $90,000 a year'). The scraper preserves that text so you can parse or compare it in your own pipeline.",
		},
		{
			question: "What markets are supported?",
			answer:
				"The current release targets the US Indeed market (www.indeed.com). Multi-market locale handling is not in scope for this version.",
		},
		{
			question: "What happens when Indeed blocks the request?",
			answer:
				"The scraper detects blocks and returns a typed `degraded` response. It does not crash the run, and no billable units are charged for blocked or error pages.",
		},
	],

	related: [
		{ label: "Vietnam Job Market API", href: "/vn_jobs" },
		{ label: "Web Crawl API", href: "/web-crawl" },
		{ label: "Google Search API", href: "/google-search" },
		{ label: "Nowing MCP Server", href: "/mcp-server" },
	],
};
