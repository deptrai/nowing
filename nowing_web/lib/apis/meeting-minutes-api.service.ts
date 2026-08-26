const API_PREFIX = "/api/v1/meeting-minutes";

export interface MeetingMinutesSegment {
	speaker: string;
	text: string;
	start: number;
	end: number;
}

export interface MeetingMinutesActionItem {
	speaker: string;
	task: string;
	due: string | null;
}

export interface MeetingMinutesRecord {
	id: number;
	workspace_id: number;
	status: "pending" | "processing" | "ready" | "failed" | "degraded" | "validation_failed";
	title: string | null;
	summary: string | null;
	transcript: MeetingMinutesSegment[] | null;
	action_items: MeetingMinutesActionItem[] | null;
	raw_transcript: string | null;
	error: string | null;
	download_url: string | null;
	created_at: string;
	updated_at: string;
}

function getWorkspaceId(): number {
	// Best-effort; the real workspace id is passed in params elsewhere.
	if (typeof window === "undefined") return 0;
	const match = window.location.pathname.match(/\/dashboard\/([^/]+)/);
	if (!match) return 0;
	const id = Number(match[1]);
	return Number.isFinite(id) ? id : 0;
}

export async function fetchMeetingMinutes(
	meetingMinutesId: number,
	workspaceId?: number
): Promise<MeetingMinutesRecord> {
	const ws = workspaceId ?? getWorkspaceId();
	const res = await fetch(`${API_PREFIX}/${meetingMinutesId}?workspace_id=${ws}`, {
		credentials: "include",
	});
	if (!res.ok) {
		throw new Error(`Failed to fetch meeting minutes: ${res.status}`);
	}
	return res.json() as Promise<MeetingMinutesRecord>;
}

export function downloadUrl(meetingMinutesId: number, workspaceId?: number): string {
	const ws = workspaceId ?? getWorkspaceId();
	return `${API_PREFIX}/${meetingMinutesId}/download?workspace_id=${ws}`;
}
