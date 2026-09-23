import type { Metadata } from "next";
import { getTranslations } from "next-intl/server";
import { SavedSearchesListContent } from "./saved-searches-list-content";

export async function generateMetadata(): Promise<Metadata> {
	const t = await getTranslations("saved_searches");
	return {
		title: t("page_title"),
	};
}

export default async function SavedSearchesPage({
	params,
}: {
	params: Promise<{ workspace_id: string }>;
}) {
	const { workspace_id } = await params;

	return <SavedSearchesListContent workspaceId={Number(workspace_id)} />;
}
