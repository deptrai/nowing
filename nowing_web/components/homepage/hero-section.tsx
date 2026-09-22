"use client";
import { ChevronDown, Download } from "lucide-react";
import { AnimatePresence, motion, useReducedMotion } from "motion/react";
import Link from "next/link";
import { useTranslations } from "next-intl";
import React, { memo, useCallback, useEffect, useRef, useState } from "react";
import Balancer from "react-wrap-balancer";
import { HeroChatDemo, type HeroChatDemoScript } from "@/components/homepage/hero-chat-demo";
import { Button } from "@/components/ui/button";
import {
	DropdownMenu,
	DropdownMenuContent,
	DropdownMenuItem,
	DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { ExpandedMediaOverlay, useExpandedMedia } from "@/components/ui/expanded-gif-overlay";
import { ScrollArea, ScrollBar } from "@/components/ui/scroll-area";
import { Separator } from "@/components/ui/separator";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
	GITHUB_RELEASES_URL,
	getAssetLabel,
	usePrimaryDownload,
} from "@/lib/desktop-download-utils";
import { buildBackendUrl } from "@/lib/env-config";
import { trackLoginAttempt } from "@/lib/posthog/events";
import { cn } from "@/lib/utils";

const GoogleLogo = ({ className }: { className?: string }) => (
	<svg
		className={className}
		viewBox="0 0 24 24"
		xmlns="http://www.w3.org/2000/svg"
		role="img"
		aria-label="Google logo"
	>
		<title>Google logo</title>
		<path
			d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"
			fill="#4285F4"
		/>
		<path
			d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"
			fill="#34A853"
		/>
		<path
			d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"
			fill="#FBBC05"
		/>
		<path
			d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"
			fill="#EA4335"
		/>
	</svg>
);

type HeroUseCase = {
	id: string;
	title: string;
	description: string;
	src: string | null;
	/** Scripted chat demo shown when there is no recorded video. */
	demo?: HeroChatDemoScript;
};

type HeroCategory = {
	id: string;
	label: string;
	useCases: HeroUseCase[];
};

const HERO_TUTORIAL = "/homepage/hero_tutorial";

/*
 * Every scripted demo below mirrors a task the Nowing agent has actually run
 * end-to-end (see backend agent e2e suite). Recorded videos take precedence via
 * `src`; everything else plays the chat demo.
 */
