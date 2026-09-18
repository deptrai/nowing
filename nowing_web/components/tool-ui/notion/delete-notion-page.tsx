"use client";

import type { ToolCallMessagePartProps } from "@assistant-ui/react";
import { CornerDownLeftIcon } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { TextShimmerLoader } from "@/components/prompt-kit/loader";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { useTranslations } from "next-intl";
import type { HitlDecision, InterruptResult } from "@/features/chat-messages/hitl";
import { isInterruptResult, useHitlDecision, useHitlPhase } from "@/features/chat-messages/hitl";

type NotionDeletePageContext = {
	account?: {
		id: number;
		name: string;
		workspace_id: string | null;
		workspace_name: string;
		workspace_icon: string;
	};
	page_id?: string;
	current_title?: string;
	document_id?: number;
	indexed_at?: string;
	error?: string;
};

interface SuccessResult {
	status: "success";
	page_id: string;
	title?: string;
	message?: string;
	deleted_from_kb?: boolean;
}

interface ErrorResult {
	status: "error";
	message: string;
}

interface InfoResult {
	status: "not_found";
	message: string;
}

interface WarningResult {
	status: "success";
	warning: string;
	page_id?: string;
	title?: string;
	message?: string;
}

interface AuthErrorResult {
	status: "auth_error";
	message: string;
	connector_id?: number;
	connector_type: string;
}

type DeleteNotionPageResult =
	| InterruptResult<NotionDeletePageContext>
	| SuccessResult
	| ErrorResult
	| InfoResult
	| WarningResult
	| AuthErrorResult;

function isErrorResult(result: unknown): result is ErrorResult {
	return (
		typeof result === "object" &&
		result !== null &&
		"status" in result &&
		(result as ErrorResult).status === "error"
	);
}

function isInfoResult(result: unknown): result is InfoResult {
	return (
		typeof result === "object" &&
		result !== null &&
		"status" in result &&
		(result as InfoResult).status === "not_found"
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

function ApprovalCard({
	interruptData,
	onDecision,
}: {
	interruptData: InterruptResult<NotionDeletePageContext>;
	onDecision: (decision: HitlDecision) => void;
}) {
	const t = useTranslations("toolUi");
	const { phase, setProcessing, setRejected } = useHitlPhase(interruptData);
	const [deleteFromKb, setDeleteFromKb] = useState(false);

	const context = interruptData.context;
	const account = context?.account;
	const currentTitle = context?.current_title;

	const handleApprove = useCallback(() => {
		if (phase !== "pending") return;
		setProcessing();
		onDecision({
			type: "approve",
			edited_action: {
				name: interruptData.action_requests[0].name,
				args: {
					page_id: interruptData.context?.page_id,
					connector_id: account?.id,
					delete_from_kb: deleteFromKb,
				},
			},
		});
	}, [phase, setProcessing, onDecision, interruptData, account?.id, deleteFromKb]);

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
							? t("notion_delete_rejected")
							: phase === "processing" || phase === "complete"
								? t("notion_delete_approved")
								: t("notion_delete_title")}
					</p>
					{phase === "processing" ? (
						<TextShimmerLoader text={t("notion_deleting_page")} size="sm" />
					) : phase === "complete" ? (
						<p className="text-xs text-muted-foreground mt-0.5">{t("notion_page_deleted")}</p>
					) : phase === "rejected" ? (
						<p className="text-xs text-muted-foreground mt-0.5">{t("notion_delete_cancelled")}</p>
					) : (
						<p className="text-xs text-muted-foreground mt-0.5">
							{t("common_requires_approval")}
						</p>
					)}
				</div>
			</div>

			{/* Context section — read-only account and page info */}
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
										<p className="text-xs font-medium text-muted-foreground">{t("notion_account_label")}</p>
										<div className="w-full rounded-md border border-input bg-muted/50 px-3 py-2 text-sm">
											{account.workspace_icon} {account.workspace_name}
										</div>
									</div>
								)}

								{currentTitle && (
									<div className="space-y-2">
										<p className="text-xs font-medium text-muted-foreground">{t("notion_page_to_delete")}</p>
										<div className="w-full rounded-md border border-input bg-muted/50 px-3 py-2 text-sm">
											{currentTitle}
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
								id="notion-delete-from-kb"
								checked={deleteFromKb}
								onCheckedChange={(v) => setDeleteFromKb(v === true)}
								className="shrink-0"
							/>
							<label htmlFor="notion-delete-from-kb" className="flex-1 cursor-pointer">
								<span className="text-sm text-foreground">{t("common_also_remove_kb")}</span>
								<p className="text-xs text-muted-foreground mt-0.5">
									{t("common_delete_kb_warning_undone")}
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
								onDecision({ type: "reject", message: "User rejected the action." });
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
				<p className="text-sm font-semibold text-destructive">{t("notion_all_accounts_expired")}</p>
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
				<p className="text-sm font-semibold text-destructive">{t("notion_delete_failed")}</p>
			</div>
			<div className="mx-5 h-px bg-border/50" />
			<div className="px-5 py-4">
				<p className="text-sm text-muted-foreground">{result.message}</p>
			</div>
		</div>
	);
}

function InfoCard({ result }: { result: InfoResult }) {
	const t = useTranslations("toolUi");
	return (
		<div className="my-4 max-w-lg overflow-hidden rounded-2xl border bg-muted/30 select-none">
			<div className="px-5 pt-5 pb-4">
				<p className="text-sm font-semibold text-amber-600 dark:text-amber-400">{t("notion_page_not_found")}</p>
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
				<p className="text-sm font-medium text-amber-600 dark:text-amber-500">{t("common_partial_success")}</p>
			</div>
			<div className="px-5 py-4 space-y-2 text-xs">
				<p className="text-sm text-muted-foreground">{result.warning}</p>
				{result.title && (
					<div className="pt-2">
						<span className="font-medium text-muted-foreground">{t("notion_deleted_page_label")} </span>
						<span>{result.title}</span>
					</div>
				)}
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
					{result.message || t("notion_deleted_success")}
				</p>
			</div>
			{(result.deleted_from_kb || result.title) && (
				<>
					<div className="mx-5 h-px bg-border/50" />
					<div className="px-5 py-4 space-y-2 text-xs">
						{result.title && (
							<div>
								<span className="font-medium text-muted-foreground">{t("notion_deleted_page_label")} </span>
								<span>{result.title}</span>
							</div>
						)}
						{result.deleted_from_kb && (
							<div className="pt-1">
								<span className="text-green-600 dark:text-green-500">
									{t("common_also_removed_kb")}
								</span>
							</div>
						)}
					</div>
				</>
			)}
		</div>
	);
}

export const DeleteNotionPageToolUI = ({
	result,
}: ToolCallMessagePartProps<
	{ page_title: string; delete_from_kb?: boolean },
	DeleteNotionPageResult
>) => {
	const { dispatch } = useHitlDecision();

	if (!result) return null;

	if (isInterruptResult(result)) {
		return (
			<ApprovalCard
				interruptData={result as InterruptResult<NotionDeletePageContext>}
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

	if (isInfoResult(result)) {
		return <InfoCard result={result} />;
	}

	if (isWarningResult(result)) {
		return <WarningCard result={result} />;
	}

	if (isAuthErrorResult(result)) {
		return <AuthErrorCard result={result} />;
	}

	if (isErrorResult(result)) {
		return <ErrorCard result={result} />;
	}

	return <SuccessCard result={result as SuccessResult} />;
};
