export interface AuditEventRead {
	id: number;
	action: string;
	actor_id?: string | null;
	subject_id?: string | null;
	actor_email?: string | null;
	subject_email?: string | null;
	ticket_ref?: string | null;
	ip_address?: string | null;
	user_agent?: string | null;
	diff_payload?: Record<string, unknown> | null;
	created_at: string;
	endpoint?: string | null;
}

export interface AuditEventListResponse {
	items: AuditEventRead[];
	total: number;
	limit: number;
	offset: number;
}

export interface AuditLogFilterParams {
	action?: string;
	actor_id?: string;
	actor_email?: string;
	subject_id?: string;
	subject_email?: string;
	ticket_ref?: string;
	start_date?: string;
	end_date?: string;
	limit?: number;
	offset?: number;
}