const getCategories = (t: (key: string) => string): HeroCategory[] => [
	{
		id: "live-research",
		label: t("cat_live_research"),
		useCases: [
			{
				id: "deep-research",
				title: t("title_deep_research"),
				description: t("hero_the_agent_crawls_dozens"),
				src: null,
				demo: {
					prompt: t("prompt_deep_research"),
					steps: [
						{
							title: t("hero_research"),
							items: [t("deep_research_s1_i1"), t("deep_research_s1_i2")],
						},
						{
							title: t("hero_generate_report"),
							items: [t("deep_research_s2_i1")],
						},
					],
					rows: [
						{
							primary: t("deep_research_r1_p"),
							secondary: t("deep_research_r1_s"),
						},
						{
							primary: t("deep_research_r2_p"),
							secondary: t("deep_research_r2_s"),
						},
					],
					summary: t("hero_landscape_brief_saved_24"),
				},
			},
			{
				id: "academic-research",
				title: t("title_academic_research"),
				description: t("hero_sweep_recent_papers_preprints"),
				src: null,
				demo: {
					prompt: t("prompt_academic_research"),
					steps: [
						{
							title: t("hero_google_search"),
							items: [t("academic_research_s1_i1")],
						},
						{
							title: t("hero_web_crawler"),
							items: [t("academic_research_s2_i1"), t("academic_research_s2_i2")],
						},
						{
							title: t("hero_generate_report"),
							items: [t("academic_research_s3_i1")],
						},
					],
					rows: [
						{
							primary: t("academic_research_r1_p"),
							secondary: t("academic_research_r1_s"),
						},
						{
							primary: t("academic_research_r2_p"),
							secondary: t("academic_research_r2_s"),
						},
					],
					summary: t("hero_literature_brief_saved_every"),
				},
			},
			{
				id: "financial-research",
				title: t("title_financial_research"),
				description: t("hero_pull_earnings_coverage_analyst"),
				src: null,
				demo: {
					prompt: t("prompt_financial_research"),
					steps: [
						{
							title: t("hero_google_search"),
							items: [t("financial_research_s1_i1")],
						},
						{
							title: t("hero_youtube"),
							items: [t("financial_research_s2_i1")],
						},
						{
							title: t("hero_reddit"),
							items: [t("financial_research_s3_i1")],
						},
					],
					rows: [
						{
							primary: "Data-center revenue beat leads coverage",
							secondary: "cited in 7 of 10 top results",
						},
						{
							primary: t("financial_research_r2_p"),
							secondary: "transcripts: 5 bullish · 3 cautious",
						},
						{
							primary: "Retail sentiment net positive",
							secondary: "top threads focus on supply constraints",
						},
					],
					summary: t("hero_cited_earnings_brief_saved"),
				},
			},
			{
				id: "geo-monitoring",
				title: t("title_geo_monitoring"),
				description: t("desc_geo_monitoring"),
				src: null,
				demo: {
					prompt: t("prompt_geo_monitoring"),
					steps: [
						{
							title: t("hero_google_search"),
							items: [t("geo_monitoring_s1_i1"), t("geo_monitoring_s1_i2")],
						},
						{
							title: t("hero_plan_tasks"),
							items: [t("geo_monitoring_s2_i1"), t("geo_monitoring_s2_i2")],
						},
					],
					rows: [
						{
							primary: t("geo_monitoring_r1_p"),
							secondary: t("geo_monitoring_r1_s"),
						},
						{
							primary: t("geo_monitoring_r2_p"),
							secondary: t("geo_monitoring_r2_s"),
						},
					],
					summary: t("hero_citation_gap_report_saved"),
				},
			},
		],
	},
	{
		id: "ci-workflows",
		label: t("cat_ci_workflows"),
		useCases: [
			{
				id: "launch-impact",
				title: t("title_launch_impact"),
				description: t("hero_one_prompt_chains_google"),
				src: null,
				demo: {
					prompt: t("prompt_launch_impact"),
					steps: [
						{
							title: t("hero_google_search"),
							items: [t("launch_impact_s1_i1")],
						},
						{
							title: t("hero_reddit"),
							items: [t("launch_impact_s2_i1")],
						},
						{
							title: t("hero_youtube"),
							items: [t("launch_impact_s3_i1")],
						},
						{
							title: t("hero_plan_tasks"),
							items: [t("launch_impact_s4_i1")],
						},
					],
					rows: [
						{
							primary: t("launch_impact_r1_p"),
							secondary: t("launch_impact_r1_s"),
						},
						{
							primary: t("launch_impact_r2_p"),
							secondary: t("launch_impact_r2_s"),
						},
						{
							primary: t("launch_impact_r3_p"),
							secondary: t("launch_impact_r3_s"),
						},
					],
					summary: t("launch_impact_summary"),
				},
			},
			{
				id: "local-teardown",
				title: t("title_local_teardown"),
				description: t("hero_google_maps_finds_the"),
				src: null,
				demo: {
					prompt: t("prompt_local_teardown"),
					steps: [
						{
							title: t("hero_google_maps"),
							items: [t("local_teardown_s1_i1")],
						},
						{
							title: t("hero_web_crawler"),
							items: [t("gym_item_1"), t("gym_item_2")],
						},
						{
							title: t("hero_google_search"),
							items: [t("local_teardown_s3_i1")],
						},
					],
					rows: [
						{
							primary: t("local_teardown_r1_p"),
							secondary: t("local_teardown_r1_s"),
						},
						{
							primary: t("local_teardown_r2_p"),
							secondary: t("local_teardown_r2_s"),
						},
						{
							primary: t("local_teardown_r3_p"),
							secondary: t("local_teardown_r3_s"),
						},
					],
					summary: t("hero_maps_crawler_search_in"),
				},
			},
			{
				id: "pricing-watch",
				title: t("title_pricing_watch"),
				description: t("desc_pricing_watch"),
				src: null,
				demo: {
					prompt: t("prompt_pricing_watch"),
					steps: [
						{
							title: t("hero_plan_tasks"),
							items: [t("pricing_watch_s1_i1"), t("pricing_watch_s1_i2")],
						},
						{
							title: t("hero_web_crawler"),
							items: [t("pricing_watch_s2_i1"), t("pricing_watch_s2_i2"), t("pricing_watch_s2_i3")],
						},
						{
							title: t("hero_create_automation"),
							items: [t("pricing_watch_s3_i1")],
						},
					],
					rows: [
						{
							primary: t("pricing_watch_r1_p"),
							secondary: t("pricing_watch_r1_s"),
						},
						{
							primary: t("pricing_watch_r2_p"),
							secondary: t("pricing_watch_r2_s"),
						},
						{
							primary: t("pricing_watch_r3_p"),
							secondary: t("pricing_watch_r3_s"),
						},
					],
					summary: t("pricing_watch_summary"),
				},
			},
			{
				id: "site-diff",
				title: t("title_site_diff"),
				description: t("desc_site_diff"),
				src: null,
				demo: {
					prompt: t("prompt_site_diff"),
					steps: [
						{
							title: t("hero_web_crawler"),
							items: [t("site_diff_s1_i1"), t("site_diff_s1_i2")],
						},
						{
							title: t("hero_create_automation"),
							items: [t("site_diff_s2_i1")],
						},
					],
					rows: [
						{
							primary: t("site_diff_r1_p"),
							secondary: t("site_diff_r1_s"),
						},
						{
							primary: t("site_diff_r2_p"),
							secondary: t("site_diff_r2_s"),
						},
					],
					summary: t("hero_brief_saved_to_workspace"),
				},
			},
			{
				id: "serp-watch",
				title: t("title_serp_watch"),
				description: t("hero_automations_track_the_google"),
				src: null,
				demo: {
					prompt: t("prompt_serp_watch"),
					steps: [
						{
							title: t("hero_google_search"),
							items: [t("serp_watch_s1_i1")],
						},
						{
							title: t("hero_plan_tasks"),
							items: [t("diff_item_1"), t("diff_item_2")],
						},
						{
							title: t("hero_create_automation"),
							items: [t("serp_watch_s3_i1")],
						},
					],
					rows: [
						{
							primary: t("serp_watch_r1_p"),
							secondary: t("serp_watch_r1_s"),
						},
						{
							primary: t("serp_watch_r2_p"),
							secondary: t("serp_watch_r2_s"),
						},
					],
					summary: t("serp_watch_summary"),
				},
			},
			{
				id: "switcher-mining",
				title: t("title_switcher_mining"),
				description: t("hero_find_the_people_actively"),
				src: null,
				demo: {
					prompt: t("prompt_switcher_mining"),
					steps: [
						{
							title: t("hero_reddit"),
							items: [t("switcher_mining_s1_i1"), t("switcher_mining_s1_i2")],
						},
						{
							title: t("hero_plan_tasks"),
							items: [t("rank_item_1"), t("rank_item_2")],
						},
					],
					rows: [
						{
							primary: t("switcher_mining_r1_p"),
							secondary: t("switcher_mining_r1_s"),
						},
						{
							primary: t("switcher_mining_r2_p"),
							secondary: t("switcher_mining_r2_s"),
						},
					],
					summary: t("hero_outreach_ready_summaries_drafted"),
				},
			},
		],
	},
	{
		id: "artifacts",
		label: t("cat_artifacts"),
		useCases: [
			{
				id: "report",
				title: t("title_report"),
				description: t("desc_report"),
				src: `${HERO_TUTORIAL}/ReportGenGif_compressed.mp4`,
			},
			{
				id: "podcast",
				title: t("title_podcast"),
				description: t("desc_podcast"),
				src: `${HERO_TUTORIAL}/PodcastGenGif.mp4`,
			},
			{
				id: "presentation",
				title: t("title_presentation"),
				description: t("desc_presentation"),
				src: `${HERO_TUTORIAL}/video_gen_surf.mp4`,
			},
			{
				id: "image-gen",
				title: t("title_image_gen"),
				description: t("desc_image_gen"),
				src: `${HERO_TUTORIAL}/ImageGenGif.mp4`,
			},
		],
	},
	{
		id: "automations",
		label: t("cat_automations"),
		useCases: [
			{
				id: "competitor-360",
				title: t("title_competitor_360"),
				description: t("hero_an_automation_chains_four"),
				src: null,
				demo: {
					prompt: t("prompt_competitor_360"),
					steps: [
						{
							title: t("hero_web_crawler"),
							items: [t("competitor_360_s1_i1")],
						},
						{
							title: t("hero_google_search"),
							items: [t("competitor_360_s2_i1")],
						},
						{
							title: t("hero_reddit"),
							items: [t("competitor_360_s3_i1")],
						},
						{
							title: t("hero_youtube"),
							items: [t("competitor_360_s4_i1")],
						},
						{
							title: t("hero_create_automation"),
							items: [t("competitor_360_s5_i1")],
						},
					],
					rows: [
						{
							primary: t("competitor_360_r1_p"),
							secondary: t("competitor_360_r1_s"),
						},
						{
							primary: t("competitor_360_r2_p"),
							secondary: t("competitor_360_r2_s"),
						},
						{
							primary: t("competitor_360_r3_p"),
							secondary: t("competitor_360_r3_s"),
						},
					],
					summary: t("competitor_360_summary"),
				},
			},
			{
				id: "cited-briefs",
				title: t("title_cited_briefs"),
				description: t("hero_everything_the_agents_gather"),
				src: null,
				demo: {
					prompt: t("prompt_cited_briefs"),
					steps: [
						{
							title: t("hero_plan_tasks"),
							items: [t("cited_briefs_s1_i1")],
						},
						{
							title: t("hero_create_automation"),
							items: [t("cited_briefs_s2_i1")],
						},
					],
					rows: [
						{
							primary: t("cited_briefs_r1_p"),
							secondary: t("cited_briefs_r1_s"),
						},
						{
							primary: t("cited_briefs_r2_p"),
							secondary: t("cited_briefs_r2_s"),
						},
					],
					summary: t("hero_automation_created_first_brief"),
				},
			},
			{
				id: "event-triggers",
				title: t("title_event_triggers"),
				description: t("hero_automations_can_fire_on"),
				src: null,
				demo: {
					prompt: t("prompt_event_triggers"),
					steps: [
						{
							title: t("hero_create_automation"),
							items: [t("event_triggers_s1_i1"), t("event_triggers_s1_i2")],
						},
					],
					rows: [
						{
							primary: t("event_triggers_r1_p"),
							secondary: t("event_triggers_r1_s"),
						},
						{
							primary: t("event_triggers_r2_p"),
							secondary: t("event_triggers_r2_s"),
						},
					],
					summary: t("hero_event_triggered_automation_live"),
				},
			},
		],
	},
	{
		id: "desktop-app",
		label: t("cat_desktop_app"),
		useCases: [
			{
				id: "general-assist",
				title: t("title_general_assist"),
				description: t("desc_general_assist"),
				src: `${HERO_TUTORIAL}/general_assist.mp4`,
			},
			{
				id: "quick-assist",
				title: t("title_quick_assist"),
				description: t("desc_quick_assist"),
				src: `${HERO_TUTORIAL}/quick_assist.mp4`,
			},
			{
				id: "screenshot-assist",
				title: t("title_screenshot_assist"),
				description: t("desc_screenshot_assist"),
				src: `${HERO_TUTORIAL}/screenshot_assist.mp4`,
			},
			{
				id: "folder-watch",
				title: t("title_folder_watch"),
				description: t("hero_auto_sync_a_local"),
				src: `${HERO_TUTORIAL}/folder_watch.mp4`,
			},
		],
	},
];

