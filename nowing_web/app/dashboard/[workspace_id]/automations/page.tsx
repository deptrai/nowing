import { useTranslations } from "next-intl";
import type { Metadata } from "next";
import { getTranslations } from "next-intl/server";
import { AutomationsContent } from "./automations-content";

export async function generateMetadata(): Promise<Metadata> {
	const t = await getTranslations("automations");
	return {
		title: t("page_title"),
	};
}

export default async function AutomationsPage({
	params,
}: {
	params: Promise<{ workspace_id: string }>;
}) {
	const { workspace_id } = await params;

	return (
		<div className="mx-auto w-full max-w-5xl space-y-6">
			<AutomationsContent workspaceId={Number(workspace_id)} />
		</div>
	);
}
