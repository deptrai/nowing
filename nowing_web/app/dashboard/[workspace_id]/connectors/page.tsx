import type { Metadata } from "next";
import { getTranslations } from "next-intl/server";
import { ConnectorsPage } from "@/components/connectors/connectors-page";

export async function generateMetadata(): Promise<Metadata> {
	const t = await getTranslations("connectors");
	return {
		title: t("title"),
	};
}

interface ConnectorsPageParams {
	params: Promise<{ workspace_id: string }>;
}

export default async function ConnectorsRoute({ params }: ConnectorsPageParams) {
	const { workspace_id } = await params;
	return <ConnectorsPage workspaceId={workspace_id} />;
}
