import { boolean, json, number, string, table } from "@rocicorp/zero";

export const leadsTable = table("leads")
	.columns({
		id: string(),
		workspaceId: number().from("workspace_id"),
		clientId: string().optional().from("client_id"),
		source: string(),
		companyName: string().from("company_name"),
		domain: string().optional(),
		industry: string().optional(),
		companySize: string().optional().from("company_size"),
		location: string().optional(),
		techStack: json().optional().from("tech_stack"),
		fitScore: number().optional().from("fit_score"),
		intentScore: number().optional().from("intent_score"),
		compositeScore: number().optional().from("composite_score"),
		status: string(),
		enriched: boolean(),
		stageId: string().optional().from("stage_id"),
		assignedToUserId: string().optional().from("assigned_to_user_id"),
		version: number(),
		createdAt: number().from("created_at"),
		updatedAt: number().optional().from("updated_at"),
	})
	.primaryKey("id", "workspaceId");

export const leadPipelineStageTable = table("lead_pipeline_stages")
	.columns({
		id: string(),
		workspaceId: number().from("workspace_id"),
		clientId: string().optional().from("client_id"),
		name: string(),
		slug: string(),
		position: number(),
		color: string().optional(),
		isSystem: boolean().from("is_system"),
		createdAt: number().from("created_at"),
		updatedAt: number().optional().from("updated_at"),
	})
	.primaryKey("id", "workspaceId");
