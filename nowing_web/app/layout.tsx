import type { Metadata, Viewport } from "next";
import "./globals.css";
import { RootProvider } from "fumadocs-ui/provider/next";
import { Roboto } from "next/font/google";
import { AnnouncementToastProvider } from "@/components/announcements/AnnouncementToastProvider";
import { GlobalLoadingProvider } from "@/components/providers/GlobalLoadingProvider";
import { I18nProvider } from "@/components/providers/I18nProvider";
import { PostHogProvider } from "@/components/providers/PostHogProvider";
import { ZeroProvider } from "@/components/providers/ZeroProvider";
import { ThemeProvider } from "@/components/theme/theme-provider";
import { Toaster } from "@/components/ui/sonner";
import { LocaleProvider } from "@/contexts/LocaleContext";
import { PlatformProvider } from "@/contexts/platform-context";
import { ReactQueryClientProvider } from "@/lib/query-client/query-client.provider";
import { cn } from "@/lib/utils";
import { OrganizationJsonLd, SoftwareApplicationJsonLd, WebSiteJsonLd } from "@/components/seo/json-ld";

const roboto = Roboto({
	subsets: ["latin"],
	weight: ["400", "500", "700"],
	display: "swap",
	variable: "--font-roboto",
});

/**
 * Viewport configuration for mobile keyboard handling.
 * - interactiveWidget: 'resizes-content' tells mobile browsers (especially Chrome Android)
 *   to resize the CSS layout viewport when the virtual keyboard opens, so sticky elements
 *   (like the chat input bar) stay visible above the keyboard.
 * - viewportFit: 'cover' enables env(safe-area-inset-*) for notched/home-indicator devices.
 */
export const viewport: Viewport = {
	width: "device-width",
	initialScale: 1,
	viewportFit: "cover",
	interactiveWidget: "resizes-content",
};

export const metadata: Metadata = {
	metadataBase: new URL("https://nowing.com"),
	alternates: {
		canonical: "https://nowing.com",
	},
	title: "Nowing - NotebookLM for Teams | AI Knowledge Platform",
	description:
		"Nowing is the AI knowledge platform for teams. Turn your documents, connectors, and conversations into cited answers, reports, and podcasts.",
	keywords: [
		"notebooklm for teams",
		"notebooklm alternative",
		"notebooklm alternative for teams",
		"ai knowledge platform",
		"team knowledge base",
		"ai enterprise search",
		"enterprise search software",
		"ai research assistant",
		"cited ai answers",
		"team ai chat",
		"document q&a",
		"ai reports generator",
		"ai podcast generator",
		"collaborative ai workspace",
		"knowledge management ai",
		"Nowing",
	],
	openGraph: {
		title: "Nowing - NotebookLM for Teams | AI Knowledge Platform",
		description:
			"Nowing is the AI knowledge platform for teams. Turn your documents, connectors, and conversations into cited answers, reports, and podcasts.",
		url: "https://nowing.com",
		siteName: "Nowing",
		type: "website",
		images: [
			{
				url: "/og-image.png",
				width: 1200,
				height: 630,
				alt: "Nowing - NotebookLM for Teams, the AI knowledge platform",
			},
		],
		locale: "en_US",
	},
	twitter: {
		card: "summary_large_image",
		title: "Nowing - NotebookLM for Teams | AI Knowledge Platform",
		description:
			"Nowing is the AI knowledge platform for teams. Turn your documents, connectors, and conversations into cited answers, reports, and podcasts.",
		creator: "@NowingAI",
		site: "@NowingAI",
		images: [
			{
				url: "/og-image-twitter.png",
				width: 1200,
				height: 630,
				alt: "Nowing - NotebookLM for Teams, the AI knowledge platform",
			},
		],
	},
};

export default function RootLayout({
	children,
}: Readonly<{
	children: React.ReactNode;
}>) {
	// Using client-side i18n
	// Language can be switched dynamically through LanguageSwitcher component
	// Locale state is managed by LocaleContext and persisted in localStorage
	return (
		<html lang="en" suppressHydrationWarning>
			<head>
				<OrganizationJsonLd />
				<WebSiteJsonLd />
				<SoftwareApplicationJsonLd />
			</head>
			<body className={cn(roboto.className, "bg-white dark:bg-black antialiased h-full w-full ")}>
				<PostHogProvider>
					<LocaleProvider>
						<I18nProvider>
							<ThemeProvider
								attribute="class"
								enableSystem
								disableTransitionOnChange
								defaultTheme="system"
							>
								<PlatformProvider>
									<RootProvider>
										<ReactQueryClientProvider>
											<ZeroProvider>
												<GlobalLoadingProvider>{children}</GlobalLoadingProvider>
											</ZeroProvider>
										</ReactQueryClientProvider>
										<Toaster />
										<AnnouncementToastProvider />
									</RootProvider>
								</PlatformProvider>
							</ThemeProvider>
						</I18nProvider>
					</LocaleProvider>
				</PostHogProvider>
			</body>
		</html>
	);
}
