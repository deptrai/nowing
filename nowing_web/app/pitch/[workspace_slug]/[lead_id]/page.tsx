import { CalendarCheck, ShieldCheck, TrendingUp } from "lucide-react";
import type { Metadata } from "next";
import { headers } from "next/headers";
import Link from "next/link";
import { notFound } from "next/navigation";
import { PitchEngagementBeacon } from "@/components/pitch/engagement-beacon";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { SERVER_BACKEND_URL } from "@/lib/env-config";

// Story 37.6: public mini-pitch portal shell served at
// pitch.nowing.ai/[workspace_slug]/[lead_id] (host rewrite in next.config).
// The full generated portal (branding, ROI calculator) lands in Story 37.5;
// this page provides the SSR route + the engagement beacon mount point.
// All dynamic prospect fields render as text nodes — React escapes them, so
// no Stored XSS surface (AD-119/AC-3 of 37.5 carries over).

interface PitchMeta {
	lead_id: string;
	workspace_id: number;
	company_name: string;
	industry: string | null;
	location: string | null;
	workspace_name: string;
	booking_path: string;
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

	return (
		<main className="min-h-screen bg-gradient-to-br from-background via-background to-primary/5">
			<PitchEngagementBeacon workspaceRef={workspaceSlug} leadId={leadId} />

			<div className="mx-auto max-w-3xl px-4 py-16 space-y-10">
				<section data-pitch-section="hero" className="text-center space-y-3">
					<p className="text-sm font-medium text-muted-foreground uppercase tracking-wide">
						{meta.workspace_name}
					</p>
					<h1 className="text-4xl font-bold tracking-tight">Dành riêng cho {meta.company_name}</h1>
					<p className="text-lg text-muted-foreground">
						{[meta.industry, meta.location].filter(Boolean).join(" · ") ||
							"Bản tóm tắt giá trị trong 30 giây"}
					</p>
				</section>

				<section data-pitch-section="exec-summary">
					<Card className="bg-card/80 backdrop-blur-xl">
						<CardHeader>
							<CardTitle className="flex items-center gap-2">
								<TrendingUp className="h-5 w-5 text-primary" />
								Tóm tắt dành cho ban lãnh đạo
							</CardTitle>
							<CardDescription>
								{meta.company_name} có thể tăng tốc outbound B2B với Nowing — lead enrichment,
								sequencing và cảnh báo realtime trong một workstation duy nhất.
							</CardDescription>
						</CardHeader>
					</Card>
				</section>

				<section data-pitch-section="roi">
					<Card className="bg-card/80 backdrop-blur-xl">
						<CardHeader>
							<CardTitle>ROI ước tính</CardTitle>
							<CardDescription>
								Mỗi lead mở portal và đọc qua phần này sẽ được ghi nhận realtime cho đội sales.
							</CardDescription>
						</CardHeader>
						<CardContent>
							<p className="text-sm text-muted-foreground">
								Tiết kiệm ~70% thời gian prospecting so với quy trình thủ công.
							</p>
						</CardContent>
					</Card>
				</section>

				<section data-pitch-section="booking" className="text-center">
					<Button asChild size="lg">
						<Link href={meta.booking_path}>
							<CalendarCheck className="mr-2 h-5 w-5" />
							Đặt lịch 30 phút với {meta.workspace_name}
						</Link>
					</Button>
				</section>

				<footer className="pt-10 border-t text-center space-y-2">
					<p className="text-xs text-muted-foreground flex items-center justify-center gap-1">
						<ShieldCheck className="h-3.5 w-3.5" />
						Dữ liệu cá nhân được bảo vệ theo Nghị định 13/2023/NĐ-CP.
					</p>
					<Link
						href="/privacy"
						className="text-xs text-muted-foreground underline underline-offset-4 hover:text-foreground"
					>
						Yêu cầu xóa thông tin của tôi / Opt-out
					</Link>
				</footer>
			</div>
		</main>
	);
}
