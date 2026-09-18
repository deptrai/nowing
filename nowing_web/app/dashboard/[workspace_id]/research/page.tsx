import type { Metadata } from "next";
import { getTranslations } from "next-intl/server";
import { redirect } from "next/navigation";

export async function generateMetadata(): Promise<Metadata> {
	const t = await getTranslations("saved_searches");
	return {
		title: t("research_title"),
	};
}

export default async function ResearchPage({
	params,
}: {
	params: Promise<{ workspace_id: string }>;
}) {
	const { workspace_id } = await params;
	redirect(`/dashboard/${workspace_id}/research/saved-searches/default`);
}
