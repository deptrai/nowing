"use client";

import { makeAssistantToolUI } from "@assistant-ui/react";
import {
	AlertTriangleIcon,
	CheckIcon,
	InfoIcon,
	Loader2Icon,
	Trash2Icon,
	XIcon,
} from "lucide-react";
import { useState } from "react";
import { Button } from "@/components/ui/button";

interface GoogleDriveAccount {
	id: number;
	name: string;
}

interface GoogleDriveFile {
	file_id: string;
	name: string;
	mime_type: string;
	web_view_link: string;
}

interface InterruptResult {
	__interrupt__: true;
	__decided__?: "approve" | "reject";
	action_requests: Array<{
		name: string;
		args: Record<string, unknown>;
	}>;
	review_configs: Array<{
		action_name: string;
		allowed_decisions: Array<"approve" | "reject">;
	}>;
	context?: {
		account?: GoogleDriveAccount;
		file?: GoogleDriveFile;
		error?: string;
	};
}

interface SuccessResult {
	status: "success";
	file_id: string;
	message?: string;
}

interface ErrorResult {
	status: "error";
	message: string;
}

interface NotFoundResult {
	status: "not_found";
	message: string;
}

type TrashGoogleDriveFileResult =
	| InterruptResult
	| SuccessResult
	| ErrorResult
	| NotFoundResult;

function isInterruptResult(result: unknown): result is InterruptResult {
	return (
		typeof result === "object" &&
		result !== null &&
		"__interrupt__" in result &&
		(result as InterruptResult).__interrupt__ === true
	);
}

function isErrorResult(result: unknown): result is ErrorResult {
	return (
		typeof result === "object" &&
		result !== null &&
		"status" in result &&
		(result as ErrorResult).status === "error"
	);
}

function isNotFoundResult(result: unknown): result is NotFoundResult {
	return (
		typeof result === "object" &&
		result !== null &&
		"status" in result &&
		(result as NotFoundResult).status === "not_found"
	);
}

const MIME_TYPE_LABELS: Record<string, string> = {
	"application/vnd.google-apps.document": "Google Doc",
	"application/vnd.google-apps.spreadsheet": "Google Sheet",
	"application/vnd.google-apps.presentation": "Google Slides",
};

function ApprovalCard({
	interruptData,
	onDecision,
}: {
	interruptData: InterruptResult;
	onDecision: (decision: {
		type: "approve" | "reject";
		message?: string;
		edited_action?: { name: string; args: Record<string, unknown> };
	}) => void;
}) {
	const [decided, setDecided] = useState<"approve" | "reject" | null>(
		interruptData.__decided__ ?? null
	);

	const account = interruptData.context?.account;
	const file = interruptData.context?.file;
	const fileLabel = file?.mime_type
		? (MIME_TYPE_LABELS[file.mime_type] ?? "File")
		: "File";

	return (
		<div
			className={`my-4 max-w-full overflow-hidden rounded-xl transition-all duration-300 ${
				decided
					? "border border-border bg-card shadow-sm"
					: "border-2 border-foreground/20 bg-muted/30 dark:bg-muted/10 shadow-lg animate-pulse-subtle"
			}`}
		>
			{/* Header */}
			<div
				className={`flex items-center gap-3 border-b ${
					decided ? "border-border bg-card" : "border-foreground/15 bg-muted/40 dark:bg-muted/20"
				} px-4 py-3`}
			>
				<div
					className={`flex size-9 shrink-0 items-center justify-center rounded-lg ${
						decided ? "bg-muted" : "bg-muted animate-pulse"
					}`}
				>
					<AlertTriangleIcon
						className={`size-4 ${decided ? "text-muted-foreground" : "text-foreground"}`}
					/>
				</div>
				<div className="min-w-0 flex-1">
					<p className="text-sm font-medium text-foreground">Trash Google Drive File</p>
					<p className="truncate text-xs text-muted-foreground">
						Requires your approval to proceed
					</p>
				</div>
			</div>

			{/* Context — read-only file details */}
			{!decided && interruptData.context && (
				<div className="border-b border-border px-4 py-3 bg-muted/30 space-y-3">
					{interruptData.context.error ? (
						<p className="text-sm text-destructive">{interruptData.context.error}</p>
					) : (
						<>
							{account && (
								<div className="space-y-1.5">
									<div className="text-xs font-medium text-muted-foreground">
										Google Drive Account
									</div>
									<div className="w-full rounded-md border border-input bg-muted/50 px-3 py-2 text-sm">
										{account.name}
									</div>
								</div>
							)}

							{file && (
								<div className="space-y-1.5">
									<div className="text-xs font-medium text-muted-foreground">
										File to Trash
									</div>
									<div className="w-full rounded-md border border-input bg-muted/50 px-3 py-2 text-sm space-y-0.5">
										<div className="font-medium">{file.name}</div>
										<div className="text-xs text-muted-foreground">{fileLabel}</div>
										{file.web_view_link && (
											<a
												href={file.web_view_link}
												target="_blank"
												rel="noopener noreferrer"
												className="text-xs text-primary hover:underline"
											>
												Open in Drive
											</a>
										)}
									</div>
								</div>
							)}
						</>
					)}
				</div>
			)}

			{/* Trash warning */}
			{!decided && (
				<div className="px-4 py-3 border-b border-border bg-muted/20">
					<p className="text-xs text-muted-foreground">
						⚠️ The file will be moved to Google Drive trash. You can restore it from trash within 30 days.
					</p>
				</div>
			)}

			{/* Action buttons */}
			<div
				className={`flex items-center gap-2 border-t ${
					decided ? "border-border bg-card" : "border-foreground/15 bg-muted/20 dark:bg-muted/10"
				} px-4 py-3`}
			>
				{decided ? (
					<p className="flex items-center gap-1.5 text-sm text-muted-foreground">
						{decided === "approve" ? (
							<>
								<CheckIcon className="size-3.5 text-green-500" />
								Approved
							</>
						) : (
							<>
								<XIcon className="size-3.5 text-destructive" />
								Rejected
							</>
						)}
					</p>
				) : (
					<>
						<Button
							size="sm"
							variant="destructive"
							onClick={() => {
								setDecided("approve");
								onDecision({
									type: "approve",
									edited_action: {
										name: interruptData.action_requests[0].name,
										args: {
											file_id: file?.file_id,
											connector_id: account?.id,
										},
									},
								});
							}}
						>
							<Trash2Icon />
							Move to Trash
						</Button>
						<Button
							size="sm"
							variant="outline"
							onClick={() => {
								setDecided("reject");
								onDecision({ type: "reject", message: "User rejected the action." });
							}}
						>
							<XIcon />
							Reject
						</Button>
					</>
				)}
			</div>
		</div>
	);
}

