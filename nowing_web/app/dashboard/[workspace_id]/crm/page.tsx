"use client";

import { Activity, Kanban } from "lucide-react";
import { useTranslations } from "next-intl";
import { use, useState } from "react";
import { WorkspaceActivityTimeline } from "@/components/crm/WorkspaceActivityTimeline";
import { LeadKanbanBoard } from "@/components/leads/pipeline/LeadKanbanBoard";

export default function WorkspaceCrmPage({
	params,
}: {
	params: Promise<{ workspace_id: string }>;
}) {
	const { workspace_id } = use(params);
	const [activeTab, setActiveTab] = useState<"pipeline" | "timeline">("pipeline");
	const t = useTranslations("crm");

	return (
		<div className="flex-1 flex flex-col p-6 space-y-6 max-w-full overflow-hidden">
			<div className="flex flex-col gap-1 sm:flex-row sm:items-center sm:justify-between">
				<div>
					<h1 className="text-xl font-bold text-foreground">{t("title")}</h1>
					<p className="text-xs text-muted-foreground">
						{t("subtitle")}
					</p>
				</div>

				<div className="flex items-center gap-1 bg-muted p-1 rounded-lg self-start sm:self-auto">
					<button
						type="button"
						onClick={() => setActiveTab("pipeline")}
						className={`flex items-center gap-2 px-3 py-1.5 rounded-md text-xs font-medium transition-colors ${
							activeTab === "pipeline"
								? "bg-background text-foreground shadow-sm"
								: "text-muted-foreground hover:text-foreground"
						}`}
					>
						<Kanban className="w-3.5 h-3.5" />
						{t("tab_pipeline")}
					</button>
					<button
						type="button"
						onClick={() => setActiveTab("timeline")}
						className={`flex items-center gap-2 px-3 py-1.5 rounded-md text-xs font-medium transition-colors ${
							activeTab === "timeline"
								? "bg-background text-foreground shadow-sm"
								: "text-muted-foreground hover:text-foreground"
						}`}
					>
						<Activity className="w-3.5 h-3.5" />
						{t("tab_timeline")}
					</button>
				</div>
			</div>

			<div className="flex-1 min-h-0">
				{activeTab === "pipeline" ? (
					<LeadKanbanBoard workspaceId={workspace_id} />
				) : (
					<WorkspaceActivityTimeline workspaceId={workspace_id} />
				)}
			</div>
		</div>
	);
}
