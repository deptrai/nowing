import { LeadKanbanBoard } from "@/components/leads/pipeline/LeadKanbanBoard";

export default async function LeadPipelinePage(props: {
	params: Promise<{ workspace_id: string }>;
}) {
	const { workspace_id } = await props.params;

	return (
		<div className="flex-1 flex flex-col p-6 space-y-4 max-w-full overflow-hidden">
			<div className="flex items-center justify-between">
				<div>
					<h1 className="text-xl font-bold text-foreground">
						Quy Trình Bán Hàng & Phân Bổ Lead (Kanban)
					</h1>
					<p className="text-xs text-muted-foreground">
						Quản lý phễu khách hàng tiềm năng, kéo thả chuyển trạng thái và phân bổ tự động cho đội
						ngũ.
					</p>
				</div>
			</div>

			<div className="flex-1 min-h-0">
				<LeadKanbanBoard workspaceId={workspace_id} />
			</div>
		</div>
	);
}
