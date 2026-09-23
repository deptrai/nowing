"use client";

import type { ToolCallMessagePartProps } from "@assistant-ui/react";
import { CornerDownLeftIcon } from "lucide-react";
import { useTranslations } from "next-intl";
import { useCallback, useEffect, useState } from "react";
import { TextShimmerLoader } from "@/components/prompt-kit/loader";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import type { HitlDecision, InterruptResult } from "@/features/chat-messages/hitl";
import { isInterruptResult, useHitlDecision, useHitlPhase } from "@/features/chat-messages/hitl";

interface JiraAccount {
	id: number;
	name: string;
	base_url: string;
	auth_expired?: boolean;
}

interface JiraIssue {
	issue_id: string;
	issue_identifier: string;
	issue_title: string;
	state?: string;
	document_id?: number;
}

type DeleteJiraIssueInterruptContext = {
	account?: JiraAccount;
	issue?: JiraIssue;
	error?: string;
};

interface SuccessResult {
	status: "success";
	deleted_from_kb?: boolean;
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

interface WarningResult {
	status: "success";
	warning: string;
	message?: string;
}

interface AuthErrorResult {
	status: "auth_error";
	message: string;
	connector_id?: number;
	connector_type: string;
}

interface InsufficientPermissionsResult {
	status: "insufficient_permissions";
	connector_id: number;
	message: string;
}

type DeleteJiraIssueResult =
	| InterruptResult<DeleteJiraIssueInterruptContext>
	| SuccessResult
	| ErrorResult
	| NotFoundResult
	| WarningResult
	| AuthErrorResult
	| InsufficientPermissionsResult;

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

function isWarningResult(result: unknown): result is WarningResult {
	return (
		typeof result === "object" &&
		result !== null &&
		"status" in result &&
		(result as WarningResult).status === "success" &&
		"warning" in result &&
		typeof (result as WarningResult).warning === "string"
	);
}

function isAuthErrorResult(result: unknown): result is AuthErrorResult {
	return (
		typeof result === "object" &&
		result !== null &&
		"status" in result &&
		(result as AuthErrorResult).status === "auth_error"
	);
}

function isInsufficientPermissionsResult(result: unknown): result is InsufficientPermissionsResult {
	return (
		typeof result === "object" &&
		result !== null &&
		"status" in result &&
		(result as InsufficientPermissionsResult).status === "insufficient_permissions"
	);
}

function ApprovalCard({
	interruptData,
	onDecision,
}: {
	interruptData: InterruptResult<DeleteJiraIssueInterruptContext>;
	onDecision: (decision: HitlDecision) => void;
}) {
	const t = useTranslations("toolUi");
	const { phase, setProcessing, setRejected } = useHitlPhase(interruptData);
	const [deleteFromKb, setDeleteFromKb] = useState(false);

	const context = interruptData.context;
	const account = context?.account;
	const issue = context?.issue;

	const handleApprove = useCallback(() => {
		if (phase !== "pending") return;
		setProcessing();
		onDecision({
			type: "approve",
			edited_action: {
				name: interruptData.action_requests[0].name,
				args: {
					issue_id: issue?.issue_id,
					connector_id: account?.id,
					delete_from_kb: deleteFromKb,
				},
			},
		});
	}, [phase, setProcessing, onDecision, interruptData, issue?.issue_id, account?.id, deleteFromKb]);

	useEffect(() => {
		const handler = (e: KeyboardEvent) => {
			if (e.key === "Enter" && !e.shiftKey && !e.ctrlKey && !e.metaKey) {
				handleApprove();
			}
		};
		window.addEventListener("keydown", handler);
		return () => window.removeEventListener("keydown", handler);
	}, [handleApprove]);

	return (
		<div className="my-4 max-w-lg overflow-hidden rounded-2xl border bg-muted/30 transition-[box-shadow] duration-300">
			{/* Header */}
			<div className="flex items-start justify-between px-5 pt-5 pb-4 select-none">
				<div>
					<p className="text-sm font-semibold text-foreground">
						{phase === "rejected"
							? t("jira_delete_rejected")
							: phase === "processing" || phase === "complete"
								? t("jira_delete_approved")
								: t("jira_delete_title")}
					</p>
					{phase === "processing" ? (
						<TextShimmerLoader text={t("jira_deleting_issue")} size="sm" />
					) : phase === "complete" ? (
						<p className="text-xs text-muted-foreground mt-0.5">{t("jira_issue_deleted")}</p>
					) : phase === "rejected" ? (
						<p className="text-xs text-muted-foreground mt-0.5">{t("jira_delete_cancelled")}</p>
					) : (
						<p className="text-xs text-muted-foreground mt-0.5">{t("common_requires_approval")}</p>
					)}
				</div>
			</div>

			{/* Context section — account + issue info */}
			{phase !== "rejected" && context && (
				<>
					<div className="mx-5 h-px bg-border/50" />
					<div className="px-5 py-4 space-y-4 select-none">
						{context.error ? (
							<p className="text-sm text-destructive">{context.error}</p>
						) : (
							<>
								{account && (
									<div className="space-y-2">
										<p className="text-xs font-medium text-muted-foreground">
											{t("jira_account_label")}
										</p>
										<div className="w-full rounded-md border border-input bg-muted/50 px-3 py-2 text-sm">
											{account.name}
										</div>
									</div>
								)}

								{issue && (
									<div className="space-y-2">
										<p className="text-xs font-medium text-muted-foreground">
											{t("jira_issue_to_delete")}
										</p>
										<div className="w-full rounded-md border border-input bg-muted/50 px-3 py-2 text-sm space-y-1">
											<div className="font-medium">
												{issue.issue_identifier}: {issue.issue_title}
											</div>
											{issue.state && (
												<div className="text-xs text-muted-foreground">{issue.state}</div>
											)}
										</div>
									</div>
								)}
							</>
						)}
					</div>
				</>
			)}

			{/* delete_from_kb toggle */}
			{phase === "pending" && (
				<>
					<div className="mx-5 h-px bg-border/50" />
					<div className="px-5 py-4 select-none">
						<div className="flex items-center gap-2.5">
							<Checkbox
								id="jira-delete-from-kb"
								checked={deleteFromKb}
								onCheckedChange={(v) => setDeleteFromKb(v === true)}
								className="shrink-0"
							/>
							<label htmlFor="jira-delete-from-kb" className="flex-1 cursor-pointer">
								<span className="text-sm text-foreground">{t("common_also_remove_kb")}</span>
								<p className="text-xs text-muted-foreground mt-0.5">
									{t("common_delete_issue_kb_warning_undone")}
								</p>
							</label>
						</div>
					</div>
				</>
			)}

			{/* Action buttons */}
			{phase === "pending" && (
				<>
					<div className="mx-5 h-px bg-border/50" />
					<div className="px-5 py-4 flex items-center gap-2 select-none">
						<Button size="sm" className="rounded-lg gap-1.5" onClick={handleApprove}>
							{t("common_approve")}
							<CornerDownLeftIcon className="size-3 opacity-60" aria-hidden="true" />
						</Button>
						<Button
							size="sm"
							variant="ghost"
							className="rounded-lg text-muted-foreground"
							onClick={() => {
								setRejected();
								onDecision({ type: "reject", message: t("user_rejected") });
							}}
						>
							{t("common_reject")}
						</Button>
					</div>
				</>
			)}
		</div>
	);
}

function AuthErrorCard({ result }: { result: AuthErrorResult }) {
	const t = useTranslations("toolUi");
	return (
		<div className="my-4 max-w-lg overflow-hidden rounded-2xl border bg-muted/30 select-none">
			<div className="px-5 pt-5 pb-4">
				<p className="text-sm font-semibold text-destructive">{t("jira_auth_expired")}</p>
			</div>
			<div className="mx-5 h-px bg-border/50" />
			<div className="px-5 py-4">
				<p className="text-sm text-muted-foreground">{result.message}</p>
			</div>
		</div>
	);
}

function InsufficientPermissionsCard({ result }: { result: InsufficientPermissionsResult }) {
	const t = useTranslations("toolUi");
	return (
		<div className="my-4 max-w-lg overflow-hidden rounded-2xl border bg-muted/30 select-none">
			<div className="px-5 pt-5 pb-4">
				<p className="text-sm font-semibold text-destructive">{t("jira_insufficient_perms")}</p>
			</div>
			<div className="mx-5 h-px bg-border/50" />
			<div className="px-5 py-4">
				<p className="text-sm text-muted-foreground">{result.message}</p>
			</div>
		</div>
	);
}

function ErrorCard({ result }: { result: ErrorResult }) {
	const t = useTranslations("toolUi");
	return (
		<div className="my-4 max-w-lg overflow-hidden rounded-2xl border bg-muted/30 select-none">
			<div className="px-5 pt-5 pb-4">
				<p className="text-sm font-semibold text-destructive">{t("jira_delete_failed")}</p>
			</div>
			<div className="mx-5 h-px bg-border/50" />
			<div className="px-5 py-4">
				<p className="text-sm text-muted-foreground">{result.message}</p>
			</div>
		</div>
	);
}

function NotFoundCard({ result }: { result: NotFoundResult }) {
	const t = useTranslations("toolUi");
	return (
		<div className="my-4 max-w-lg overflow-hidden rounded-2xl border bg-muted/30 select-none">
			<div className="px-5 pt-5 pb-4">
				<p className="text-sm font-semibold text-amber-600 dark:text-amber-400">
					{t("common_issue_not_found")}
				</p>
			</div>
			<div className="mx-5 h-px bg-border/50" />
			<div className="px-5 py-4">
				<p className="text-sm text-muted-foreground">{result.message}</p>
			</div>
		</div>
	);
}

function WarningCard({ result }: { result: WarningResult }) {
	const t = useTranslations("toolUi");
	return (
		<div className="my-4 max-w-lg overflow-hidden rounded-2xl border bg-muted/30 select-none">
			<div className="flex items-start gap-3 border-b px-5 py-4">
				<p className="text-sm font-medium text-amber-600 dark:text-amber-500">
					{t("common_partial_success")}
				</p>
			</div>
			<div className="px-5 py-4">
				<p className="text-sm text-muted-foreground">{result.warning}</p>
			</div>
		</div>
	);
}

function SuccessCard({ result }: { result: SuccessResult }) {
	const t = useTranslations("toolUi");
	return (
		<div className="my-4 max-w-lg overflow-hidden rounded-2xl border bg-muted/30 select-none">
			<div className="px-5 pt-5 pb-4">
				<p className="text-sm font-semibold text-foreground">
					{result.message || t("jira_deleted_success")}
				</p>
			</div>
			{result.deleted_from_kb && (
				<>
					<div className="mx-5 h-px bg-border/50" />
					<div className="px-5 py-4 text-xs">
						<span className="text-green-600 dark:text-green-500">
							{t("common_also_removed_kb")}
						</span>
					</div>
				</>
			)}
		</div>
	);
}

export const DeleteJiraIssueToolUI = ({
	result,
}: ToolCallMessagePartProps<
	{ issue_title_or_key: string; delete_from_kb?: boolean },
	DeleteJiraIssueResult
>) => {
	const { dispatch } = useHitlDecision();

	if (!result) return null;

	if (isInterruptResult(result)) {
		return (
			<ApprovalCard
				interruptData={result as InterruptResult<DeleteJiraIssueInterruptContext>}
				onDecision={(decision) => dispatch([decision])}
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
	if (isInsufficientPermissionsResult(result))
		return <InsufficientPermissionsCard result={result} />;
	if (isAuthErrorResult(result)) return <AuthErrorCard result={result} />;
	if (isWarningResult(result)) return <WarningCard result={result} />;
	if (isErrorResult(result)) return <ErrorCard result={result} />;

	return <SuccessCard result={result as SuccessResult} />;
};