function ErrorCard({ result }: { result: ErrorResult }) {
	return (
		<div className="my-4 max-w-md overflow-hidden rounded-xl border border-destructive/50 bg-card">
			<div className="flex items-center gap-3 border-b border-destructive/50 px-4 py-3">
				<div className="flex size-9 shrink-0 items-center justify-center rounded-lg bg-destructive/10">
					<XIcon className="size-4 text-destructive" />
				</div>
				<div className="min-w-0 flex-1">
					<p className="text-sm font-medium text-destructive">Failed to trash file</p>
				</div>
			</div>
			<div className="px-4 py-3">
				<p className="text-sm text-muted-foreground">{result.message}</p>
			</div>
		</div>
	);
}

function NotFoundCard({ result }: { result: NotFoundResult }) {
	return (
		<div className="my-4 max-w-md overflow-hidden rounded-xl border border-amber-500/50 bg-card">
			<div className="flex items-start gap-3 px-4 py-3">
				<div className="flex size-9 shrink-0 items-center justify-center rounded-lg bg-amber-500/10">
					<InfoIcon className="size-4 text-amber-500" />
				</div>
				<div className="min-w-0 flex-1 pt-2">
					<p className="text-sm text-muted-foreground">{result.message}</p>
				</div>
			</div>
		</div>
	);
}

function SuccessCard({ result }: { result: SuccessResult }) {
	return (
		<div className="my-4 max-w-md overflow-hidden rounded-xl border border-border bg-card">
			<div className="flex items-center gap-3 px-4 py-3">
				<div className="flex size-9 shrink-0 items-center justify-center rounded-lg bg-green-500/10">
					<CheckIcon className="size-4 text-green-500" />
				</div>
				<div className="min-w-0 flex-1">
					<p className="text-[.8rem] text-muted-foreground">
						{result.message || "File moved to trash successfully"}
					</p>
				</div>
			</div>
		</div>
	);
}

export const TrashGoogleDriveFileToolUI = makeAssistantToolUI<
	{ file_name: string },
	TrashGoogleDriveFileResult
>({
	toolName: "trash_google_drive_file",
	render: function TrashGoogleDriveFileUI({ result, status }) {
		if (status.type === "running") {
			return (
				<div className="my-4 flex max-w-md items-center gap-3 rounded-xl border border-border bg-card px-4 py-3">
					<Loader2Icon className="size-4 animate-spin text-muted-foreground" />
					<p className="text-sm text-muted-foreground">Looking up file in Google Drive...</p>
				</div>
			);
		}

		if (!result) return null;

		if (isInterruptResult(result)) {
			return (
				<ApprovalCard
					interruptData={result}
					onDecision={(decision) => {
						window.dispatchEvent(
							new CustomEvent("hitl-decision", { detail: { decisions: [decision] } })
						);
					}}
				/>
			);
		}

		if (
			typeof result === "object" &&
			result !== null &&
			"status" in result &&
			(result as { status: string }).status === "rejected"
		) {
			return null;
		}

		if (isNotFoundResult(result)) return <NotFoundCard result={result} />;
		if (isErrorResult(result)) return <ErrorCard result={result} />;

		return <SuccessCard result={result as SuccessResult} />;
	},
});
