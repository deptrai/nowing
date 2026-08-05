import type { Metadata } from "next";
import { ConnectorsPage } from "@/components/connectors/connectors-page";

export const metadata: Metadata = {
	title: "Integrations",
};

interface ConnectorsPageParams {
	params: Promise<{ workspace_id: string }>;
}

export default async function ConnectorsRoute({ params }: ConnectorsPageParams) {
	const { workspace_id } = await params;
	return <ConnectorsPage workspaceId={workspace_id} />;
}
