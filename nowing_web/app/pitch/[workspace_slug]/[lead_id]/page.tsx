import { CalendarCheck, ShieldCheck } from "lucide-react";
import type { Metadata } from "next";
import { headers } from "next/headers";
import Link from "next/link";
import { notFound } from "next/navigation";
import { PitchEngagementBeacon } from "@/components/pitch/engagement-beacon";
import { PitchRoiCalculator } from "@/components/pitch/roi-calculator";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { SERVER_BACKEND_URL } from "@/lib/env-config";

// Story 37.5 (AD-119): generated 1-click mini-pitch portal served via the
// single multi-tenant SSR route pitch.nowing.ai/[workspace_slug]/[lead_id].
// Content is generated + sanitized backend-side (app/services/pitch_portal.py)
// and cached per lead; this page only renders it.  All dynamic prospect
// fields render as text nodes — React escapes them, so no Stored XSS
// surface (AC-3).  The engagement beacon mount is Story 37.6.

interface PitchExecCard {
	tone: "red" | "yellow" | "green";
	title: string;
	body: string;
}

interface PitchRoiDefaults {
	default_sales_reps: number;
	min_sales_reps: number;
	max_sales_reps: number;
	meetings_per_rep_per_month: number;
	data_saving_per_rep_vnd: number;
}

interface PitchMeta {
	lead_id: string;
	workspace_id: number;
	company_name: string;
	industry: string | null;
	location: string | null;
	workspace_name: string;
	booking_path: string;
	opt_out_path: string | null;
	headline: string | null;
	exec_summary: string | null;
	exec_cards: PitchExecCard[];
	logo_url: string | null;
	roi: PitchRoiDefaults | null;
}

async function getPitchMeta(
	workspaceSlug: string,
	leadId: string,
	clientIp: string | null
): Promise<PitchMeta | null> {
	// The backend rate-limits per client IP; forward the real visitor's IP so
	// server-side fetches don't all share (and exhaust) the Next.js server's IP.
	const forwardHeaders: Record<string, string> = {};
	if (clientIp) {
		forwardHeaders["x-real-ip"] = clientIp;
		forwardHeaders["x-forwarded-for"] = clientIp;
	}
	const url = `${SERVER_BACKEND_URL}/api/v1/public/pitch/${encodeURIComponent(workspaceSlug)}/${encodeURIComponent(leadId)}/meta`;

	const attempt = (cached: boolean) =>
		fetch(
			url,
			cached
				? // Edge/ISR cache keeps TTFB low per AD-119; meta rarely changes.
					{ next: { revalidate: 60 }, headers: forwardHeaders }
				: { cache: "no-store", headers: forwardHeaders }
		).catch(() => null);

	let res = await attempt(true);
	// 404 is a definitive invalid link; anything else may be transient, so
	// retry once uncached before giving up.
	if (res?.status !== 404 && !res?.ok) {
		res = await attempt(false);
	}
	if (!res || !res.ok) return null;
	return (await res.json().catch(() => null)) as PitchMeta | null;
}

export const metadata: Metadata = {
	title: "Mini Pitch",
	robots: { index: false, follow: false },
};

const TONE_STYLES: Record<PitchExecCard["tone"], string> = {
	red: "border-l-4 border-l-red-500/70",
	yellow: "border-l-4 border-l-amber-500/70",
	green: "border-l-4 border-l-emerald-500/70",
};

