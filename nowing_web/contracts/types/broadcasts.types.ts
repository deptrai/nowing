export type BannerType = "info" | "warning" | "maintenance" | "promo";
export type BroadcastStatus = "active" | "scheduled" | "expired" | "inactive";

export interface BroadcastRead {
	id: string;
	title: string;
	message: string;
	banner_type: BannerType;
	target_all: boolean;
	target_workspace_ids: number[];
	starts_at: string;
	expires_at?: string | null;
	dismissible: boolean;
	is_active: boolean;
	status: BroadcastStatus;
	created_by_user_id?: string | null;
	updated_by_user_id?: string | null;
	created_at: string;
	updated_at: string;
}

export interface BroadcastListResponse {
	items: BroadcastRead[];
	total: number;
}

export interface BroadcastActiveRead {
	id: string;
	title: string;
	message: string;
	banner_type: BannerType;
	dismissible: boolean;
}

export interface BroadcastCreate {
	title: string;
	message: string;
	banner_type: BannerType;
	target_all: boolean;
	target_workspace_ids?: number[];
	starts_at?: string;
	expires_at?: string | null;
	dismissible?: boolean;
	is_active?: boolean;
}

export interface BroadcastUpdate {
	title?: string;
	message?: string;
	banner_type?: BannerType;
	target_all?: boolean;
	target_workspace_ids?: number[];
	starts_at?: string;
	expires_at?: string | null;
	dismissible?: boolean;
	is_active?: boolean;
}
