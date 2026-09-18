// auto-deploy verified - trigger-recompile-turbopack
import type { Metadata, Viewport } from "next";
import { getTranslations } from "next-intl/server";
import "./globals.css";
import { Instrument_Serif, Inter, JetBrains_Mono } from "next/font/google";
import Script from "next/script";
import { AnnouncementToastProvider } from "@/components/announcements/AnnouncementToastProvider";
import { DesktopUpdateToast } from "@/components/desktop/desktop-update-toast";
import { AuthCutoverPurge } from "@/components/providers/AuthCutoverPurge";
import { GlobalLoadingProvider } from "@/components/providers/GlobalLoadingProvider";
import { I18nProvider } from "@/components/providers/I18nProvider";
import { PostHogProvider } from "@/components/providers/PostHogProvider";
import { ZeroProvider } from "@/components/providers/ZeroProvider";
import {
	OrganizationJsonLd,
	SoftwareApplicationJsonLd,
	WebSiteJsonLd,
} from "@/components/seo/json-ld";
import { ThemeProvider } from "@/components/theme/theme-provider";
import { Toaster } from "@/components/ui/sonner";
import { LocaleProvider } from "@/contexts/LocaleContext";
import { PlatformProvider } from "@/contexts/platform-context";
import { BUILD_TIME_AUTH_TYPE } from "@/lib/env-config";
import { ReactQueryClientProvider } from "@/lib/query-client/query-client.provider";
import { getRuntimeAuthInitScript, resolveRuntimeAuthUiMode } from "@/lib/runtime-auth-config";
import { cn } from "@/lib/utils";

const inter = Inter({
	subsets: ["latin", "vietnamese"],
	display: "swap",
	variable: "--font-inter",
});

const instrumentSerif = Instrument_Serif({
	subsets: ["latin"],
	weight: ["400"],
	style: ["normal", "italic"],
	display: "swap",
	variable: "--font-instrument-serif",
});

const jetbrainsMono = JetBrains_Mono({
	subsets: ["latin", "vietnamese"],
	display: "swap",
	variable: "--font-jetbrains-mono",
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

export async function generateMetadata(): Promise<Metadata> {
	const t = await getTranslations("common");
	const title = t("layout_meta_title");
	const description = t("layout_meta_description");
	const ogDescription = t("layout_meta_og_description");
	return {
	metadataBase: new URL("https://www.nowing.com"),
	alternates: {
		canonical: "https://www.nowing.com",
	},
	title,
	description,
	keywords: [
		"open core research memory",
		"long-term research memory",
		"AI agent memory",
		"open web research platform",
		"web research for AI agents",
		"live web data for agents",
		"web scraping API",
		"reddit scraper api",
		"youtube scraper api",
		"deep research agent",
		"mcp server",
		"agent harness",
		"Nowing",
	],
	openGraph: {
		title,
		description: ogDescription,
		url: "https://www.nowing.com",
		siteName: "Nowing",
		type: "website",
		images: [
			{
				url: "/og-image.png",
				width: 1200,
				height: 630,
				alt: "Nowing, open-core long-term research memory for AI agents",
			},
		],
		locale: "en_US",
	},
	twitter: {
		card: "summary_large_image",
		title,
		description: ogDescription,
		creator: "@NowingAI",
		site: "@NowingAI",
		images: [
			{
				url: "/og-image-twitter.png",
				width: 1200,
				height: 630,
				alt: "Nowing, open-core long-term research memory for AI agents",
			},
		],
	},
	};
}

export default function RootLayout({
	children,
}: Readonly<{
	children: React.ReactNode;
}>) {
	// Using client-side i18n
	// Language can be switched dynamically through LanguageSwitcher component
	// Locale state is managed by LocaleContext and persisted in localStorage
	return (
		<html
			lang="en"
			data-nowing-auth-type={resolveRuntimeAuthUiMode(BUILD_TIME_AUTH_TYPE)}
			suppressHydrationWarning
		>
			<head>
				<Script id="nowing-runtime-auth-init" strategy="afterInteractive" suppressHydrationWarning>
					{getRuntimeAuthInitScript(BUILD_TIME_AUTH_TYPE)}
				</Script>
				<link rel="preconnect" href="https://api.github.com" />
				<OrganizationJsonLd />
				<WebSiteJsonLd />
				<SoftwareApplicationJsonLd />
			</head>
			<body
				className={cn(
					inter.variable,
					instrumentSerif.variable,
					jetbrainsMono.variable,
					inter.className,
					"font-sans bg-main-panel antialiased h-full w-full"
				)}
			>
				<ReactQueryClientProvider>
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
										<AuthCutoverPurge />
										<ZeroProvider>
											<GlobalLoadingProvider>{children}</GlobalLoadingProvider>
										</ZeroProvider>
										<DesktopUpdateToast />
										<Toaster />
										<AnnouncementToastProvider />
									</PlatformProvider>
								</ThemeProvider>
							</I18nProvider>
						</LocaleProvider>
					</PostHogProvider>
				</ReactQueryClientProvider>
			</body>
		</html>
	);
}
