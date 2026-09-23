import type { Metadata } from "next";
import { headers } from "next/headers";
import Link from "next/link";
import { PitchOptOutForm } from "@/components/pitch/opt-out-form";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { SERVER_BACKEND_URL } from "@/lib/env-config";

// Story 37.5 / AC-4: prospect-facing opt-out page linked from the portal
// footer.  Works on both hosts: on pitch.nowing.ai the /pitch/... path is a
// real app route (the host rewrite only covers the 2-segment portal path).

export const metadata: Metadata = {
	title: "Opt-out — Xóa thông tin",
	robots: { index: false, follow: false },
};

async function getCompanyName(
	workspaceSlug: string,
	leadId: string,
	clientIp: string | null
): Promise<string | null> {
	const forwardHeaders: Record<string, string> = {};
	if (clientIp) {
		forwardHeaders["x-real-ip"] = clientIp;
		forwardHeaders["x-forwarded-for"] = clientIp;
	}
	const url = `${SERVER_BACKEND_URL}/api/v1/public/pitch/${encodeURIComponent(workspaceSlug)}/${encodeURIComponent(leadId)}/meta`;
	const res = await fetch(url, { cache: "no-store", headers: forwardHeaders }).catch(() => null);
	if (!res || !res.ok) return null; // opt-out still works without the name
	const meta = (await res.json().catch(() => null)) as { company_name?: string } | null;
	return meta?.company_name ?? null;
}

export default async function PitchOptOutPage({
	params,
}: {
	params: Promise<{ workspace_slug: string; lead_id: string }>;
}) {
	const { workspace_slug: workspaceSlug, lead_id: leadId } = await params;
	const requestHeaders = await headers();
	const clientIp =
		requestHeaders.get("x-forwarded-for")?.split(",")[0]?.trim() || requestHeaders.get("x-real-ip");
	const companyName = await getCompanyName(workspaceSlug, leadId, clientIp);

	return (
		<main className="min-h-screen bg-gradient-to-br from-background via-background to-primary/5 flex items-center justify-center px-4">
			<Card className="w-full max-w-md bg-card/80 backdrop-blur-xl">
				<CardHeader>
					<CardTitle>Yêu cầu xóa thông tin</CardTitle>
					<CardDescription>Quyền xóa dữ liệu cá nhân theo Nghị định 13/2023/NĐ-CP.</CardDescription>
				</CardHeader>
				<CardContent className="space-y-6">
					<PitchOptOutForm workspaceRef={workspaceSlug} leadId={leadId} companyName={companyName} />
					<p className="text-center">
						<Link
							href={`/pitch/${workspaceSlug}/${leadId}`}
							className="text-xs text-muted-foreground underline underline-offset-4 hover:text-foreground"
						>
							← Quay lại báo cáo
						</Link>
					</p>
				</CardContent>
			</Card>
		</main>
	);
}