export function HeroSection() {
	const t = useTranslations("home");
	return (
		<div className="mx-auto w-full max-w-7xl min-w-0 pt-36">
			<div className="mt-4 flex w-full min-w-0 flex-col items-start px-2 md:px-8 xl:px-0">
				<h1
					className={cn(
						"relative mt-4 max-w-4xl text-left font-serif font-normal text-3xl sm:text-4xl md:text-5xl lg:text-[52px] tracking-tight leading-[1.14] text-balance text-neutral-900 dark:text-neutral-50"
					)}
				>
					<Balancer>
						{t("hero_open_core_memory")}{" "}
						<span className="italic font-serif font-normal">{t("hero_for_ai_agents")}</span>
					</Balancer>
				</h1>
				<div className="mt-4 flex w-full flex-col items-start justify-between gap-4 md:mt-6 md:flex-row md:items-end md:gap-10">
					<div>
						<p
							className={cn(
								"relative mb-8 max-w-2xl text-left text-sm sm:text-base text-neutral-600 font-sans leading-relaxed dark:text-neutral-400"
							)}
						>
							{t("hero_subdescription")}
						</p>

						<div className="relative mb-4 flex w-full flex-col justify-center gap-y-2 sm:flex-row sm:justify-start sm:space-y-0 sm:space-x-4">
							<GetStartedButton />
							<DownloadButton />
						</div>
					</div>
				</div>
				<BrowserWindow />
			</div>
		</div>
	);
}

