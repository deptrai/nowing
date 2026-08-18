import { number, string, table } from "@rocicorp/zero";

export const dshMissionsTable = table("dsh_missions")
	.columns({
		id: string(),
		workspaceId: number().from("workspace_id"),
		missionType: string().from("mission_type"),
		status: string(),
		phase: string(),
		progressPercent: number().from("progress_percent"),
		currentSubtaskId: string().optional().from("current_subtask_id"),
		createdAt: number().from("created_at"),
		updatedAt: number().optional().from("updated_at"),
	})
	.primaryKey("id", "workspaceId");
