import { getTranslations } from "next-intl/server";
import { LeadKanbanBoard } from "@/components/leads/pipeline/LeadKanbanBoard";

export const dynamic = "force-dynamic";

export default async function LeadPipelinePage(props: {
	params: Promise<{ workspace_id: string }>;
}) {
	const t = await getTranslations("leads");
	const { workspace_id } = await props.params;

	return (
		<div className="flex-1 flex flex-col p-6 space-y-4 max-w-full overflow-hidden">
			<div className="flex items-center justify-between">
				<div>
					<h1 className="text-xl font-bold text-foreground">{t("pipeline_title")}</h1>
					<p className="text-xs text-muted-foreground">{t("pipeline_desc")}</p>
				</div>
			</div>

			<div className="flex-1 min-h-0">
				<LeadKanbanBoard workspaceId={workspace_id} />
			</div>
		</div>
	);
}