function GetStartedButton() {
	const t = useTranslations("home");
	const [isRedirecting, setIsRedirecting] = useState(false);

	const handleGoogleLogin = () => {
		if (isRedirecting) return;
		setIsRedirecting(true);
		trackLoginAttempt("google");
		window.location.href = buildBackendUrl("/auth/google/authorize-redirect");
	};

	return (
		<>
			<Button
				type="button"
				variant="ghost"
				onClick={handleGoogleLogin}
				disabled={isRedirecting}
				className="runtime-auth-google h-14 w-full cursor-pointer gap-3 rounded-lg border border-white bg-white text-center text-base font-medium text-[#1f1f1f] shadow-sm transition duration-150 hover:bg-zinc-100 hover:text-[#1f1f1f] sm:w-56 dark:border-white"
			>
				<GoogleLogo className="h-5 w-5" aria-hidden="true" />
				<span>{t("hero_continue_with_google")}</span>
			</Button>
			<Button
				asChild
				variant="ghost"
				className="runtime-auth-local h-14 w-full rounded-lg bg-black text-center text-base font-medium text-white shadow-sm ring-1 shadow-black/10 ring-black/10 transition duration-150 active:scale-98 hover:bg-black sm:w-52 dark:bg-white dark:text-black dark:hover:bg-white"
			>
				<Link href="/login">{t("hero_get_started")}</Link>
			</Button>
		</>
	);
}

