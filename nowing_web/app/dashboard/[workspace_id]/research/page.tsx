import type { Metadata } from "next";
import { redirect } from "next/navigation";

export const metadata: Metadata = {
	title: "Research",
};

export default async function ResearchPage({
	params,
}: {
	params: Promise<{ workspace_id: string }>;
}) {
	const { workspace_id } = await params;
	redirect(`/dashboard/${workspace_id}/research/saved-searches/default`);
}
