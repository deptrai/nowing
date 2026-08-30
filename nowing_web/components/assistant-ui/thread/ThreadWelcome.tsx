"use client";

import { useAtomValue } from "jotai";
import { X } from "lucide-react";
import { useParams } from "next/navigation";
import { useTranslations } from "next-intl";
import { type FC, useMemo, useState } from "react";
import { toast } from "sonner";
import { currentUserAtom } from "@/atoms/user/user-query.atoms";
import { QuickstartPlaybookBuilder } from "@/components/assistant-ui/quickstart-playbook-builder";
import { Composer } from "./Composer";
import { OUTREACH_BETA_DISMISSED_KEY } from "./constants";
import type { ThreadProps } from "./types";

export const ThreadWelcome: FC<Pick<ThreadProps, "initialPrompt">> = ({ initialPrompt }) => {
	const tChat = useTranslations("chat");
	const [showBetaCard, setShowBetaCard] = useState(() => {
		if (typeof window === "undefined") return true;
		return window.localStorage.getItem(OUTREACH_BETA_DISMISSED_KEY) !== "true";
	});
	const { data: user } = useAtomValue(currentUserAtom);
	const params = useParams();
	const workspaceId = params?.workspace_id as string | undefined;

	const creditsCount = useMemo(() => {
		if (!user) return 500;
		const micros = user.credit_micros_balance ?? 5_000_000;
		return Math.max(0, Math.floor(micros / 10_000));
	}, [user]);

	const displayName = useMemo(() => {
		if (user?.display_name?.trim()) {
			return user.display_name.trim().split(/\s+/)[0];
		}
		if (user?.email) {
			return user.email.split("@")[0];
		}
		return "Luis";
	}, [user]);

	return (
		<div className="aui-thread-welcome-root flex min-h-0 flex-1 flex-col items-center justify-between p-4 sm:p-8 overflow-y-auto overflow-x-hidden">
			<div className="w-full flex items-center justify-end mb-2">
				<div
					className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-pink-500/10 dark:bg-pink-500/20 text-pink-600 dark:text-pink-400 text-xs font-semibold border border-pink-500/20 shadow-2xs"
					title={tChat("available_balance", {
						balance: ((user?.credit_micros_balance ?? 5_000_000) / 1_000_000).toFixed(2),
					})}
				>
					<span>🌸</span>
					<span className="font-mono font-bold">
						{new Intl.NumberFormat().format(creditsCount)}
					</span>{" "}
					Credits
				</div>
			</div>

			<section className="mx-auto w-full max-w-xl lg:max-w-2xl py-4 space-y-6">
				{/* Welcome Title */}
				<div className="text-center">
					<h1 className="text-2xl sm:text-3xl lg:text-[34px] font-serif tracking-tight text-foreground font-normal select-none">
						Welcome back, {displayName}.
					</h1>
				</div>

				{/* Real Assistant UI Composer in Center */}
				<div className="flex w-full items-start justify-center">
					<Composer initialPrompt={initialPrompt} hasActiveThread={false} />
				</div>

				{/* Quick Suggestion Chips */}
				<div className="flex flex-wrap items-center justify-center gap-2 max-w-full">
					{[
						{
							label: "Build a landing page",
							icon: "🌐",
							prompt:
								"Build a modern high-converting landing page for a SaaS product with hero section, features, testimonials, and email signup CTA.",
							mode: "web_builder",
						},
						{
							label: "Pricing page",
							icon: "💳",
							prompt:
								"Create a modern 3-tier pricing page with monthly/yearly toggle, comparison table, and FAQ section.",
							mode: "web_builder",
						},
						{
							label: "Lead capture",
							icon: "🎯",
							prompt:
								"Create an engaging lead capture page with an email opt-in form, value proposition highlights, and social proof badges.",
							mode: "web_builder",
						},
						{
							label: "Waitlist page",
							icon: "🚀",
							prompt:
								"Build an exciting viral waitlist coming-soon page with early access signup, countdown timer, and referral perk highlights.",
							mode: "web_builder",
						},
						{
							label: "Marketing report",
							icon: "📊",
							prompt:
								"Generate a clean interactive marketing report and whitepaper showcase page with key metric callouts and download CTA.",
							mode: "web_builder",
						},
						{
							label: tChat("card_pitch_title"),
							icon: "📑",
							prompt: tChat("card_pitch_prompt"),
							mode: "presentation_studio",
						},
						{
							label: tChat("card_marp_title"),
							icon: "📝",
							prompt: tChat("card_marp_prompt"),
							mode: "presentation_studio",
						},
						{
							label: "Summarize a meeting",
							icon: "🎙️",
							prompt: "Paste the meeting recording URL here",
							mode: "meeting_minutes",
						},
						{
							label: "Give me ideas",
							icon: "💡",
							prompt: tChat("card_icp_prompt"),
						},
						{
							label: tChat("card_bds_title"),
							icon: "🏢",
							prompt: tChat("card_bds_prompt"),
						},
						{
							label: tChat("card_it_title"),
							icon: "⚡",
							prompt: tChat("card_it_prompt"),
						},
					].map((chip) => (
						<button
							key={chip.label}
							type="button"
							onClick={() => {
								const targetWorkspace = workspaceId || "1";
								const modeParam = chip.mode ? `&mode=${chip.mode}` : "";
								window.location.href = `/dashboard/${targetWorkspace}/new-chat?q=${encodeURIComponent(chip.prompt)}${modeParam}`;
							}}
							className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full border border-border/80 bg-card hover:bg-muted/70 text-xs font-medium text-foreground transition-all hover:scale-102 cursor-pointer shadow-2xs focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
							title={`${chip.label}: ${chip.prompt}`}
						>
							<span aria-hidden="true">{chip.icon}</span>
							<span>{chip.label}</span>
						</button>
					))}
				</div>

				{/* Beta Outreach Agent Setup Card */}
				{showBetaCard && (
					<section
						className="p-3.5 sm:p-4 rounded-2xl border border-pink-500/20 bg-pink-500/5 dark:bg-pink-500/10 flex items-start sm:items-center justify-between gap-3 relative"
						aria-label="Set up your Outreach Agent"
					>
						<div className="flex items-center gap-3 min-w-0">
							<div
								className="size-9 sm:size-10 rounded-2xl bg-pink-500/15 flex items-center justify-center text-lg sm:text-xl shrink-0"
								aria-hidden="true"
							>
								🌸
							</div>
							<div className="min-w-0">
								<div className="flex items-center gap-2 flex-wrap">
									<h4 className="text-xs sm:text-sm font-bold text-foreground">
										Set up your Outreach Agent
									</h4>
									<span className="px-1.5 py-0.2 rounded bg-pink-500/20 text-pink-700 dark:text-pink-300 text-[10px] font-extrabold uppercase tracking-wider">
										BETA
									</span>
								</div>
								<p className="text-xs text-muted-foreground mt-0.5 max-w-xl truncate sm:whitespace-normal">
									15 minutes of setup, then it maximizes your replies — keeping quality leads
									flowing and your senders at full speed.
								</p>
							</div>
						</div>

						<div className="flex items-center gap-2 shrink-0 self-end sm:self-center">
							<button
								type="button"
								onClick={() => toast.success(tChat("modal_setup_outreach"))}
								className="px-3.5 py-1.5 rounded-xl bg-zinc-900 hover:bg-zinc-800 dark:bg-zinc-100 dark:hover:bg-zinc-200 dark:text-zinc-900 text-white text-xs font-semibold transition-colors cursor-pointer shadow-xs focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
								title={tChat("set_it_up")}
							>
								{tChat("set_it_up")}
							</button>
							<button
								type="button"
								onClick={() => {
									setShowBetaCard(false);
									if (typeof window !== "undefined") {
										window.localStorage.setItem(OUTREACH_BETA_DISMISSED_KEY, "true");
									}
								}}
								className="p-1 text-muted-foreground hover:text-foreground transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring rounded"
								aria-label="Dismiss"
								title="Dismiss"
							>
								<X className="size-3.5" aria-hidden="true" />
							</button>
						</div>
					</section>
				)}

				{/* Performance Summary Banner */}
				<div className="flex flex-wrap items-center justify-between gap-2 text-xs text-muted-foreground border-y border-border/60 py-2.5">
					<div className="flex items-center gap-1.5">
						<span className="text-emerald-600 dark:text-emerald-400 font-semibold">
							{tChat("lead_ready_badge")}
						</span>
						<span className="text-muted-foreground">•</span>
						<span className="text-foreground font-medium">{tChat("live_sources_badge")}</span>
					</div>
					<div className="flex items-center gap-3">
						<a
							href={workspaceId ? `/dashboard/${workspaceId}/user-settings` : "/dashboard"}
							className="text-muted-foreground hover:text-foreground font-medium transition-colors cursor-pointer rounded px-1 -mx-1 focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
							title={tChat("config_channels_link")}
						>
							{tChat("config_channels_link")}
						</a>
					</div>
				</div>

				{/* Conversational Quickstart Playbook Builder */}
				<QuickstartPlaybookBuilder />
			</section>
		</div>
	);
};