function DownloadButton() {
	const t = useTranslations("home");
	const { os, primary, alternatives, isMobileOS } = usePrimaryDownload();

	const fallbackUrl = GITHUB_RELEASES_URL;
	const mobileDisabledLabel = t("mobile_disabled");

	if (isMobileOS) {
		return (
			<Button
				type="button"
				variant="ghost"
				disabled
				className="h-14 w-full gap-2 rounded-lg border border-neutral-200 bg-white text-center text-base font-medium text-neutral-700 shadow-sm transition duration-150 sm:w-auto sm:px-6 dark:border-neutral-700 dark:bg-neutral-900 dark:text-neutral-200"
			>
				<Download className="size-4" aria-hidden="true" />
				{mobileDisabledLabel}
			</Button>
		);
	}

	if (!primary) {
		return (
			<Button
				asChild
				variant="ghost"
				className="h-14 w-full gap-2 rounded-lg border border-neutral-200 bg-white text-center text-base font-medium text-neutral-700 shadow-sm transition duration-150 active:scale-98 hover:bg-neutral-50 sm:w-auto sm:px-6 dark:border-neutral-700 dark:bg-neutral-900 dark:text-neutral-200 dark:hover:bg-neutral-800"
			>
				<a href={fallbackUrl} target="_blank" rel="noopener noreferrer">
					<Download className="size-4" aria-hidden="true" />
					{t("hero_download_for", { os })}
				</a>
			</Button>
		);
	}

	return (
		<div className="flex h-14 w-full items-stretch sm:w-auto">
			<Button
				asChild
				variant="ghost"
				className="h-auto flex-1 gap-2 rounded-l-lg rounded-r-none border border-r-0 border-neutral-200 bg-white px-5 text-base font-medium text-neutral-700 shadow-sm transition duration-150 active:scale-[0.99] hover:bg-neutral-50 dark:border-neutral-700 dark:bg-neutral-900 dark:text-neutral-200 dark:hover:bg-neutral-800"
			>
				<a href={primary.url}>
					<Download className="size-4 shrink-0" aria-hidden="true" />
					{t("hero_download_for", { os })}
				</a>
			</Button>
			<DropdownMenu>
				<DropdownMenuTrigger asChild>
					<Button
						type="button"
						variant="ghost"
						aria-label={t("hero_more_download_options")}
						className="h-auto rounded-l-none rounded-r-lg border border-neutral-200 bg-white px-2.5 text-neutral-500 shadow-sm transition duration-150 hover:bg-neutral-50 dark:border-neutral-700 dark:bg-neutral-900 dark:text-neutral-400 dark:hover:bg-neutral-800"
					>
						<ChevronDown className="size-4" aria-hidden />
					</Button>
				</DropdownMenuTrigger>
				<DropdownMenuContent align="end" className="w-64">
					{alternatives.map((asset) => (
						<DropdownMenuItem key={asset.name} asChild>
							<a href={asset.url} className="cursor-pointer">
								<Download className="mr-2 size-3.5" aria-hidden="true" />
								{getAssetLabel(asset.name)}
							</a>
						</DropdownMenuItem>
					))}
					<DropdownMenuItem asChild>
						<a
							href={fallbackUrl}
							target="_blank"
							rel="noopener noreferrer"
							className="cursor-pointer"
						>
							{t("hero_all_downloads")}
						</a>
					</DropdownMenuItem>
				</DropdownMenuContent>
			</DropdownMenu>
		</div>
	);
}

