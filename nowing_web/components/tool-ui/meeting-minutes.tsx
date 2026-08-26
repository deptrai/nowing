"use client";

import type { ToolCallMessagePartProps } from "@assistant-ui/react";
import {
	AlertCircleIcon,
	CheckSquareIcon,
	ChevronDownIcon,
	ChevronUpIcon,
	DownloadIcon,
	Loader2Icon,
	MicIcon,
	UsersIcon,
} from "lucide-react";
import { useParams } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import { TextShimmerLoader } from "@/components/prompt-kit/loader";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
	downloadUrl,
	fetchMeetingMinutes,
	type MeetingMinutesRecord,
} from "@/lib/apis/meeting-minutes-api.service";
import { getWorkspaceIdNumber } from "@/lib/route-params";
import { cn } from "@/lib/utils";

export const MeetingMinutesBuildArgsSchema = {
	audio_url: "",
	document_id: 0,
	language: "",
};

export const MeetingMinutesBuildResultSchema = {
	status: "",
	meeting_minutes_id: 0,
	title: "",
	summary: "",
	transcript: [],
	action_items: [],
	download_url: "",
	error: "",
};

export type MeetingMinutesBuildArgs = {
	audio_url?: string | null;
	document_id?: number | null;
	language?: string | null;
};

export type MeetingMinutesBuildResult = {
	status?: string;
	meeting_minutes_id?: number;
	title?: string | null;
	summary?: string | null;
	transcript?: { speaker: string; text: string; start: number; end: number }[] | null;
	action_items?: { speaker: string; task: string; due: string | null }[] | null;
	download_url?: string | null;
	error?: string | null;
};

function parseToolResult(raw: unknown): Partial<MeetingMinutesBuildResult> {
	if (typeof raw === "object" && raw !== null) {
		return raw as Partial<MeetingMinutesBuildResult>;
	}
	if (typeof raw === "string") {
		try {
			const parsed = JSON.parse(raw);
			if (typeof parsed === "object" && parsed !== null) {
				return parsed as Partial<MeetingMinutesBuildResult>;
			}
		} catch {
			return { error: raw, status: "error" };
		}
	}
	return {};
}

function isTerminalStatus(status: string | undefined): boolean {
	return (
		status === "ready" ||
		status === "failed" ||
		status === "degraded" ||
		status === "validation_failed"
	);
}

