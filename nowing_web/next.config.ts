import path from "node:path";
import { createMDX } from "fumadocs-mdx/next";
import type { NextConfig } from "next";
import createNextIntlPlugin from "next-intl/plugin";

// Create the next-intl plugin
const withNextIntl = createNextIntlPlugin("./i18n/request.ts");

// TODO: Separate app routes (/login, /dashboard) from marketing routes
// (landing page, /contact, /pricing, /docs) so the desktop build only
// ships what desktop users actually need.
const nextConfig: NextConfig = {
	output: "standalone",
	async redirects() {
		return [
			// /mcp-connector was split into the two MCP directions; the external
			// (client) side kept the original content.
			{ source: "/mcp-connector", destination: "/external-mcp-connectors", permanent: true },
		];
	},
	outputFileTracingRoot: path.join(__dirname, ".."),
	reactStrictMode: false,
	typescript: {
		ignoreBuildErrors: true,
	},
	async headers() {
		return [
			// Story 10.5: allow the anti-bot evidence screenshot to be displayed
			// on the admin page. The storage backend domain may differ per
			// deployment, so we allow any HTTPS origin for img-src on this path,
			// and permit API calls to the configured backend.
			{
				source: "/admin/anti-bot-escalations",
				headers: [
					{
						key: "Content-Security-Policy",
						value:
							"default-src 'self'; img-src 'self' http://localhost:* http://127.0.0.1:* https: data:; connect-src 'self' http://localhost:* http://127.0.0.1:* https: ws://localhost:* ws://127.0.0.1:*; script-src 'self' 'unsafe-inline' 'unsafe-eval'; style-src 'self' 'unsafe-inline';",
					},
				],
			},
		];
	},
	images: {
		remotePatterns: [
			{
				protocol: "http",
				hostname: "localhost",
				port: "8000",
				pathname: "/api/v1/image-generations/**",
			},
			{
				protocol: "https",
				hostname: "**",
			},
		],
		// Allow remote SVGs (e.g. README badges from img.shields.io, trendshift.io,
		// etc.) which are otherwise blocked by next/image. The CSP below sandboxes
		// the SVG and forbids any embedded scripts, which is the mitigation
		// recommended by Vercel's NEXTJS_SAFE_SVG_IMAGES conformance rule.
		dangerouslyAllowSVG: true,
		contentDispositionType: "attachment",
		contentSecurityPolicy: "default-src 'self'; script-src 'none'; sandbox;",
	},
	experimental: {
		optimizePackageImports: [
			"lucide-react",
			"@tabler/icons-react",
			"date-fns",
			"@assistant-ui/react",
			"@assistant-ui/react-markdown",
			"motion",
		],
	},
	// Turbopack config (used during `next dev --turbopack`)
	turbopack: {
		rules: {
			"*.svg": {
				loaders: ["@svgr/webpack"],
				as: "*.js",
			},
		},
	},

	// Configure webpack (SVGR)
	webpack: (config) => {
		// SVGR: import *.svg as React components
		const fileLoaderRule = config.module.rules.find(
			(rule: { test?: { test?: (s: string) => boolean } }) => rule.test?.test?.(".svg")
		);
		config.module.rules.push(
			// Re-apply the existing file loader for *.svg?url imports
			{
				...fileLoaderRule,
				test: /\.svg$/i,
				resourceQuery: /url/, // e.g. import icon from './icon.svg?url'
			},
			// Convert all other *.svg imports to React components
			{
				test: /\.svg$/i,
				issuer: fileLoaderRule.issuer,
				resourceQuery: { not: [...fileLoaderRule.resourceQuery.not, /url/] },
				use: ["@svgr/webpack"],
			}
		);
		fileLoaderRule.exclude = /\.svg$/i;

		return config;
	},
};

// Wrap the config with MDX and next-intl plugins
const withMDX = createMDX({});

export default withNextIntl(withMDX(nextConfig));
