import type { Metadata } from "next";
import { SavedSearchesListContent } from "./saved-searches-list-content";

export const metadata: Metadata = {
	title: "Saved Searches & Alerts",
};

export default async function SavedSearchesPage({
	params,
}: {
	params: Promise<{ workspace_id: string }>;
}) {
	const { workspace_id } = await params;

	return <SavedSearchesListContent workspaceId={Number(workspace_id)} />;
}