export function MeetingMinutesToolUI({
	args,
	result: rawResult,
	status: toolStatus,
}: ToolCallMessagePartProps<MeetingMinutesBuildArgs, MeetingMinutesBuildResult | string>) {
	const params = useParams();
	const workspaceId = getWorkspaceIdNumber(params) || 0;
	const result = useMemo(() => parseToolResult(rawResult), [rawResult]);
	const [record, setRecord] = useState<MeetingMinutesRecord | null>(null);
	const [expanded, setExpanded] = useState(false);
	const [showRaw, setShowRaw] = useState(false);

	const meetingMinutesId = result.meeting_minutes_id;
	const isRunning =
		toolStatus.type === "running" ||
		toolStatus.type === "requires-action" ||
		(!isTerminalStatus(result.status) && !record);

	useEffect(() => {
		if (!meetingMinutesId) return;
		let cancelled = false;
		let interval: ReturnType<typeof setInterval> | null = null;

		const load = async () => {
			try {
				const data = await fetchMeetingMinutes(meetingMinutesId, workspaceId);
				if (cancelled) return;
				setRecord(data);
				if (isTerminalStatus(data.status)) {
					if (interval) clearInterval(interval);
				}
			} catch {
				if (cancelled) return;
				// Stop polling on error; the card shows the last known result.
				if (interval) clearInterval(interval);
			}
		};

		void load();
		interval = setInterval(load, 2000);
		return () => {
			cancelled = true;
			if (interval) clearInterval(interval);
		};
	}, [meetingMinutesId, workspaceId]);

	const title = record?.title || result.title || args.audio_url || "Meeting Minutes";
	const status = record?.status || result.status;
	const summary = record?.summary || result.summary || "";
	const actionItems = record?.action_items || result.action_items || [];
	const transcript = record?.transcript || result.transcript || [];
	const rawTranscript = record?.raw_transcript || "";
	const error = record?.error || result.error;

	const failed =
		status === "failed" ||
		status === "validation_failed" ||
		status === "error" ||
		(error && status !== "degraded");
	const degraded = status === "degraded";
	const ready = status === "ready" || degraded;

	if (isRunning || (!ready && !failed)) {
		return (
			<div className="my-4 max-w-xl overflow-hidden rounded-2xl border border-border/80 bg-card p-5 shadow-sm select-none">
				<div className="flex items-center gap-3">
					<div className="flex size-9 shrink-0 items-center justify-center rounded-xl bg-emerald-500/10 text-emerald-600 dark:text-emerald-400">
						<MicIcon className="size-4.5" aria-hidden="true" />
					</div>
					<div className="min-w-0">
						<h4 className="truncate text-sm font-semibold text-foreground">{title}</h4>
						<TextShimmerLoader text="Transcribing and extracting minutes…" size="sm" />
					</div>
					<Badge variant="secondary" className="ml-auto gap-1 px-2 py-0.5 text-xs">
						<Loader2Icon className="size-3 animate-spin text-muted-foreground" aria-hidden="true" />
						Processing
					</Badge>
				</div>
				{args.audio_url && (
					<p className="mt-3 truncate text-xs text-muted-foreground italic">
						URL: {args.audio_url}
					</p>
				)}
			</div>
		);
	}

	if (failed) {
		return (
			<div className="my-4 max-w-xl overflow-hidden rounded-2xl border border-destructive/20 bg-destructive/5 p-5 shadow-sm">
				<div className="flex items-center gap-3">
					<div className="flex size-9 shrink-0 items-center justify-center rounded-xl bg-destructive/10 text-destructive">
						<AlertCircleIcon className="size-5" aria-hidden="true" />
					</div>
					<div className="min-w-0 flex-1">
						<h4 className="truncate text-sm font-semibold text-destructive">
							Meeting Minutes Failed
						</h4>
						<p className="mt-0.5 text-xs text-muted-foreground line-clamp-2">
							{error || "Unable to generate meeting minutes."}
						</p>
					</div>
				</div>
			</div>
		);
	}

	const groupedTranscript = transcript.reduce<Record<string, typeof transcript>>((acc, seg) => {
		acc[seg.speaker] = acc[seg.speaker] || [];
		acc[seg.speaker].push(seg);
		return acc;
	}, {});

	const displayDownloadUrl = record?.id
		? downloadUrl(record.id, workspaceId)
		: result.download_url || "";

	return (
		<div className="my-4 max-w-2xl overflow-hidden rounded-2xl border border-border/80 bg-card p-5 shadow-sm transition-all hover:border-border">
			<div className="flex items-start justify-between gap-3">
				<div className="flex items-center gap-3 min-w-0">
					<div className="flex size-10 shrink-0 items-center justify-center rounded-xl bg-emerald-500/10 text-emerald-600 dark:text-emerald-400">
						<UsersIcon className="size-5" aria-hidden="true" />
					</div>
					<div className="min-w-0">
						<h4 className="truncate text-sm font-bold text-foreground">{title}</h4>
						<p className="truncate text-xs text-muted-foreground">Meeting minutes</p>
					</div>
				</div>
				<Badge
					variant="outline"
					className={cn(
						"shrink-0 font-medium text-xs capitalize",
						degraded
							? "border-amber-500/30 bg-amber-500/10 text-amber-700 dark:text-amber-300"
							: "border-emerald-500/30 bg-emerald-500/10 text-emerald-700 dark:text-emerald-300"
					)}
				>
					{degraded ? "Degraded" : "Ready"}
				</Badge>
			</div>

			{degraded && (
				<p className="mt-3 text-xs text-amber-700 dark:text-amber-300">
					Transcript ready, but speaker labels are unavailable.
				</p>
			)}

			{summary && (
				<div className="mt-4 space-y-1">
					<h5 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
						Summary
					</h5>
					<p className="text-sm text-foreground whitespace-pre-wrap">{summary}</p>
				</div>
			)}

			{actionItems.length > 0 && (
				<div className="mt-4 space-y-2">
					<h5 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
						Action Items
					</h5>
					<ul className="space-y-1.5">
						{actionItems.map((item) => (
							<li
								key={`action-${item.speaker}-${item.task}-${item.due ?? ""}`}
								className="flex items-start gap-2 text-sm"
							>
								<CheckSquareIcon className="size-4 shrink-0 text-emerald-600" aria-hidden="true" />
								<span className="text-foreground">
									<span className="font-medium">{item.speaker}:</span> {item.task}
									{item.due && <span className="text-muted-foreground"> · {item.due}</span>}
								</span>
							</li>
						))}
					</ul>
				</div>
			)}

			<div className="mt-4 flex flex-wrap items-center gap-2 pt-3 border-t border-border/60">
				{displayDownloadUrl && (
					<Button
						type="button"
						variant="outline"
						size="sm"
						asChild
						className="gap-1.5 text-xs font-semibold rounded-xl"
					>
						<a href={displayDownloadUrl} download rel="noopener noreferrer">
							<DownloadIcon className="size-3.5" aria-hidden="true" />
							Download
						</a>
					</Button>
				)}

				{transcript.length > 0 && (
					<Button
						type="button"
						variant="ghost"
						size="sm"
						onClick={() => setExpanded((v) => !v)}
						className="gap-1 text-xs"
					>
						{expanded ? (
							<ChevronUpIcon className="size-3.5" />
						) : (
							<ChevronDownIcon className="size-3.5" />
						)}
						Transcript
					</Button>
				)}

				{rawTranscript && (
					<Button
						type="button"
						variant="ghost"
						size="sm"
						onClick={() => setShowRaw((v) => !v)}
						className="gap-1 text-xs"
					>
						{showRaw ? (
							<ChevronUpIcon className="size-3.5" />
						) : (
							<ChevronDownIcon className="size-3.5" />
						)}
						Raw transcript
					</Button>
				)}
			</div>

			{expanded && transcript.length > 0 && (
				<div className="mt-3 space-y-3 rounded-xl bg-muted/40 p-3">
					{Object.entries(groupedTranscript).map(([speaker, segs]) => (
						<div key={speaker}>
							<h6 className="text-xs font-semibold text-emerald-700 dark:text-emerald-300">
								{speaker}
							</h6>
							{segs.map((seg) => (
								<p
									key={`${seg.speaker}-${seg.start}-${seg.end}-${seg.text.slice(0, 20)}`}
									className="text-sm text-foreground"
								>
									{seg.text}
								</p>
							))}
						</div>
					))}
				</div>
			)}

			{showRaw && rawTranscript && (
				<div className="mt-3 rounded-xl bg-muted/40 p-3">
					<p className="text-sm text-foreground whitespace-pre-wrap">{rawTranscript}</p>
				</div>
			)}
		</div>
	);
}