const TabVideo = memo(function TabVideo({
	src,
	title,
	reduceMotion,
}: {
	src: string;
	title: string;
	reduceMotion: boolean;
}) {
	const t = useTranslations("home");
	const videoRef = useRef<HTMLVideoElement>(null);
	const [hasLoaded, setHasLoaded] = useState(false);

	useEffect(() => {
		setHasLoaded(false);
		const video = videoRef.current;
		if (!video) return;
		video.currentTime = 0;
		// Respect reduced-motion: show the first frame and expose controls instead of autoplaying.
		if (!reduceMotion) {
			video.play().catch(() => {});
		}
	}, [reduceMotion]);

	const handleCanPlay = useCallback(() => {
		setHasLoaded(true);
	}, []);

	return (
		<div className="relative">
			<video
				ref={videoRef}
				key={src}
				src={src}
				preload={reduceMotion ? "metadata" : "auto"}
				aria-label={t("hero_demo_label", { title })}
				autoPlay={!reduceMotion}
				controls={reduceMotion}
				loop
				muted
				playsInline
				onCanPlay={handleCanPlay}
				className="aspect-video w-full rounded-lg sm:rounded-xl"
			/>
			{!hasLoaded && (
				<Skeleton className="absolute inset-0 aspect-video w-full rounded-lg bg-neutral-100 motion-reduce:animate-none sm:rounded-xl dark:bg-neutral-800" />
			)}
		</div>
	);
});

const UseCasePane = memo(function UseCasePane({
	useCase,
	reduceMotion,
}: {
	useCase: HeroUseCase;
	reduceMotion: boolean;
}) {
	const t = useTranslations("home");
	const { expanded, open, close } = useExpandedMedia();
	const hasVideo = Boolean(useCase.src);

	const media = hasVideo ? (
		<Button
			type="button"
			variant="ghost"
			onClick={open}
			aria-label={t("hero_expand_demo", { title: useCase.title })}
			className="h-auto w-full cursor-pointer rounded-none bg-neutral-50 p-2 hover:bg-neutral-50 sm:p-3 dark:bg-neutral-950 dark:hover:bg-neutral-950"
		>
			<TabVideo src={useCase.src as string} title={useCase.title} reduceMotion={reduceMotion} />
		</Button>
	) : (
		<div className="bg-neutral-50 p-2 sm:p-3 dark:bg-neutral-950">
			{useCase.demo && <HeroChatDemo demo={useCase.demo} reduceMotion={reduceMotion} />}
		</div>
	);

	const card = (
		<div className="relative overflow-hidden rounded-tl-xl rounded-tr-xl bg-white shadow-sm ring-1 shadow-black/10 ring-black/10 dark:bg-neutral-950">
			<div className="flex items-center gap-3 border-b border-neutral-200/60 px-4 py-3 sm:px-6 sm:py-4 dark:border-neutral-700/60">
				<div className="min-w-0">
					<h2 className="truncate text-base font-semibold text-neutral-900 sm:text-lg dark:text-white">
						{useCase.title}
					</h2>
					<p className="text-sm text-neutral-500 text-pretty dark:text-neutral-400">
						{useCase.description}
					</p>
				</div>
			</div>
			{media}
		</div>
	);

	return (
		<>
			{reduceMotion ? (
				card
			) : (
				<motion.div
					initial={{ opacity: 0, scale: 0.99, filter: "blur(10px)" }}
					animate={{ opacity: 1, scale: 1, filter: "blur(0px)" }}
					transition={{ duration: 0.3, ease: "easeOut" }}
					className="will-change-transform"
				>
					{card}
				</motion.div>
			)}

			<AnimatePresence>
				{expanded && hasVideo && (
					<ExpandedMediaOverlay
						src={useCase.src as string}
						alt={t("hero_demo_alt", { title: useCase.title })}
						onClose={close}
					/>
				)}
			</AnimatePresence>
		</>
	);
});

