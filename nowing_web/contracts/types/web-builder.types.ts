export type WebAppStatus =
	| "generated"
	| "validation_failed"
	| "building"
	| "preview_ready"
	| "build_failed"
	| "published"
	| "deploy_failed"
	| "error";

export interface BuildLogsOutput {
	app_id: string;
	workspace_id: number;
	logs: string;
	lines: number;
	status: string;
}

export interface WorkspaceApp {
	id: string;
	workspace_id: number;
	user_id?: string;
	name: string;
	slug: string;
	description?: string;
	prompt?: string;
	language: string;
	status: WebAppStatus;
	preview_url?: string;
	public_url?: string;
	custom_domain?: string;
	custom_domain_status?: "active" | "pending_verification" | "failed";
	error_message?: string;
	created_at: string;
	updated_at: string;
}

export interface WebAppBuildInput {
	prompt: string;
	workspace_id: number;
	language?: string;
	app_name?: string;
}

export interface WebAppBuildOutput {
	app_id: string;
	workspace_id: number;
	name: string;
	slug: string;
	status: WebAppStatus;
	preview_url?: string;
	public_url?: string;
	message?: string;
	error_message?: string;
	files: string[];
}

export interface WebAppDeployInput {
	workspace_id: number;
	slug?: string;
}

export interface WebAppDeployOutput {
	app_id: string;
	workspace_id: number;
	status: "published" | "deploy_failed" | "error";
	public_url?: string;
	slug: string;
	message?: string;
}

export interface CustomDomainInput {
	workspace_id: number;
	custom_domain: string;
}

export interface CustomDomainOutput {
	app_id: string;
	workspace_id: number;
	custom_domain: string;
	status: "active" | "pending_verification" | "failed";
	cname_target: string;
	message?: string;
}

export interface MarkToolRect {
	x: number;
	y: number;
	width: number;
	height: number;
}

export interface MarkToolInput {
	workspace_id: number;
	selector: string;
	patch: {
		type: "text" | "className" | "style" | "attribute" | "replace";
		value: string;
		attribute?: string;
	};
	file_path?: string;
	rect?: MarkToolRect;
	component_hint?: string;
}

export interface MarkToolOutput {
	app_id: string;
	workspace_id: number;
	status: "patched" | "mark_unresolvable" | "error";
	file_path: string;
	patched_code?: string;
	message?: string;
}

export type WebBuilderStreamEvent =
	| { type: "phase"; phase: string; message: string }
	| { type: "token"; token: string }
	| { type: "file_written"; path: string; size?: number }
	| {
			type: "complete";
			app: {
				id: string;
				workspace_id: number;
				name: string;
				slug: string;
				status: WebAppStatus;
				preview_url?: string;
				public_url?: string;
				files: string[];
				message?: string;
			};
	  };