export default async function PitchPortalPage({
	params,
}: {
	params: Promise<{ workspace_slug: string; lead_id: string }>;
}) {
	const { workspace_slug: workspaceSlug, lead_id: leadId } = await params;
	const requestHeaders = await headers();
	const clientIp =
		requestHeaders.get("x-forwarded-for")?.split(",")[0]?.trim() || requestHeaders.get("x-real-ip");
	const meta = await getPitchMeta(workspaceSlug, leadId, clientIp);
	if (!meta) notFound();

	const optOutPath = meta.opt_out_path || `/pitch/${workspaceSlug}/${leadId}/opt-out`;

	return (
		<main className="min-h-screen bg-gradient-to-br from-background via-background to-primary/5">
			<PitchEngagementBeacon workspaceRef={workspaceSlug} leadId={leadId} />

			<div className="mx-auto max-w-3xl px-4 py-10 sm:py-16 space-y-8 sm:space-y-10">
				{/* Dual-branding hero: prospect logo x sender workspace */}
				<section data-pitch-section="hero" className="text-center space-y-4">
					<div className="flex items-center justify-center gap-3">
						{meta.logo_url ? (
							// eslint-disable-next-line @next/next/no-img-element -- external favicon, not worth the optimizer hop
							<img
								src={meta.logo_url}
								alt={`Logo ${meta.company_name}`}
								className="h-10 w-10 rounded-md object-contain"
							/>
						) : null}
						<span className="text-muted-foreground/60 text-xl font-light">×</span>
						<p className="text-sm font-medium text-muted-foreground uppercase tracking-wide">
							{meta.workspace_name}
						</p>
					</div>
					<p className="text-xs text-muted-foreground">
						🔒 Báo cáo nội bộ dành riêng cho {meta.company_name}
					</p>
					<h1 className="text-2xl sm:text-4xl font-bold tracking-tight">
						{meta.headline || `Dành riêng cho ${meta.company_name}`}
					</h1>
					<p className="text-lg text-muted-foreground">
						{[meta.industry, meta.location].filter(Boolean).join(" · ") ||
							"Bản tóm tắt giá trị trong 30 giây"}
					</p>
				</section>

				{/* 30-second executive summary + card stack */}
				<section data-pitch-section="exec-summary" className="space-y-4">
					{meta.exec_summary ? (
						<Card className="bg-card/80 backdrop-blur-xl">
							<CardHeader>
								<CardTitle>Tóm tắt dành cho ban lãnh đạo</CardTitle>
								<CardDescription className="text-base leading-relaxed text-foreground/80">
									{meta.exec_summary}
								</CardDescription>
							</CardHeader>
						</Card>
					) : null}
					<div className="space-y-3">
						{meta.exec_cards.map((card) => (
							<Card
								key={card.title}
								className={`bg-card/50 backdrop-blur-xl ${TONE_STYLES[card.tone] ?? ""}`}
							>
								<CardHeader className="py-4">
									<CardTitle className="text-base">{card.title}</CardTitle>
									<CardDescription>{card.body}</CardDescription>
								</CardHeader>
							</Card>
						))}
					</div>
				</section>

				{/* Interactive ROI calculator */}
				<section data-pitch-section="roi">
					<Card className="bg-card/80 backdrop-blur-xl">
						<CardHeader>
							<CardTitle>Máy tính ROI trực quan</CardTitle>
							<CardDescription>
								Vuốt để chọn quy mô đội sales — kết quả cập nhật theo thời gian thực.
							</CardDescription>
						</CardHeader>
						<CardContent>
							<PitchRoiCalculator defaults={meta.roi} />
						</CardContent>
					</Card>
				</section>

				{/* Inline booking CTA → Story 37.3 booking engine */}
				<section data-pitch-section="booking" className="text-center">
					<Button asChild size="lg" className="w-full sm:w-auto">
						<Link href={meta.booking_path}>
							<CalendarCheck className="mr-2 h-5 w-5" />
							Đặt lịch trao đổi với {meta.workspace_name}
						</Link>
					</Button>
				</section>

				<footer className="pt-10 border-t text-center space-y-2">
					<p className="text-xs text-muted-foreground flex items-center justify-center gap-1">
						<ShieldCheck className="h-3.5 w-3.5" />
						Bạn nhận được báo cáo này vì doanh nghiệp của bạn đang hoạt động công khai trong ngành.
						Dữ liệu cá nhân được bảo vệ theo Nghị định 13/2023/NĐ-CP.
					</p>
					<Link
						href={optOutPath}
						className="inline-block text-xs text-muted-foreground underline underline-offset-4 hover:text-foreground"
					>
						Yêu cầu xóa thông tin của tôi / Opt-out
					</Link>
				</footer>
			</div>
		</main>
	);
}