const CategoryPanel = memo(function CategoryPanel({
	category,
	reduceMotion,
}: {
	category: HeroCategory;
	reduceMotion: boolean;
}) {
	return (
		<div className="flex w-full flex-col gap-3">
			<Tabs
				defaultValue={category.useCases[0]?.id}
				orientation="vertical"
				className="flex w-full flex-col gap-3 md:flex-row md:gap-4"
			>
				<ScrollArea className="w-full md:w-56 md:shrink-0">
					<TabsList className="flex h-auto w-max gap-1 bg-transparent p-0 md:w-full md:flex-col md:items-stretch">
						{category.useCases.map((useCase) => (
							<TabsTrigger
								key={useCase.id}
								value={useCase.id}
								className="h-auto shrink-0 touch-manipulation justify-start rounded-md px-3 py-2 text-left text-xs whitespace-normal data-[state=active]:bg-background data-[state=active]:shadow-sm sm:text-sm md:w-full"
							>
								{useCase.title}
							</TabsTrigger>
						))}
					</TabsList>
					<ScrollBar orientation="horizontal" className="md:hidden" />
				</ScrollArea>
				<div className="min-w-0 flex-1">
					{category.useCases.map((useCase) => (
						<TabsContent key={useCase.id} value={useCase.id} className="mt-0">
							<UseCasePane useCase={useCase} reduceMotion={reduceMotion} />
						</TabsContent>
					))}
				</div>
			</Tabs>
		</div>
	);
});

const BrowserWindow = () => {
	const t = useTranslations("home");
	const categories = getCategories(t);
	const [activeCategory, setActiveCategory] = useState(categories[0].id);
	const reduceMotion = useReducedMotion() ?? false;

	return (
		<Tabs
			value={activeCategory}
			onValueChange={setActiveCategory}
			className="relative my-4 flex w-full flex-col items-start justify-start gap-0 overflow-hidden rounded-2xl shadow-2xl md:my-12"
		>
			<div className="flex w-full items-center justify-start overflow-hidden bg-gray-200 py-4 pl-4 dark:bg-neutral-800">
				<div className="mr-6 flex items-center gap-2">
					<div className="size-3 rounded-full bg-red-500" />
					<div className="size-3 rounded-full bg-yellow-500" />
					<div className="size-3 rounded-full bg-green-500" />
				</div>
				<ScrollArea className="min-w-0 flex-1">
					<TabsList className="flex h-auto w-max items-center gap-1 bg-transparent p-0 pr-4">
						{categories.map((category, index) => (
							<React.Fragment key={category.id}>
								<TabsTrigger
									value={category.id}
									className="h-auto shrink-0 touch-manipulation gap-1.5 rounded-md px-2.5 py-1 text-xs data-[state=active]:bg-background data-[state=active]:shadow sm:text-sm"
								>
									{category.label}
								</TabsTrigger>
								{index !== categories.length - 1 && (
									<Separator
										orientation="vertical"
										className="h-4 bg-neutral-300 dark:bg-neutral-700"
									/>
								)}
							</React.Fragment>
						))}
					</TabsList>
					<ScrollBar orientation="horizontal" />
				</ScrollArea>
			</div>
			<div className="w-full overflow-hidden bg-gray-100/50 px-4 pt-4 dark:bg-neutral-950">
				{categories.map((category) => (
					<TabsContent key={category.id} value={category.id} className="mt-0">
						<CategoryPanel category={category} reduceMotion={reduceMotion} />
					</TabsContent>
				))}
			</div>
		</Tabs>
	);
};
